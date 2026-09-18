"""
Translate Fusion profiles into routing frames and transient centerline graphics.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Optional, Union
from uuid import UUID, uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import WireGroupRouteLeg, plan_wire_group_routes
from ..domain import (
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    WireColor,
)
from ..routing import (
    GateFrame,
    RefineFrame,
    RouteCollision,
    RoutePreview,
    TransitionAdjustment,
    TransitionLengths,
    Vector3,
    WireRouteInput,
    fair_route,
    minimum_circular_bend_radius,
    place_route_crossings,
    sample_centerline,
    separate_route_collisions,
)
from ..routing.geometry import cross, difference, dot, unit

PREVIEW_GROUP_ID = "kev0.wire_bundler.route_preview"
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


@dataclass(frozen=True)
class _ProfileFrame:
    """
    Describe one end guide and any circular interior available to its route.
    """

    origin: Vector3
    normal: Vector3
    u_direction: Vector3
    v_direction: Vector3
    usable_radius_mm: Optional[float] = None


@dataclass(frozen=True)
class _RouteSolveCache:
    """
    Retain one geometry-validated route solution for immediate reuse.
    """

    design: adsk.fusion.Design
    definition: HarnessDefinition
    control_frames: tuple[tuple[UUID, Union[GateFrame, RefineFrame]], ...]
    profile_frames: tuple[tuple[str, _ProfileFrame], ...]
    routes: tuple[RoutePreview, ...]
    legs: tuple[WireGroupRouteLeg, ...]
    notices: tuple[str, ...]


_preview_states: dict[str, _PreviewState] = {}
_preview_history: dict[tuple[str, HarnessDefinition], _PreviewState] = {}
_route_solve_cache: Optional[_RouteSolveCache] = None


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
    global _route_solve_cache

    _preview_states.clear()
    _preview_history.clear()
    _route_solve_cache = None


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
    Recognize cached, named, and explicitly identified Wire Bundler previews.

    Fusion may retain a host-assigned group ID, so the live cache and the name
    assigned during creation are authoritative fallbacks.
    """
    return (
        group.id in _preview_states
        or group.id == PREVIEW_GROUP_ID
        or group.id.startswith(f"{PREVIEW_GROUP_ID}:")
        or group.name.endswith(" Route Preview")
        or _has_wire_preview_children(group)
    )


def _has_wire_preview_children(group: adsk.fusion.CustomGraphicsGroup) -> bool:
    """
    Recognize an orphaned preview by the wire groups created beneath it.

    This supports graphics left by an earlier add-in session whose Python cache
    is gone and whose top-level ID or name was not retained by Fusion.
    """
    for index in range(group.count):
        child = adsk.fusion.CustomGraphicsGroup.cast(group.item(index))
        if child is not None and child.name.startswith("Wire ") and child.name.endswith(" Preview"):
            return True
    return False


def show_route_previews(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[RoutePreview, ...]:
    """
    Solve and display transient centerlines for grouped wire-end networks.

    Raises:
        RuntimeError: If referenced geometry is unavailable or unsupported.
        ValueError: If route inputs or gate capacity are invalid.
    """
    routes, legs = _solve_wire_group_routes(design, definition, notices)
    root_component = design.rootComponent
    clear_route_previews(design)
    preview_group = root_component.customGraphicsGroups.add()
    if preview_group is None:
        raise RuntimeError("Fusion did not create the route-preview graphics group.")
    preview_group.id = f"{PREVIEW_GROUP_ID}:{uuid4()}"
    preview_group.name = f"{definition.name} Route Preview"
    route_group_ids = {leg.route_id: leg.wire_group_id for leg in legs}
    groups_by_id = {group.wire_group_id: group for group in definition.wire_groups}
    try:
        for index, route in enumerate(routes):
            wire_group = groups_by_id[route_group_ids[route.wire_id]]
            _add_route_graphics(
                preview_group,
                route,
                index,
                definition.wire_group_materials(wire_group).main_color,
            )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        preview_group.deleteMe()
        raise
    group_connections = {
        group.wire_group_id: group.connection_ids for group in definition.wire_groups
    }
    _preview_states[preview_group.id] = _PreviewState(
        definition,
        {route.wire_id: route for route in routes},
        {route.wire_id: index for index, route in enumerate(routes)},
        definition.minimum_clearance_mm,
        route_group_ids=route_group_ids,
        route_connection_ids={leg.route_id: group_connections[leg.wire_group_id] for leg in legs},
        route_pathway_ids={leg.route_id: leg.pathway_ids for leg in legs},
        route_control_ids={
            leg.route_id: tuple(step.control_id for step in leg.control_steps) for leg in legs
        },
    )
    _remember_preview(preview_group.id, _preview_states[preview_group.id])
    return routes


def clear_route_previews(design: adsk.fusion.Design) -> int:
    """
    Delete Wire Bundler route-preview graphics from the active design.
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
    Report whether the live Fusion object model exposes a Wire Bundler preview.

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


def _wire_graphics(
    group: adsk.fusion.CustomGraphicsGroup,
    wire_ids: set[UUID],
) -> tuple[adsk.fusion.CustomGraphicsGroup, ...]:
    """
    Find existing children by stable wire identity without touching other paths.
    """
    identities = {str(identity) for identity in wire_ids}
    children = []
    for index in range(group.count):
        child = adsk.fusion.CustomGraphicsGroup.cast(group.item(index))
        if child is not None and child.id in identities:
            children.append(child)
    return tuple(children)


def _solve_wire_group_routes(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[tuple[RoutePreview, ...], tuple[WireGroupRouteLeg, ...]]:
    """
    Solve every wire group as one topology tree with shared hub crossings.

    One group occupies one slot at each control regardless of how many legs
    meet there, preventing duplicated paths and split junction crossings.
    """
    global _route_solve_cache

    if not definition.wire_groups:
        raise ValueError("Create at least one wire group before previewing routes.")
    legs = plan_wire_group_routes(definition)
    groups_by_id = {group.wire_group_id: group for group in definition.wire_groups}
    controls = {control.control_id: control for control in definition.controls}
    connections = {connection.connection_id: connection for connection in definition.connections}
    frames: dict[UUID, Union[GateFrame, RefineFrame]] = {}
    group_order = {group.wire_group_id: index for index, group in enumerate(definition.wire_groups)}
    control_groups: dict[UUID, list[UUID]] = defaultdict(list)
    for leg in legs:
        for step in leg.control_steps:
            if step.control_id not in frames:
                frames[step.control_id] = _routing_frame(
                    design, controls.get(step.control_id), step.control_id
                )
            if leg.wire_group_id not in control_groups[step.control_id]:
                control_groups[step.control_id].append(leg.wire_group_id)
    profile_frames: dict[str, _ProfileFrame] = {}
    for leg in legs:
        for connection_id, position in (
            (leg.start_connection_id, "start"),
            (leg.end_connection_id, "end"),
        ):
            if connection_id is None:
                continue
            connection = connections.get(connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing {position} connection.")
            _connection_profile_frames(design, connection, profile_frames)
    control_frame_snapshot = tuple(sorted(frames.items(), key=lambda item: str(item[0])))
    profile_frame_snapshot = tuple(sorted(profile_frames.items()))
    cached = _route_solve_cache
    if (
        cached is not None
        and cached.design is design
        and cached.definition == definition
        and cached.control_frames == control_frame_snapshot
        and cached.profile_frames == profile_frame_snapshot
    ):
        if notices is not None:
            notices.extend(cached.notices)
        return cached.routes, cached.legs
    crossings: dict[tuple[UUID, UUID], Vector3] = {}
    prior_crossings: dict[UUID, Vector3] = {}
    origin = Vector3(0.0, 0.0, 0.0)
    for control_id, group_ids in control_groups.items():
        ordered_group_ids = sorted(group_ids, key=group_order.__getitem__)
        placement_inputs = tuple(
            WireRouteInput(
                wire_id=group_id,
                wire_number=f"Group {group_order[group_id] + 1}",
                start=origin,
                end=origin,
                diameter_mm=groups_by_id[group_id].diameter_mm,
            )
            for group_id in ordered_group_ids
        )
        points = place_route_crossings(
            placement_inputs,
            frames[control_id],
            definition.minimum_clearance_mm,
            tuple(prior_crossings.get(group_id) for group_id in ordered_group_ids),
        )
        crossings.update(
            ((control_id, group_id), point) for group_id, point in zip(ordered_group_ids, points)
        )
        prior_crossings.update(zip(ordered_group_ids, points))

    routes: list[RoutePreview] = []
    route_group_ids: list[UUID] = []
    route_diameters: list[float] = []
    route_normals: list[tuple[Vector3, ...]] = []
    route_transitions: list[tuple[TransitionLengths, ...]] = []
    minimum_bend_radii: list[float] = []
    solve_notices: list[str] = []
    for leg in legs:
        diameter_mm = groups_by_id[leg.wire_group_id].diameter_mm
        points: list[Vector3] = []
        normals: list[Vector3] = []
        transitions: list[TransitionLengths] = []
        start_frames: tuple[_ProfileFrame, ...] = ()
        if leg.start_connection_id is not None:
            connection = connections.get(leg.start_connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing start connection.")
            connection_frames = _connection_profile_frames(design, connection, profile_frames)
            start_frames = connection_frames
            points.extend(frame.origin for frame in connection_frames)
            normals.extend(frame.normal for frame in connection_frames)
            transitions.extend(
                TransitionLengths(settings.approach_mm, settings.departure_mm)
                for settings in connection.member_settings
            )
        for step in leg.control_steps:
            control = controls.get(step.control_id)
            if control is None:
                raise RuntimeError(f"{leg.label} references a missing routing control.")
            frame = frames[step.control_id]
            points.append(crossings[step.control_id, leg.wire_group_id])
            normals.append(cross(frame.u_direction, frame.v_direction))
            settings = control.interpolation
            transitions.append(
                TransitionLengths(
                    settings.departure_mm if step.reversed else settings.approach_mm,
                    settings.approach_mm if step.reversed else settings.departure_mm,
                )
            )
        if start_frames and len(points) > len(start_frames):
            start_points = _connection_profile_points(
                start_frames,
                points[len(start_frames)],
                diameter_mm,
            )
            points[: len(start_frames)] = start_points
        if leg.end_connection_id is not None:
            connection = connections.get(leg.end_connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing end connection.")
            connection_frames = _connection_profile_frames(design, connection, profile_frames)
            end_points = _connection_profile_points(
                connection_frames,
                points[-1],
                diameter_mm,
            )
            points.extend(reversed(end_points))
            normals.extend(frame.normal for frame in reversed(connection_frames))
            transitions.extend(
                TransitionLengths(settings.departure_mm, settings.approach_mm)
                for settings in reversed(connection.member_settings)
            )
        if len(points) < 2:
            raise ValueError(f"{leg.label} does not contain enough route geometry.")
        route = RoutePreview(leg.route_id, leg.label, tuple(points))
        adjustments: list[TransitionAdjustment] = []
        minimum_bend_radius = minimum_circular_bend_radius(diameter_mm)
        route = fair_route(
            route,
            tuple(normals),
            tuple(transitions),
            minimum_bend_radius_mm=minimum_bend_radius,
            adjustments=adjustments,
        )
        routes.append(route)
        route_group_ids.append(leg.wire_group_id)
        route_diameters.append(diameter_mm)
        route_normals.append(tuple(normals))
        route_transitions.append(tuple(transitions))
        minimum_bend_radii.append(minimum_bend_radius)
        solve_notices.extend(_adjustment_notice(item) for item in adjustments)
    separated_routes, collisions = separate_route_collisions(
        tuple(routes),
        tuple(route_group_ids),
        tuple(route_diameters),
        tuple(route_normals),
        tuple(route_transitions),
        tuple(minimum_bend_radii),
        definition.minimum_clearance_mm,
    )
    solve_notices.extend(_collision_notice(item) for item in collisions)
    _route_solve_cache = _RouteSolveCache(
        design,
        definition,
        control_frame_snapshot,
        profile_frame_snapshot,
        separated_routes,
        legs,
        tuple(solve_notices),
    )
    if notices is not None:
        notices.extend(solve_notices)
    return separated_routes, legs


def _connection_profile_frames(
    design: adsk.fusion.Design,
    connection: Connection,
    cache: dict[str, _ProfileFrame],
) -> tuple[_ProfileFrame, ...]:
    """
    Resolve and cache every ordered profile frame owned by one connection.
    """
    member_tokens = connection.member_tokens
    for token in member_tokens:
        if token not in cache:
            cache[token] = _profile_frame(design, token)
    return tuple(cache[token] for token in member_tokens)


def _connection_profile_points(
    frames: tuple[_ProfileFrame, ...],
    pathway_target: Vector3,
    diameter_mm: float,
) -> list[Vector3]:
    """
    Use circular guide interiors to approach the pathway without slot swaps.

    Frames are stored terminal-to-pathway, so placement propagates backward
    from the known pathway crossing while preserving the authored guide order.
    """
    reversed_points: list[Vector3] = []
    target = pathway_target
    for frame in reversed(frames):
        radius = frame.usable_radius_mm
        if radius is None:
            point = frame.origin
        else:
            available_radius = max(0.0, radius - diameter_mm / 2.0)
            delta = difference(target, frame.origin)
            u_offset = dot(delta, frame.u_direction)
            v_offset = dot(delta, frame.v_direction)
            distance = math.hypot(u_offset, v_offset)
            scale = (
                1.0
                if distance <= available_radius or distance <= 1e-12
                else available_radius / distance
            )
            point = frame.origin.translated(frame.u_direction, u_offset * scale).translated(
                frame.v_direction,
                v_offset * scale,
            )
        reversed_points.append(point)
        target = point
    return list(reversed(reversed_points))


def refresh_route_previews(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
) -> tuple[str, ...]:
    """
    Recompute active wire-group previews and retain the last valid graphics on failure.
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
        warning = _refresh_wire_group_preview(design, group, state, definition)
        if warning:
            warnings.append(warning)
    return tuple(warnings)


def _refresh_wire_group_preview(
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
    if not definition.wire_groups:
        for child in _wire_graphics(group, set(state.routes)):
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
        routes, legs = _solve_wire_group_routes(design, definition, solve_notices)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        return f"Preview update failed for a wire group: {error}"
    solved = {route.wire_id: route for route in routes}
    removed_ids = set(state.routes) - set(solved)
    for child in _wire_graphics(group, removed_ids):
        child.deleteMe()
    for route_id in removed_ids:
        state.routes.pop(route_id, None)
    old_groups = {item.wire_group_id: item for item in state.definition.wire_groups}
    new_groups = {item.wire_group_id: item for item in definition.wire_groups}
    route_group_ids = {leg.route_id: leg.wire_group_id for leg in legs}
    warnings: list[str] = solve_notices
    for route in routes:
        group_id = route_group_ids[route.wire_id]
        old_group = old_groups.get(group_id)
        new_group = new_groups[group_id]
        color_changed = old_group is None or (
            state.definition.wire_group_materials(old_group).main_color
            != definition.wire_group_materials(new_group).main_color
        )
        if state.routes.get(route.wire_id) == route and not color_changed:
            continue
        previous = _wire_graphics(group, {route.wire_id})
        color_index = state.color_indices.setdefault(
            route.wire_id, max(state.color_indices.values(), default=-1) + 1
        )
        try:
            _add_route_graphics(
                group,
                route,
                color_index,
                definition.wire_group_materials(new_group).main_color,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            for child in _wire_graphics(group, {route.wire_id}):
                child.deleteMe()
            state.routes.pop(route.wire_id, None)
            warnings.append(f"Could not draw {route.wire_number}: {error}")
            continue
        for child in previous:
            child.deleteMe()
        state.routes[route.wire_id] = route
    group_connections = {
        wire_group.wire_group_id: wire_group.connection_ids for wire_group in definition.wire_groups
    }
    drawn_leg_ids = set(state.routes)
    state.definition = definition
    state.clearance_mm = definition.minimum_clearance_mm
    state.route_group_ids = {
        leg.route_id: leg.wire_group_id for leg in legs if leg.route_id in drawn_leg_ids
    }
    state.route_connection_ids = {
        leg.route_id: group_connections[leg.wire_group_id]
        for leg in legs
        if leg.route_id in drawn_leg_ids
    }
    state.route_pathway_ids = {
        leg.route_id: leg.pathway_ids for leg in legs if leg.route_id in drawn_leg_ids
    }
    state.route_control_ids = {
        leg.route_id: tuple(step.control_id for step in leg.control_steps)
        for leg in legs
        if leg.route_id in drawn_leg_ids
    }
    _remember_preview(group.id, state)
    return " ".join(warnings)


def highlight_route_preview(design: adsk.fusion.Design, group_id: Optional[UUID]) -> int:
    """
    Emphasize one existing wire-group network and restore all other preview widths.

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
    Emphasize complete wire-group preview networks matching the supplied members.
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
            wire_group = adsk.fusion.CustomGraphicsGroup.cast(group.item(child_index))
            if wire_group is None:
                continue
            selected = wire_group.id in selected_ids
            for line_index in range(wire_group.count):
                lines = adsk.fusion.CustomGraphicsLines.cast(wire_group.item(line_index))
                if lines is not None:
                    lines.weight = 5.0 if selected else 1.0
                    if selected:
                        selected_count += 1
    return selected_count


def _adjustment_notice(adjustment: TransitionAdjustment) -> str:
    """
    Format a dynamic transition correction for the palette event console.
    """
    return (
        f"Wire {adjustment.wire_number}: dynamically adjusted transitions between profiles "
        f"{adjustment.start_profile} and {adjustment.end_profile} from "
        f"{adjustment.required_mm:.3f} mm to {adjustment.applied_mm:.3f} mm; "
        f"the {adjustment.minimum_bend_radius_mm:.3f} mm sweep radius is preserved."
    )


def _collision_notice(collision: RouteCollision) -> str:
    """
    Format one best-effort residual member collision for the event console.
    """
    return (
        f"{collision.left_label} and {collision.right_label} remain "
        f"{collision.clearance_shortfall_mm:.3f} mm inside the requested separation; "
        "generated geometry uses the best deterministic route found."
    )


def _routing_frame(
    design: adsk.fusion.Design,
    control: Optional[ControlStructure],
    control_id: UUID,
) -> Union[GateFrame, RefineFrame]:
    """
    Build a constrained gate or unconstrained refine routing frame.
    """
    if control is None:
        raise RuntimeError(f"Routing control is missing: {control_id}")
    if control.kind is ControlKind.REFINE:
        geometry = control.refine_geometry
        if geometry is None:
            raise RuntimeError(f"{control.name} has no saved refine geometry.")
        return RefineFrame(
            refine_id=control.control_id,
            name=control.name,
            origin=Vector3(*geometry.origin_mm),
            u_direction=Vector3(*geometry.u_direction),
            v_direction=Vector3(*geometry.v_direction),
        )
    return _gate_frame(design, control, control_id)


def _gate_frame(
    design: adsk.fusion.Design,
    control: Optional[ControlStructure],
    control_id: UUID,
) -> GateFrame:
    """
    Build a millimeter-scale circular aperture frame from one physical control.

    Connection-owned end profiles are resolved separately as centroid/normal
    frames. Their position and orientation guide fairing and the resulting sweep,
    but they are not apertures against which the wire bundle is fit-tested.
    """
    if control is None:
        raise RuntimeError(f"Routing control is missing: {control_id}")
    if control.kind is not ControlKind.ROUTING_GATE:
        raise RuntimeError(
            f"{control.name} is not a routing gate; profile-gate preview is not supported yet."
        )
    profile = _resolve_profile(design, control.entity_token)
    profile_loops = profile.profileLoops
    if profile_loops.count != 1:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    profile_curves = profile_loops.item(0).profileCurves
    if profile_curves.count != 1:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    profile_curve = profile_curves.item(0)
    circle = adsk.fusion.SketchCircle.cast(
        profile_curve.sketchEntity if profile_curve is not None else None
    )
    if circle is None:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    sketch = profile.parentSketch
    center = sketch.sketchToModelSpace(circle.geometry.center)
    return GateFrame(
        gate_id=control.control_id,
        name=control.name,
        origin=_point_to_mm(center),
        u_direction=_vector(sketch.xDirection),
        v_direction=_vector(sketch.yDirection),
        usable_radius_mm=circle.geometry.radius * 10.0,
    )


def _profile_frame(design: adsk.fusion.Design, entity_token: str) -> _ProfileFrame:
    """
    Return a millimeter-scale model centroid and dimensionless unit plane normal.
    """
    profile = _resolve_profile(design, entity_token)
    area_properties = profile.areaProperties()
    if area_properties is None:
        raise RuntimeError("Fusion could not calculate connection-profile area properties.")
    sketch = profile.parentSketch
    u_direction = _vector(sketch.xDirection)
    v_direction = _vector(sketch.yDirection)
    normal = unit(cross(u_direction, v_direction))
    usable_radius_mm: Optional[float] = None
    origin = sketch.sketchToModelSpace(area_properties.centroid)
    loops = profile.profileLoops
    if loops.count == 1:
        curves = loops.item(0).profileCurves
        if curves.count == 1:
            profile_curve = curves.item(0)
            circle = adsk.fusion.SketchCircle.cast(
                profile_curve.sketchEntity if profile_curve is not None else None
            )
            if circle is not None:
                origin = sketch.sketchToModelSpace(circle.geometry.center)
                usable_radius_mm = circle.geometry.radius * 10.0
    return _ProfileFrame(
        _point_to_mm(origin),
        normal,
        u_direction,
        v_direction,
        usable_radius_mm,
    )


def _resolve_profile(design: adsk.fusion.Design, entity_token: str) -> adsk.fusion.Profile:
    """
    Resolve one stored token to a Fusion sketch profile.
    """
    entities = design.findEntityByToken(entity_token)
    profile = adsk.fusion.Profile.cast(entities[0] if entities else None)
    if profile is None:
        raise RuntimeError("A route profile is missing or no longer resolves in Fusion.")
    return profile


def _add_route_graphics(
    preview_group: adsk.fusion.CustomGraphicsGroup,
    route: RoutePreview,
    color_index: int,
    wire_color: Optional[WireColor] = None,
) -> None:
    """
    Add one selectable colored line strip to a preview group.
    """
    wire_group = preview_group.addGroup()
    if wire_group is None:
        raise RuntimeError(f"Fusion did not create graphics for wire {route.wire_number}.")
    wire_group.id = str(route.wire_id)
    wire_group.name = f"Wire {route.wire_number} Preview"
    sampled_points = sample_centerline(route)
    coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
        [
            coordinate / 10.0
            for point in sampled_points
            for coordinate in (point.x, point.y, point.z)
        ]
    )
    if coordinates is None:
        raise RuntimeError(f"Fusion did not create coordinates for wire {route.wire_number}.")
    lines = wire_group.addLines(coordinates, [], True)
    if lines is None:
        raise RuntimeError(f"Fusion did not draw wire {route.wire_number}.")
    lines.name = f"Wire {route.wire_number} Centerline"
    lines.weight = 1.0
    red, green, blue = (
        (wire_color.red, wire_color.green, wire_color.blue)
        if wire_color is not None
        else _PREVIEW_COLORS[color_index % len(_PREVIEW_COLORS)]
    )
    color = adsk.core.Color.create(red, green, blue, 255)
    color_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(color)
    if color_effect is None:
        raise RuntimeError(f"Fusion did not create a color for wire {route.wire_number}.")
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


def solve_wire_group_centerlines(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[tuple[RoutePreview, ...], tuple[WireGroupRouteLeg, ...]]:
    """
    Resolve grouped-wire legs without changing transient preview state.

    The returned legs and routes share stable route identities and definition
    order so persistent generation can consume exactly the geometry previewed
    by the user.
    """
    return _solve_wire_group_routes(design, definition, notices)
