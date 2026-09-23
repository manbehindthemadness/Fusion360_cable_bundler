"""
Build persistent cable-group solids from the exact curves used by previews.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Optional, Protocol
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import (
    CableGroupDefinition,
    CableMaterialSettings,
    HarnessDefinition,
    PullbackMode,
    validate_harness,
)
from ..routing import (
    RoutePreview,
)
from .cable_solid_parts.constants import (
    FINALIZED_OUTPUT_MODE,
    GENERATED_CABLE_GROUP_ATTRIBUTE,
    GENERATED_OUTPUT_MODE_KEY,
    GENERATED_STRIPE_GROUP_ID,
    SOLID_OUTPUT_MODE,
)
from .cable_solid_parts.materials import cable_appearance, material_metadata
from .cable_solid_parts.metadata import (
    connection_branches_from_metadata,
    group_geometry_routes_from_metadata,
    group_routes_from_metadata,
    route_in_component_space,
    world_to_harness,
)
from .cable_solid_parts.solid_builder import build_cable_group_solid
from .cable_solid_parts.stripes import (
    build_continuous_segment_stripes,
    clear_all_stripe_graphics,
    clear_group_stripe_graphics,
    generated_stripe_graphics_groups,
    replace_group_stripe_bodies,
    replace_group_stripe_graphics,
)
from .cable_solid_parts.sweep_geometry import (
    prepare_group_sweep_segments,
    split_route_endpoint_pullbacks,
    split_route_for_pullback,
)
from .harness_gateway import ATTRIBUTE_GROUP
from .route_preview import solve_cable_group_centerlines

_build_continuous_segment_stripes = build_continuous_segment_stripes
_prepare_group_sweep_segments = prepare_group_sweep_segments
_split_route_for_pullback = split_route_for_pullback
_split_route_endpoint_pullbacks = split_route_endpoint_pullbacks
_replace_group_stripe_graphics = replace_group_stripe_graphics
_replace_group_stripe_bodies = replace_group_stripe_bodies

__all__ = [
    "GENERATED_STRIPE_GROUP_ID",
    "_build_continuous_segment_stripes",
    "_prepare_group_sweep_segments",
    "_split_route_for_pullback",
    "_split_route_endpoint_pullbacks",
    "_replace_group_stripe_graphics",
    "_replace_group_stripe_bodies",
    "CableSolidVisibilityState",
    "apply_cable_group_materials",
    "clear_cable_solids",
    "generate_cable_group_solids",
    "generated_cable_group_output_mode",
    "generated_cable_group_bodies",
    "generated_cable_group_occurrences",
    "hide_generated_cable_group_solids",
    "refresh_changed_generated_cable_groups",
    "refresh_generated_cable_groups_for_connection",
    "restore_cable_group_stripe_graphics",
    "restore_generated_cable_group_visibility",
]


class _VisibilityOccurrence(Protocol):
    """
    Expose the Fusion occurrence state needed for temporary solid hiding.
    """

    isLightBulbOn: bool
    isValid: bool


class _VisibilityGraphicsGroup(Protocol):
    """
    Expose the Fusion graphics state needed for temporary stripe hiding.
    """

    isVisible: bool
    isValid: bool


@dataclass(frozen=True)
class CableSolidVisibilityState:
    """
    Capture generated body and stripe visibility for one harness.
    """

    occurrences: tuple[tuple[_VisibilityOccurrence, bool], ...]
    stripe_groups: tuple[tuple[_VisibilityGraphicsGroup, bool], ...]


def _leg_materials(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    leg: CableGroupRouteLeg,
) -> CableMaterialSettings:
    """
    Resolve group materials or one connection branch's visual overrides.
    """
    attachment_id = getattr(leg, "attachment_id", None)
    connection_id = getattr(leg, "start_connection_id", None)
    if not isinstance(attachment_id, UUID) or not isinstance(connection_id, UUID):
        return definition.cable_group_materials(group)
    return definition.cable_end_attachment_materials(
        group,
        connection_id,
        attachment_id,
    )


def _attachment_materials(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    attachment_id: Optional[UUID],
) -> CableMaterialSettings:
    """
    Resolve saved branch materials, falling back for legacy generated metadata.
    """
    if attachment_id is None:
        return definition.cable_group_materials(group)
    for connection in definition.connections:
        if connection.connection_id not in group.connection_ids:
            continue
        if any(item.attachment_id == attachment_id for item in connection.attachments):
            return definition.cable_end_attachment_materials(
                group, connection.connection_id, attachment_id
            )
    return definition.cable_group_materials(group)


def _attachment_pullback_mm(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    attachment_id: Optional[UUID],
    diameter_mm: float,
) -> float:
    """
    Resolve one leaf connection's requested pullback distance in millimeters.

    Intermediate connection nodes keep their complete insulation sweep. Percent
    values use the resolved diameter of the leaf connection branch.
    """
    if attachment_id is None:
        return 0.0
    for connection in definition.connections:
        if connection.connection_id not in group.connection_ids:
            continue
        attachment = next(
            (item for item in connection.attachments if item.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            continue
        if connection.attachment_children(attachment_id):
            return 0.0
        settings = definition.cable_end_attachment_materials(
            group,
            connection.connection_id,
            attachment_id,
        ).pullback
        if settings.mode is PullbackMode.DISTANCE:
            return settings.value
        return diameter_mm * settings.value / 100.0
    return 0.0


def _attachment_conductor_diameter_mm(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    attachment_id: Optional[UUID],
    fallback_diameter_mm: float,
) -> float:
    """
    Resolve conductor sizing within the attachment's owning cable group.
    """
    if attachment_id is None:
        return fallback_diameter_mm * 0.75
    for connection in definition.connections:
        if connection.connection_id not in group.connection_ids:
            continue
        if any(item.attachment_id == attachment_id for item in connection.attachments):
            return definition.cable_end_attachment_conductor_diameter(
                group,
                connection.connection_id,
                attachment_id,
            )
    return fallback_diameter_mm * 0.75


def _leg_pullback_mm(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    leg: CableGroupRouteLeg,
) -> float:
    """
    Resolve pullback only for a routed leaf connection branch.
    """
    if not getattr(leg, "is_connection_branch", False):
        return 0.0
    diameter_mm = getattr(leg, "diameter_mm", None) or group.diameter_mm
    return _attachment_pullback_mm(
        definition,
        group,
        getattr(leg, "attachment_id", None),
        diameter_mm,
    )


def _connection_endpoint_pullback(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    connection_id: Optional[UUID],
) -> tuple[float, Optional[CableMaterialSettings], Optional[UUID], float]:
    """
    Resolve a single connected root node when it is also the chain leaf.
    """
    if connection_id is None:
        return 0.0, None, None, 0.0
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        return 0.0, None, None, 0.0
    roots = connection.attachment_children(None)
    if len(roots) != 1:
        return 0.0, None, None, 0.0
    attachment = roots[0]
    if not attachment.has_target or connection.attachment_children(attachment.attachment_id):
        return 0.0, None, None, 0.0
    materials = definition.cable_end_attachment_materials(
        group,
        connection_id,
        attachment.attachment_id,
    )
    return (
        _attachment_pullback_mm(
            definition,
            group,
            attachment.attachment_id,
            group.diameter_mm,
        ),
        materials,
        attachment.attachment_id,
        definition.cable_end_attachment_conductor_diameter(
            group,
            connection_id,
            attachment.attachment_id,
        ),
    )


def _leg_endpoint_pullbacks(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    leg: CableGroupRouteLeg,
) -> tuple[
    tuple[float, Optional[CableMaterialSettings], Optional[UUID], float],
    tuple[float, Optional[CableMaterialSettings], Optional[UUID], float],
]:
    """
    Resolve target-facing pullback options for both ends of one routed leg.
    """
    if getattr(leg, "is_connection_branch", False):
        attachment_id = getattr(leg, "attachment_id", None)
        distance_mm = _leg_pullback_mm(definition, group, leg)
        materials = (
            _leg_materials(definition, group, leg)
            if distance_mm > 0.0 and attachment_id is not None
            else None
        )
        connection_id = getattr(leg, "start_connection_id", None)
        conductor_diameter_mm = (
            definition.cable_end_attachment_conductor_diameter(
                group,
                connection_id,
                attachment_id,
            )
            if isinstance(connection_id, UUID) and isinstance(attachment_id, UUID)
            else 0.0
        )
        return (
            distance_mm,
            materials,
            attachment_id,
            conductor_diameter_mm,
        ), (0.0, None, None, 0.0)
    return (
        _connection_endpoint_pullback(
            definition,
            group,
            getattr(leg, "start_connection_id", None),
        ),
        _connection_endpoint_pullback(
            definition,
            group,
            getattr(leg, "end_connection_id", None),
        ),
    )


def _route_build_options(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    legs: tuple[CableGroupRouteLeg, ...],
) -> dict[str, object]:
    """
    Build optional per-route diameter, material, identity, and pullback inputs.
    """
    branch_indices = frozenset(
        index for index, leg in enumerate(legs) if getattr(leg, "is_connection_branch", False)
    )
    options: dict[str, object] = {}
    if branch_indices:
        attachment_ids = tuple(getattr(leg, "attachment_id", None) for leg in legs)
        options.update(
            {
                "route_diameters_mm": tuple(
                    getattr(leg, "diameter_mm", None) or group.diameter_mm for leg in legs
                ),
                "connection_branch_indices": branch_indices,
            }
        )
        if any(attachment_ids):
            options.update(
                {
                    "route_materials": tuple(
                        _leg_materials(definition, group, leg) for leg in legs
                    ),
                    "route_attachment_ids": attachment_ids,
                }
            )
    endpoint_options = tuple(_leg_endpoint_pullbacks(definition, group, leg) for leg in legs)
    if any(start[0] > 0.0 or end[0] > 0.0 for start, end in endpoint_options):
        options.update(
            {
                "route_pullbacks_mm": tuple(start[0] for start, _end in endpoint_options),
                "route_end_pullbacks_mm": tuple(end[0] for _start, end in endpoint_options),
                "route_pullback_materials": tuple(start[1] for start, _end in endpoint_options),
                "route_end_pullback_materials": tuple(end[1] for _start, end in endpoint_options),
                "route_pullback_attachment_ids": tuple(
                    start[2] for start, _end in endpoint_options
                ),
                "route_end_pullback_attachment_ids": tuple(
                    end[2] for _start, end in endpoint_options
                ),
                "route_pullback_diameters_mm": tuple(start[3] for start, _end in endpoint_options),
                "route_end_pullback_diameters_mm": tuple(
                    end[3] for _start, end in endpoint_options
                ),
            }
        )
    return options


def generate_cable_group_solids(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    replace_existing: bool = False,
    notices: Optional[list[str]] = None,
    output_mode: str = SOLID_OUTPUT_MODE,
) -> int:
    """
    Build one multi-body component per cable group before replacing managed output.
    """
    issues = validate_harness(definition)
    if issues:
        raise ValueError(
            "Cannot generate cable groups: " + "; ".join(issue.message for issue in issues)
        )
    if not definition.cable_groups:
        raise ValueError("Create at least one cable group before generating solids.")
    previous = generated_cable_group_occurrences(harness)
    if previous and not replace_existing:
        raise ValueError(
            "Generated solids already exist; confirm rebuilding before replacing them."
        )
    routes, legs, routes_by_id = _solve_complete_group_routes(design, definition, notices)
    legs_by_group: dict[UUID, list[tuple[CableGroupRouteLeg, RoutePreview]]] = {}
    for leg in legs:
        legs_by_group.setdefault(leg.cable_group_id, []).append((leg, routes_by_id[leg.route_id]))
    local_transform = world_to_harness(design, harness)
    created: list[adsk.fusion.Occurrence] = []
    try:
        for group_index, group in enumerate(definition.cable_groups):
            group_legs = legs_by_group.get(group.cable_group_id, [])
            if not group_legs:
                raise ValueError(f"Cable Group {group_index + 1} has no route legs.")
            occurrence = harness.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if occurrence is None:
                raise RuntimeError(
                    f"Fusion could not create a component for Cable Group {group_index + 1}."
                )
            created.append(occurrence)
            try:
                route_options = _route_build_options(
                    definition,
                    group,
                    tuple(leg for leg, _route in group_legs),
                )
                build_cable_group_solid(
                    occurrence.component,
                    harness,
                    group,
                    group_index,
                    tuple(route for _leg, route in group_legs),
                    local_transform,
                    definition.harness_id,
                    definition.cable_group_materials(group),
                    design,
                    output_mode,
                    **route_options,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Cable Group {group_index + 1} could not be generated: {error}"
                ) from error
        for occurrence in previous:
            if not occurrence.deleteMe():
                raise RuntimeError("Fusion could not remove old generated cable-group geometry.")
    except Exception as error:
        for group in definition.cable_groups:
            clear_group_stripe_graphics(harness, group.cable_group_id)
        for occurrence in reversed(created):
            if occurrence.isValid and not occurrence.deleteMe():
                raise RuntimeError(
                    "Fusion could not clean incomplete grouped-cable geometry; undo this command."
                ) from error
        if previous:
            restore_cable_group_stripe_graphics(harness, definition)
        raise
    return len(created)


def refresh_generated_cable_groups_for_connection(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    connection_id: UUID,
    notices: Optional[list[str]] = None,
) -> int:
    """
    Rebuild only generated cable-group components that contain one edited end.

    Existing output mode and visibility are preserved. If no generated output
    exists for the affected groups, this is a harmless no-op.
    """
    affected_ids = {
        group.cable_group_id
        for group in definition.cable_groups
        if connection_id in group.connection_ids
    }
    return _refresh_generated_cable_groups(
        design,
        harness,
        definition,
        frozenset(affected_ids),
        notices,
    )


def refresh_changed_generated_cable_groups(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> int:
    """
    Rebuild generated groups whose stored curves differ from current guide geometry.

    Stored component-local curves make this comparison independent of harness
    placement. Groups with no generated occurrence remain untouched.
    """
    occurrences_by_id = _generated_cable_group_metadata_by_id(harness)
    if not occurrences_by_id:
        return 0

    routes, legs, routes_by_id = _solve_complete_group_routes(design, definition, notices)
    local_transform = world_to_harness(design, harness)
    current_by_group: dict[UUID, dict[UUID, RoutePreview]] = {}
    for leg in legs:
        route = route_in_component_space(routes_by_id[leg.route_id], local_transform)
        current_by_group.setdefault(leg.cable_group_id, {})[route.cable_id] = route

    changed_ids: set[UUID] = set()
    for group_id, (_occurrence, metadata) in occurrences_by_id.items():
        current = current_by_group.get(group_id)
        if current is None:
            continue
        stored_curves = {
            route.cable_id: route.curves for route in group_geometry_routes_from_metadata(metadata)
        }
        current_curves = {route_id: route.curves for route_id, route in current.items()}
        if stored_curves != current_curves:
            changed_ids.add(group_id)
    return _refresh_generated_cable_groups(
        design,
        harness,
        definition,
        frozenset(changed_ids),
    )


def _generated_cable_group_metadata_by_id(
    harness: adsk.fusion.Component,
) -> dict[UUID, tuple[adsk.fusion.Occurrence, dict[str, object]]]:
    """
    Decode generated group identity and route metadata exactly once per component.
    """
    occurrences_by_id: dict[UUID, tuple[adsk.fusion.Occurrence, dict[str, object]]] = {}
    for occurrence in generated_cable_group_occurrences(harness):
        attribute = occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP,
            GENERATED_CABLE_GROUP_ATTRIBUTE,
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        if group_id in occurrences_by_id:
            raise RuntimeError("A cable group has duplicate generated geometry.")
        occurrences_by_id[group_id] = (occurrence, metadata)
    return occurrences_by_id


def _solve_complete_group_routes(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]],
) -> tuple[tuple[RoutePreview, ...], tuple[CableGroupRouteLeg, ...], dict[UUID, RoutePreview]]:
    """
    Solve every route and reject incomplete generated-output geometry.
    """
    routes, legs = solve_cable_group_centerlines(design, definition, notices)
    routes_by_id = {route.cable_id: route for route in routes}
    if not routes or set(routes_by_id) != {leg.route_id for leg in legs}:
        raise ValueError("Every cable group must have complete route geometry before generation.")
    return routes, legs, routes_by_id


def _refresh_generated_cable_groups(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    affected_ids: frozenset[UUID],
    notices: Optional[list[str]] = None,
) -> int:
    """
    Rebuild the selected generated cable groups while preserving presentation.
    """
    if not affected_ids:
        return 0
    previous_by_id = {
        group_id: occurrence
        for group_id, (occurrence, _metadata) in _generated_cable_group_metadata_by_id(
            harness
        ).items()
        if group_id in affected_ids
    }
    if not previous_by_id:
        return 0

    routes, legs, routes_by_id = _solve_complete_group_routes(design, definition, notices)
    legs_by_group: dict[UUID, list[RoutePreview]] = {}
    for leg in legs:
        legs_by_group.setdefault(leg.cable_group_id, []).append(routes_by_id[leg.route_id])
    local_transform = world_to_harness(design, harness)
    created: list[adsk.fusion.Occurrence] = []
    try:
        for group_index, group in enumerate(definition.cable_groups):
            if group.cable_group_id not in previous_by_id:
                continue
            previous = previous_by_id[group.cable_group_id]
            group_routes = tuple(legs_by_group.get(group.cable_group_id, ()))
            if not group_routes:
                raise ValueError(f"Cable Group {group_index + 1} has no route legs.")
            occurrence = harness.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if occurrence is None:
                raise RuntimeError(
                    f"Fusion could not update Cable Group {group_index + 1} geometry."
                )
            created.append(occurrence)
            group_legs = tuple(leg for leg in legs if leg.cable_group_id == group.cable_group_id)
            route_options = _route_build_options(definition, group, group_legs)
            build_cable_group_solid(
                occurrence.component,
                harness,
                group,
                group_index,
                group_routes,
                local_transform,
                definition.harness_id,
                definition.cable_group_materials(group),
                design,
                generated_cable_group_output_mode(previous),
                is_visible=previous.isLightBulbOn,
                **route_options,
            )
            occurrence.isLightBulbOn = previous.isLightBulbOn
        for occurrence in previous_by_id.values():
            if not occurrence.deleteMe():
                raise RuntimeError("Fusion could not replace generated cable-group geometry.")
    except Exception as error:
        for group_id in previous_by_id:
            clear_group_stripe_graphics(harness, group_id)
        for occurrence in reversed(created):
            if occurrence.isValid and not occurrence.deleteMe():
                raise RuntimeError(
                    "Fusion could not clean incomplete cable geometry; undo this command."
                ) from error
        restore_cable_group_stripe_graphics(harness, definition)
        raise
    return len(created)


def generated_cable_group_occurrences(
    harness: adsk.fusion.Component,
) -> tuple[adsk.fusion.Occurrence, ...]:
    """
    Find direct children explicitly marked as generated cable-group output.
    """
    return tuple(
        occurrence
        for occurrence in harness.occurrences
        if occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        is not None
    )


def generated_cable_group_output_mode(occurrence: adsk.fusion.Occurrence) -> str:
    """
    Read the persistent render mode, treating legacy generated output as solids.
    """
    attribute = occurrence.component.attributes.itemByName(
        ATTRIBUTE_GROUP,
        GENERATED_CABLE_GROUP_ATTRIBUTE,
    )
    if attribute is None:
        return SOLID_OUTPUT_MODE
    try:
        metadata = json.loads(attribute.value)
    except (TypeError, json.JSONDecodeError):
        return SOLID_OUTPUT_MODE
    mode = metadata.get(GENERATED_OUTPUT_MODE_KEY)
    return FINALIZED_OUTPUT_MODE if mode == FINALIZED_OUTPUT_MODE else SOLID_OUTPUT_MODE


def hide_generated_cable_group_solids(
    harness: adsk.fusion.Component,
) -> CableSolidVisibilityState:
    """
    Hide managed cable-group occurrences and capture their exact prior visibility.

    If Fusion rejects a visibility update, every occurrence changed so far is
    restored before the error is propagated.
    """
    occurrence_visibility = tuple(
        (occurrence, occurrence.isLightBulbOn)
        for occurrence in generated_cable_group_occurrences(harness)
    )
    stripe_visibility = tuple(
        (group, group.isVisible) for group in generated_stripe_graphics_groups(harness)
    )
    visibility = CableSolidVisibilityState(occurrence_visibility, stripe_visibility)
    try:
        for occurrence, was_visible in visibility.occurrences:
            if was_visible:
                occurrence.isLightBulbOn = False
        for group, was_visible in visibility.stripe_groups:
            if was_visible:
                group.isVisible = False
    except (AttributeError, RuntimeError) as error:
        restore_generated_cable_group_visibility(visibility)
        raise RuntimeError("Fusion could not hide generated cable solids.") from error
    return visibility


def restore_generated_cable_group_visibility(
    visibility: CableSolidVisibilityState,
) -> None:
    """
    Restore managed cable-group occurrences to their captured light-bulb states.
    """
    for occurrence, was_visible in visibility.occurrences:
        if occurrence.isValid:
            occurrence.isLightBulbOn = was_visible
    for group, was_visible in visibility.stripe_groups:
        if group.isValid:
            group.isVisible = was_visible


def generated_cable_group_bodies(
    root: adsk.fusion.Component,
    harness: adsk.fusion.Component,
    cable_group_ids: tuple[UUID, ...],
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Resolve root-context bodies for persistent cable-group identities.

    Malformed metadata is ignored so palette hover remains a harmless,
    best-effort operation.
    """
    selected_ids = {str(group_id) for group_id in cable_group_ids}
    bodies: list[adsk.fusion.BRepBody] = []
    for occurrence in generated_cable_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            group_id = json.loads(attribute.value).get("cable_group_id")
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
        if group_id not in selected_ids:
            continue
        bodies.extend(_root_context_bodies(root, component))
    return tuple(bodies)


def _root_context_bodies(
    root: adsk.fusion.Component,
    component: adsk.fusion.Component,
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Return every body proxy for a generated component in root assembly context.
    """
    bodies: list[adsk.fusion.BRepBody] = []
    root_occurrences = root.allOccurrencesByComponent(component)
    for occurrence_index in range(root_occurrences.count):
        root_occurrence = root_occurrences.item(occurrence_index)
        if root_occurrence is None:
            continue
        for body_index in range(root_occurrence.bRepBodies.count):
            body = root_occurrence.bRepBodies.item(body_index)
            if body is not None:
                bodies.append(body)
    return tuple(bodies)


def clear_cable_solids(harness: adsk.fusion.Component) -> int:
    """
    Delete direct child components marked as generated cable output.

    Callers should invoke this inside a native Fusion command transaction so a
    failed deletion rolls the complete operation back and Undo can restore it.
    """
    occurrences = generated_cable_group_occurrences(harness)
    for occurrence in occurrences:
        if not occurrence.deleteMe():
            raise RuntimeError("Fusion could not delete a generated cable component.")
    clear_all_stripe_graphics(harness)
    return len(occurrences)


def _main_pullbacks_from_metadata(
    metadata: dict[str, object],
) -> tuple[tuple[UUID, float, UUID, str, float, float], ...]:
    """
    Decode finalized main-route pullback body ownership in body order.
    """
    encoded = metadata.get("main_pullbacks", [])
    if not isinstance(encoded, list):
        raise RuntimeError("Generated cable-group pullback metadata is malformed.")
    decoded: list[tuple[UUID, float, UUID, str, float, float]] = []
    for item in encoded:
        if not isinstance(item, dict):
            raise RuntimeError("Generated cable-group pullback metadata is malformed.")
        raw_attachment_id = item.get("attachment_id")
        requested_mm = item.get("requested_mm")
        raw_route_id = item.get("route_id")
        boundary = item.get("boundary")
        length_mm = item.get("length_mm")
        diameter_mm = item.get("diameter_mm", 0.0)
        if (
            not isinstance(raw_attachment_id, str)
            or not isinstance(raw_route_id, str)
            or boundary not in ("start", "end")
            or isinstance(requested_mm, bool)
            or not isinstance(requested_mm, (int, float))
            or not math.isfinite(requested_mm)
            or requested_mm < 0.0
            or isinstance(length_mm, bool)
            or not isinstance(length_mm, (int, float))
            or not math.isfinite(length_mm)
            or length_mm < 0.0
            or isinstance(diameter_mm, bool)
            or not isinstance(diameter_mm, (int, float))
            or not math.isfinite(diameter_mm)
            or ("diameter_mm" in item and diameter_mm <= 0.0)
        ):
            raise RuntimeError("Generated cable-group pullback metadata is malformed.")
        try:
            attachment_id = UUID(raw_attachment_id)
            route_id = UUID(raw_route_id)
        except ValueError as error:
            raise RuntimeError("Generated cable-group pullback metadata is malformed.") from error
        decoded.append(
            (
                attachment_id,
                float(requested_mm),
                route_id,
                boundary,
                float(length_mm),
                float(diameter_mm),
            )
        )
    return tuple(decoded)


def _expected_main_pullbacks(
    definition: HarnessDefinition,
    group: CableGroupDefinition,
) -> dict[UUID, tuple[float, float]]:
    """
    Resolve current single-node leaf pullbacks at the group's main-route ends.
    """
    expected: dict[UUID, tuple[float, float]] = {}
    for connection_id in group.connection_ids:
        distance_mm, _materials, attachment_id, conductor_diameter_mm = (
            _connection_endpoint_pullback(
                definition,
                group,
                connection_id,
            )
        )
        if distance_mm > 0.0 and attachment_id is not None:
            expected[attachment_id] = (distance_mm, conductor_diameter_mm)
    return expected


# noinspection DuplicatedCode
def apply_cable_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply resolved materials to existing generated cable-group components.

    Stored component-local leg curves are reused to replace stripe presentation.
    Finalized groups are rebuilt only when a leaf pullback length or leaf status
    changed, because those material settings also define body boundaries.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    occurrences = generated_cable_group_occurrences(harness)
    pullback_changed_ids: set[UUID] = set()
    for occurrence in occurrences:
        if generated_cable_group_output_mode(occurrence) != FINALIZED_OUTPUT_MODE:
            continue
        attribute = occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        stored_main_pullbacks = {
            attachment_id: (requested_mm, diameter_mm)
            for attachment_id, requested_mm, _route_id, _boundary, _length_mm, diameter_mm in (
                _main_pullbacks_from_metadata(metadata)
            )
        }
        expected_main_pullbacks = _expected_main_pullbacks(definition, group)
        if stored_main_pullbacks.keys() != expected_main_pullbacks.keys() or any(
            not math.isclose(
                stored_main_pullbacks[attachment_id][0],
                requested[0],
                abs_tol=1e-6,
            )
            or not math.isclose(
                stored_main_pullbacks[attachment_id][1],
                requested[1],
                abs_tol=1e-6,
            )
            for attachment_id, requested in expected_main_pullbacks.items()
        ):
            pullback_changed_ids.add(group_id)
            continue
        for branch in connection_branches_from_metadata(metadata):
            requested_mm = _attachment_pullback_mm(
                definition,
                group,
                branch.attachment_id,
                branch.diameter_mm,
            )
            if not math.isclose(
                requested_mm,
                branch.pullback_requested_mm,
                abs_tol=1e-6,
            ) or not math.isclose(
                _attachment_conductor_diameter_mm(
                    definition,
                    group,
                    branch.attachment_id,
                    branch.diameter_mm,
                ),
                branch.pullback_diameter_mm,
                abs_tol=1e-6,
            ):
                pullback_changed_ids.add(group_id)
                break
    if pullback_changed_ids:
        _refresh_generated_cable_groups(
            design,
            harness,
            definition,
            frozenset(pullback_changed_ids),
        )
        occurrences = generated_cable_group_occurrences(harness)
    applied = 0
    for occurrence in occurrences:
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        materials = definition.cable_group_materials(group)
        branches = connection_branches_from_metadata(metadata)
        main_pullbacks = _main_pullbacks_from_metadata(metadata)
        branch_materials = tuple(
            _attachment_materials(definition, group, branch.attachment_id) for branch in branches
        )
        bodies = component.bRepBodies
        if bodies.count == 0:
            raise RuntimeError(f"Generated Cable Group {group_id} has no bodies to color.")
        branch_body_count = sum(
            branch.insulation_body_count + branch.pullback_body_count for branch in branches
        )
        raw_main_insulation_body_count = metadata.get(
            "main_insulation_body_count",
            bodies.count - branch_body_count,
        )
        if (
            isinstance(raw_main_insulation_body_count, bool)
            or not isinstance(raw_main_insulation_body_count, int)
            or raw_main_insulation_body_count < 0
        ):
            raise RuntimeError(f"Generated Cable Group {group_id} has invalid branch bodies.")
        main_insulation_body_count = raw_main_insulation_body_count
        if main_insulation_body_count + len(main_pullbacks) + branch_body_count != bodies.count:
            raise RuntimeError(f"Generated Cable Group {group_id} has invalid branch bodies.")
        appearance = cable_appearance(design, materials.main_color, materials.appearance)
        for body_index in range(main_insulation_body_count):
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = appearance
        body_index = main_insulation_body_count
        for (
            attachment_id,
            _requested_mm,
            _route_id,
            _boundary,
            _length_mm,
            _diameter_mm,
        ) in main_pullbacks:
            pullback_materials = _attachment_materials(
                definition,
                group,
                attachment_id,
            ).pullback
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = cable_appearance(
                    design,
                    pullback_materials.color,
                    pullback_materials.appearance,
                )
            body_index += 1
        for branch, branch_settings in zip(branches, branch_materials):
            if branch.insulation_body_count:
                body = bodies.item(body_index)
                if body is not None:
                    body.appearance = cable_appearance(
                        design, branch_settings.main_color, branch_settings.appearance
                    )
                body_index += 1
            if branch.pullback_body_count:
                body = bodies.item(body_index)
                if body is not None:
                    body.appearance = cable_appearance(
                        design,
                        branch_settings.pullback.color,
                        branch_settings.pullback.appearance,
                    )
                body_index += 1
        routes = group_routes_from_metadata(metadata)
        if not routes and materials.stripes:
            raise RuntimeError(
                "Generated cable-group metadata has no routes for applying stripe patterns."
            )
        clear_group_stripe_graphics(component, group_id, include_legacy=True)
        clear_group_stripe_graphics(harness, group_id)
        if generated_cable_group_output_mode(occurrence) == FINALIZED_OUTPUT_MODE:
            pullbacks_by_route: dict[UUID, dict[str, float]] = {}
            for (
                _attachment_id,
                _requested_mm,
                route_id,
                boundary,
                length_mm,
                _diameter_mm,
            ) in main_pullbacks:
                pullbacks_by_route.setdefault(route_id, {})[boundary] = length_mm
            insulation_routes = []
            for route in routes:
                route_pullbacks = pullbacks_by_route.get(route.cable_id, {})
                insulation = split_route_endpoint_pullbacks(
                    route,
                    route_pullbacks.get("start", 0.0),
                    route_pullbacks.get("end", 0.0),
                ).insulation
                if insulation is not None:
                    insulation_routes.append(insulation)
            branch_decorations = []
            for branch, settings in zip(branches, branch_materials):
                insulation = split_route_for_pullback(
                    branch.route,
                    branch.pullback_mm,
                ).insulation
                if insulation is not None:
                    branch_decorations.append(
                        (insulation, settings.stripes, branch.diameter_mm / 2.0)
                    )
            replace_group_stripe_bodies(
                component,
                tuple(insulation_routes),
                materials.stripes,
                group.diameter_mm / 2.0,
                design,
                branch_decorations=tuple(branch_decorations),
            )
        else:
            _replace_group_stripe_graphics(
                harness,
                routes,
                materials.stripes,
                group.diameter_mm / 2.0,
                group_id,
                is_visible=occurrence.isLightBulbOn,
                branch_decorations=tuple(
                    (branch.route, settings.stripes, branch.diameter_mm / 2.0)
                    for branch, settings in zip(branches, branch_materials)
                ),
            )
        metadata.update(material_metadata(materials))
        attribute.value = json.dumps(metadata, sort_keys=True)
        applied += 1
    return applied


# noinspection DuplicatedCode
def restore_cable_group_stripe_graphics(
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Recreate transient stripe meshes for existing generated cable-group solids.

    Generated components retain their exact component-local route curves, while
    the harness definition remains authoritative for current stripe settings.
    Rebuilding only Custom Graphics keeps existing solid geometry untouched.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    restored = 0
    for occurrence in generated_cable_group_occurrences(harness):
        if generated_cable_group_output_mode(occurrence) == FINALIZED_OUTPUT_MODE:
            continue
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        stripes = definition.cable_group_materials(group).stripes
        routes = group_routes_from_metadata(metadata)
        branches = connection_branches_from_metadata(metadata)
        if not routes and stripes:
            raise RuntimeError(
                "Generated cable-group metadata has no routes for restoring stripe patterns."
            )
        clear_group_stripe_graphics(component, group_id, include_legacy=True)
        restored += _replace_group_stripe_graphics(
            harness,
            routes,
            stripes,
            group.diameter_mm / 2.0,
            group_id,
            is_visible=occurrence.isLightBulbOn,
            **(
                {
                    "branch_decorations": tuple(
                        (
                            branch.route,
                            _attachment_materials(definition, group, branch.attachment_id).stripes,
                            branch.diameter_mm / 2.0,
                        )
                        for branch in branches
                    )
                }
                if branches
                else {}
            ),
        )
    return restored
