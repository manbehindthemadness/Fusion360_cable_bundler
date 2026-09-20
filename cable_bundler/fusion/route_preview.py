"""
Translate Fusion profiles into routing frames and transient centerline graphics.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional
from uuid import UUID, uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import (
    CableColor,
    HarnessDefinition,
)
from ..routing import (
    RoutePreview,
    Vector3,
    sample_centerline,
)
from .route_preview_parts.solver import (
    leg_control_ids,
    reset_route_solve_cache,
    solve_cable_group_routes,
)

PREVIEW_GROUP_ID = "kev0.cable_bundler.route_preview"
_PREVIEW_COLORS = (
    (23, 119, 200),
    (220, 92, 66),
    (40, 145, 85),
    (154, 87, 190),
    (220, 153, 42),
    (37, 153, 165),
)


@dataclass
class _PreviewState:
    """
    Retain the inputs and paths actually displayed by one transient preview.
    """

    definition: HarnessDefinition
    routes: dict[UUID, RoutePreview]
    color_indices: dict[UUID, int]
    clearance_mm: float
    route_group_ids: dict[UUID, UUID] = field(default_factory=dict)
    route_connection_ids: dict[UUID, tuple[UUID, ...]] = field(default_factory=dict)
    route_pathway_ids: dict[UUID, tuple[UUID, ...]] = field(default_factory=dict)
    route_control_ids: dict[UUID, tuple[UUID, ...]] = field(default_factory=dict)


_preview_states: dict[str, _PreviewState] = {}
_preview_history: dict[tuple[str, HarnessDefinition], _PreviewState] = {}


def _remember_preview(group_id: str, state: _PreviewState) -> None:
    """
    Preserve a cache snapshot for graphics restored by Fusion Undo/Redo.
    """
    _preview_history[group_id, state.definition] = replace(
        state,
        routes=dict(state.routes),
        color_indices=dict(state.color_indices),
        route_group_ids=dict(state.route_group_ids),
        route_connection_ids=dict(state.route_connection_ids),
        route_pathway_ids=dict(state.route_pathway_ids),
        route_control_ids=dict(state.route_control_ids),
    )


def reset_preview_history() -> None:
    """
    Release session-only snapshots when the add-in stops.
    """
    _preview_states.clear()
    _preview_history.clear()
    reset_route_solve_cache()


def reconcile_preview_history(
    design: adsk.fusion.Design, definitions: tuple[HarnessDefinition, ...]
) -> None:
    """
    Adopt caches matching restored graphics without any Fusion model writes.

    Fusion restores graphics in the edit transaction. Recreating them here would
    create a new edit and risk clearing Redo. Unknown states force a fresh solve
    on the next explicit edit instead.
    """
    by_id = {definition.harness_id: definition for definition in definitions}
    groups = design.rootComponent.customGraphicsGroups
    for index in range(groups.count):
        group = groups.item(index)
        if group is None or not _is_preview_group(group):
            continue
        candidates = [
            state for (identity, _), state in _preview_history.items() if identity == group.id
        ]
        if not candidates:
            continue
        latest = candidates[-1]
        definition = by_id.get(latest.definition.harness_id)
        if definition is None:
            _preview_states.pop(group.id, None)
            continue
        saved = _preview_history.get((group.id, definition))
        _preview_states[group.id] = replace(
            saved or latest,
            definition=definition,
            routes=dict(saved.routes) if saved else {},
            color_indices=dict((saved or latest).color_indices),
            route_group_ids=dict((saved or latest).route_group_ids),
            route_connection_ids=dict((saved or latest).route_connection_ids),
            route_pathway_ids=dict((saved or latest).route_pathway_ids),
            route_control_ids=dict((saved or latest).route_control_ids),
        )


def _is_preview_group(group: adsk.fusion.CustomGraphicsGroup) -> bool:
    """
    Recognize cached, named, and explicitly identified Cable Bundler previews.

    Fusion may retain a host-assigned group ID, so the live cache and the name
    assigned during creation are authoritative fallbacks.
    """
    return (
        group.id in _preview_states
        or group.id == PREVIEW_GROUP_ID
        or group.id.startswith(f"{PREVIEW_GROUP_ID}:")
        or group.name.endswith(" Route Preview")
        or _has_cable_preview_children(group)
    )


def _has_cable_preview_children(group: adsk.fusion.CustomGraphicsGroup) -> bool:
    """
    Recognize an orphaned preview by the cable groups created beneath it.

    This supports graphics left by an earlier add-in session whose Python cache
    is gone and whose top-level ID or name was not retained by Fusion.
    """
    for index in range(group.count):
        child = adsk.fusion.CustomGraphicsGroup.cast(group.item(index))
        if (
            child is not None
            and child.name.startswith("Cable ")
            and child.name.endswith(" Preview")
        ):
            return True
    return False


def show_route_previews(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[RoutePreview, ...]:
    """
    Solve and display transient centerlines for grouped cable-end networks.

    Raises:
        RuntimeError: If referenced geometry is unavailable or unsupported.
        ValueError: If route inputs are invalid.
    """
    routes, legs = solve_cable_group_routes(design, definition, notices)
    root_component = design.rootComponent
    clear_route_previews(design)
    preview_group = root_component.customGraphicsGroups.add()
    if preview_group is None:
        raise RuntimeError("Fusion did not create the route-preview graphics group.")
    preview_group.id = f"{PREVIEW_GROUP_ID}:{uuid4()}"
    preview_group.name = f"{definition.name} Route Preview"
    route_group_ids = {leg.route_id: leg.cable_group_id for leg in legs}
    groups_by_id = {group.cable_group_id: group for group in definition.cable_groups}
    try:
        for index, route in enumerate(routes):
            cable_group = groups_by_id[route_group_ids[route.cable_id]]
            _add_route_graphics(
                preview_group,
                route,
                index,
                definition.cable_group_materials(cable_group).main_color,
            )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        preview_group.deleteMe()
        raise
    group_connections = {
        group.cable_group_id: group.connection_ids for group in definition.cable_groups
    }
    end_control_ids = {
        end.connection_id: end.ordered_control_ids for end in definition.standalone_ends
    }
    _preview_states[preview_group.id] = _PreviewState(
        definition,
        {route.cable_id: route for route in routes},
        {route.cable_id: index for index, route in enumerate(routes)},
        definition.minimum_clearance_mm,
        route_group_ids=route_group_ids,
        route_connection_ids={leg.route_id: group_connections[leg.cable_group_id] for leg in legs},
        route_pathway_ids={leg.route_id: leg.pathway_ids for leg in legs},
        route_control_ids={leg.route_id: leg_control_ids(leg, end_control_ids) for leg in legs},
    )
    _remember_preview(preview_group.id, _preview_states[preview_group.id])
    return routes


def clear_route_previews(design: adsk.fusion.Design) -> int:
    """
    Delete Cable Bundler route-preview graphics from the active design.
    """
    deleted_count = 0
    for groups in _design_graphics_collections(design):
        for index in range(groups.count - 1, -1, -1):
            group = groups.item(index)
            if group is not None and _is_preview_group(group):
                group_id = group.id
                state = _preview_states.get(group_id)
                if state is not None:
                    _remember_preview(group_id, state)
                _delete_graphics_group(group)
                _preview_states.pop(group_id, None)
                deleted_count += 1
    return deleted_count


def has_route_previews(design: adsk.fusion.Design) -> bool:
    """
    Report whether the live Fusion object model exposes a Cable Bundler preview.

    Fusion can serialize Custom Graphics into its OGS scene cache while dropping
    their API objects on reload. This check intentionally covers only graphics
    that are still reachable and can therefore be protected before a save.
    """
    for groups in _design_graphics_collections(design):
        for index in range(groups.count):
            group = groups.item(index)
            if group is not None and _is_preview_group(group):
                return True
    return False


def has_route_preview_for_harness(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
) -> bool:
    """
    Report whether the live preview belongs to the specified harness.

    Cached identity is authoritative. The assigned group name recovers identity
    after a plugin reload, when Fusion can retain graphics but Python state is
    no longer available.
    """
    expected_name = f"{definition.name} Route Preview"
    for groups in _design_graphics_collections(design):
        for index in range(groups.count):
            group = groups.item(index)
            if group is None or not _is_preview_group(group):
                continue
            state = _preview_states.get(group.id)
            if state is not None:
                if state.definition.harness_id == definition.harness_id:
                    return True
                continue
            if group.name == expected_name:
                return True
    return False


def _design_graphics_collections(
    design: adsk.fusion.Design,
) -> tuple[adsk.fusion.CustomGraphicsGroups, ...]:
    """
    Return Custom Graphics collections for every component in the design.

    A preview restored with a document can belong to an assembly or external
    component even though new previews are currently created on the design root.
    """
    root_groups = design.rootComponent.customGraphicsGroups
    collections = [root_groups]
    all_components = design.allComponents
    for index in range(all_components.count):
        component = all_components.item(index)
        if component is None or component == design.rootComponent:
            continue
        collections.append(component.customGraphicsGroups)
    return tuple(collections)


def _delete_graphics_group(group: adsk.fusion.CustomGraphicsGroup) -> None:
    """
    Hide and explicitly empty a preview group before deleting its container.

    Hiding removes the graphics from the viewport immediately. Explicit child
    deletion avoids relying on Fusion to cascade nested groups after a palette
    event has returned.
    """
    group.isVisible = False
    for index in range(group.count - 1, -1, -1):
        child = group.item(index)
        if child is not None and child.deleteMe() is False:
            raise RuntimeError("Fusion could not delete a route-preview graphics entity.")
    if group.deleteMe() is False:
        raise RuntimeError("Fusion could not delete a route-preview graphics group.")


def _cable_graphics(
    group: adsk.fusion.CustomGraphicsGroup,
    cable_ids: set[UUID],
) -> tuple[adsk.fusion.CustomGraphicsGroup, ...]:
    """
    Find existing children by stable cable identity without touching other paths.
    """
    identities = {str(identity) for identity in cable_ids}
    children = []
    for index in range(group.count):
        child = adsk.fusion.CustomGraphicsGroup.cast(group.item(index))
        if child is not None and child.id in identities:
            children.append(child)
    return tuple(children)


def refresh_route_previews(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
) -> tuple[str, ...]:
    """
    Recompute active cable-group previews and retain the last valid graphics on failure.
    """
    groups = design.rootComponent.customGraphicsGroups
    warnings: list[str] = []
    for index in range(groups.count):
        group = groups.item(index)
        if group is None:
            continue
        state = _preview_states.get(group.id)
        if state is None or state.definition.harness_id != definition.harness_id:
            continue
        warning = _refresh_cable_group_preview(design, group, state, definition)
        if warning:
            warnings.append(warning)
    return tuple(warnings)


def _refresh_cable_group_preview(
    design: adsk.fusion.Design,
    group: adsk.fusion.CustomGraphicsGroup,
    state: _PreviewState,
    definition: HarnessDefinition,
) -> str:
    """
    Reconcile one active group-network preview after a saved definition edit.

    An unexpected planning failure keeps the last valid graphics visible and
    reports a warning; removing every group intentionally clears every leg.
    """
    _remember_preview(group.id, state)
    if not definition.cable_groups:
        for child in _cable_graphics(group, set(state.routes)):
            child.deleteMe()
        state.definition = definition
        state.routes.clear()
        state.route_group_ids.clear()
        state.route_connection_ids.clear()
        state.route_pathway_ids.clear()
        state.route_control_ids.clear()
        _remember_preview(group.id, state)
        return ""
    solve_notices: list[str] = []
    try:
        routes, legs = solve_cable_group_routes(design, definition, solve_notices)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        return f"Preview update failed for a cable group: {error}"
    solved = {route.cable_id: route for route in routes}
    removed_ids = set(state.routes) - set(solved)
    for child in _cable_graphics(group, removed_ids):
        child.deleteMe()
    for route_id in removed_ids:
        state.routes.pop(route_id, None)
    old_groups = {item.cable_group_id: item for item in state.definition.cable_groups}
    new_groups = {item.cable_group_id: item for item in definition.cable_groups}
    route_group_ids = {leg.route_id: leg.cable_group_id for leg in legs}
    warnings: list[str] = solve_notices
    for route in routes:
        group_id = route_group_ids[route.cable_id]
        old_group = old_groups.get(group_id)
        new_group = new_groups[group_id]
        color_changed = old_group is None or (
            state.definition.cable_group_materials(old_group).main_color
            != definition.cable_group_materials(new_group).main_color
        )
        if state.routes.get(route.cable_id) == route and not color_changed:
            continue
        previous = _cable_graphics(group, {route.cable_id})
        color_index = state.color_indices.setdefault(
            route.cable_id, max(state.color_indices.values(), default=-1) + 1
        )
        try:
            _add_route_graphics(
                group,
                route,
                color_index,
                definition.cable_group_materials(new_group).main_color,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            for child in _cable_graphics(group, {route.cable_id}):
                child.deleteMe()
            state.routes.pop(route.cable_id, None)
            warnings.append(f"Could not draw {route.cable_number}: {error}")
            continue
        for child in previous:
            child.deleteMe()
        state.routes[route.cable_id] = route
    group_connections = {
        cable_group.cable_group_id: cable_group.connection_ids
        for cable_group in definition.cable_groups
    }
    drawn_leg_ids = set(state.routes)
    state.definition = definition
    state.clearance_mm = definition.minimum_clearance_mm
    state.route_group_ids = {
        leg.route_id: leg.cable_group_id for leg in legs if leg.route_id in drawn_leg_ids
    }
    state.route_connection_ids = {
        leg.route_id: group_connections[leg.cable_group_id]
        for leg in legs
        if leg.route_id in drawn_leg_ids
    }
    state.route_pathway_ids = {
        leg.route_id: leg.pathway_ids for leg in legs if leg.route_id in drawn_leg_ids
    }
    state.route_control_ids = {
        leg.route_id: leg_control_ids(
            leg,
            {end.connection_id: end.ordered_control_ids for end in definition.standalone_ends},
        )
        for leg in legs
        if leg.route_id in drawn_leg_ids
    }
    _remember_preview(group.id, state)
    return " ".join(warnings)


def highlight_route_preview(design: adsk.fusion.Design, group_id: Optional[UUID]) -> int:
    """
    Emphasize one existing cable-group network and restore all other preview widths.

    A missing preview is a harmless no-op; None clears hover emphasis.
    """
    return highlight_route_members(design, (group_id,) if group_id is not None else ())


def highlight_route_members(
    design: adsk.fusion.Design,
    group_ids: tuple[UUID, ...],
    *,
    connection_ids: tuple[UUID, ...] = (),
    pathway_ids: tuple[UUID, ...] = (),
    control_ids: tuple[UUID, ...] = (),
) -> int:
    """
    Emphasize complete cable-group preview networks matching the supplied members.
    """
    selected_group_ids = set(group_ids)
    selected_ids: set[str] = set()
    selected_count = 0
    groups = design.rootComponent.customGraphicsGroups
    for index in range(groups.count):
        group = groups.item(index)
        if group is None or not _is_preview_group(group):
            continue
        state = _preview_states.get(group.id)
        matched_group_ids: set[UUID] = set()
        if state is not None:
            connection_set = set(connection_ids)
            pathway_set = set(pathway_ids)
            control_set = set(control_ids)
            for route_id, group_id in state.route_group_ids.items():
                if (
                    connection_set.intersection(state.route_connection_ids.get(route_id, ()))
                    or pathway_set.intersection(state.route_pathway_ids.get(route_id, ()))
                    or control_set.intersection(state.route_control_ids.get(route_id, ()))
                ):
                    matched_group_ids.add(group_id)
            selected_ids.update(
                str(route_id)
                for route_id, group_id in state.route_group_ids.items()
                if group_id in selected_group_ids or group_id in matched_group_ids
            )
        for child_index in range(group.count):
            cable_group = adsk.fusion.CustomGraphicsGroup.cast(group.item(child_index))
            if cable_group is None:
                continue
            selected = cable_group.id in selected_ids
            for line_index in range(cable_group.count):
                lines = adsk.fusion.CustomGraphicsLines.cast(cable_group.item(line_index))
                if lines is not None:
                    lines.weight = 5.0 if selected else 1.0
                    if selected:
                        selected_count += 1
    return selected_count


def _add_route_graphics(
    preview_group: adsk.fusion.CustomGraphicsGroup,
    route: RoutePreview,
    color_index: int,
    cable_color: Optional[CableColor] = None,
) -> None:
    """
    Add one selectable colored line strip to a preview group.
    """
    cable_group = preview_group.addGroup()
    if cable_group is None:
        raise RuntimeError(f"Fusion did not create graphics for cable {route.cable_number}.")
    cable_group.id = str(route.cable_id)
    cable_group.name = f"Cable {route.cable_number} Preview"
    sampled_points = sample_centerline(route)
    coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
        [
            coordinate / 10.0
            for point in sampled_points
            for coordinate in (point.x, point.y, point.z)
        ]
    )
    if coordinates is None:
        raise RuntimeError(f"Fusion did not create coordinates for cable {route.cable_number}.")
    lines = cable_group.addLines(coordinates, [], True)
    if lines is None:
        raise RuntimeError(f"Fusion did not draw cable {route.cable_number}.")
    lines.name = f"Cable {route.cable_number} Centerline"
    lines.weight = 1.0
    red, green, blue = (
        (cable_color.red, cable_color.green, cable_color.blue)
        if cable_color is not None
        else _PREVIEW_COLORS[color_index % len(_PREVIEW_COLORS)]
    )
    color = adsk.core.Color.create(red, green, blue, 255)
    color_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(color)
    if color_effect is None:
        raise RuntimeError(f"Fusion did not create a color for cable {route.cable_number}.")
    lines.color = color_effect


def _point_to_mm(point: adsk.core.Point3D) -> Vector3:
    """
    Convert a Fusion point from centimeters to millimeters.
    """
    return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)


def _vector(vector: adsk.core.Vector3D) -> Vector3:
    """
    Copy a Fusion model-space direction into the routing model.
    """
    return Vector3(vector.x, vector.y, vector.z)


def solve_cable_group_centerlines(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[tuple[RoutePreview, ...], tuple[CableGroupRouteLeg, ...]]:
    """
    Resolve grouped-cable legs without changing transient preview state.

    The returned legs and routes share stable route identities and definition
    order so persistent generation can consume exactly the geometry previewed
    by the user.
    """
    return solve_cable_group_routes(design, definition, notices)
