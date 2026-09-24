"""
Build persistent cable-group solids from the exact curves used by previews.
"""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import (
    AttachmentTargetKind,
    CableGroupDefinition,
    CableMaterialSettings,
    HarnessDefinition,
    PullbackMode,
    validate_harness,
)
from ..routing import (
    RoutePreview,
)
from .attachment_targets import resolve_attachment_target
from .cable_solid_parts.constants import (
    GENERATED_CABLE_GROUP_ATTRIBUTE,
    GENERATED_STRIPE_GROUP_ID,
    SOLID_OUTPUT_MODE,
)
from .cable_solid_parts.materials import cable_appearance as cable_appearance
from .cable_solid_parts.metadata import (
    group_geometry_routes_from_metadata,
    route_in_component_space,
    world_to_harness,
)
from .cable_solid_parts.solid_builder import build_cable_group_solid
from .cable_solid_parts.stripes import (
    build_continuous_segment_stripes,
    clear_group_stripe_graphics,
    replace_group_stripe_bodies,
    replace_group_stripe_graphics,
)
from .cable_solid_parts.sweep_geometry import (
    prepare_group_sweep_segments,
    split_route_endpoint_pullbacks,
    split_route_for_pullback,
)
from .cable_solid_parts.welds import WeldEndpoint
from .cable_solid_visibility import (
    CableSolidVisibilityState,
    clear_cable_solids,
    generated_attachment_bodies,
    generated_cable_group_bodies,
    generated_cable_group_output_mode,
    hide_generated_cable_group_solids,
    restore_generated_cable_group_visibility,
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
    "cable_appearance",
    "apply_cable_group_materials",
    "clear_cable_solids",
    "generate_cable_group_solids",
    "generated_attachment_bodies",
    "generated_cable_group_output_mode",
    "generated_cable_group_bodies",
    "generated_cable_group_occurrences",
    "hide_generated_cable_group_solids",
    "refresh_changed_generated_cable_groups",
    "refresh_generated_cable_groups_for_connection",
    "restore_cable_group_stripe_graphics",
    "restore_generated_cable_group_visibility",
]


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


def _attachment_weld_endpoint(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    attachment_id: Optional[UUID],
) -> Optional[WeldEndpoint]:
    """
    Resolve weld geometry for a connected leaf, optionally with a target face.
    """
    if attachment_id is None:
        return None
    for connection in definition.connections:
        if connection.connection_id not in group.connection_ids:
            continue
        attachment = next(
            (item for item in connection.attachments if item.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            continue
        if not attachment.has_target or connection.attachment_children(attachment_id):
            return None
        materials = definition.cable_end_attachment_materials(
            group,
            connection.connection_id,
            attachment_id,
        )
        if materials.weld.value <= 1e-9:
            return None
        face = None
        if attachment.target_kind is AttachmentTargetKind.FACE:
            entity = resolve_attachment_target(design, attachment)
            face = adsk.fusion.BRepFace.cast(entity)
        return WeldEndpoint(
            attachment_id,
            face,
            definition.cable_end_attachment_conductor_diameter(
                group,
                connection.connection_id,
                attachment_id,
            ),
            materials.weld,
        )
    return None


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


def _connection_endpoint_weld(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    connection_id: Optional[UUID],
) -> Optional[WeldEndpoint]:
    """
    Resolve a weld for a single connected root node that is also a leaf.
    """
    if connection_id is None:
        return None
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        return None
    roots = connection.attachment_children(None)
    if len(roots) != 1:
        return None
    attachment = roots[0]
    return _attachment_weld_endpoint(
        design,
        definition,
        group,
        attachment.attachment_id,
    )


def _leg_endpoint_welds(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    leg: CableGroupRouteLeg,
) -> tuple[Optional[WeldEndpoint], Optional[WeldEndpoint]]:
    """
    Resolve target-facing welds for both ends of one routed leg.
    """
    if getattr(leg, "is_connection_branch", False):
        return (
            _attachment_weld_endpoint(
                design,
                definition,
                group,
                getattr(leg, "attachment_id", None),
            ),
            None,
        )
    return (
        _connection_endpoint_weld(
            design,
            definition,
            group,
            getattr(leg, "start_connection_id", None),
        ),
        _connection_endpoint_weld(
            design,
            definition,
            group,
            getattr(leg, "end_connection_id", None),
        ),
    )


def _route_build_options(
    design: adsk.fusion.Design,
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
    weld_options = tuple(_leg_endpoint_welds(design, definition, group, leg) for leg in legs)
    if any(start is not None or end is not None for start, end in weld_options):
        options.update(
            {
                "route_welds": tuple(start for start, _end in weld_options),
                "route_end_welds": tuple(end for _start, end in weld_options),
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
                    design,
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
            route_options = _route_build_options(design, definition, group, group_legs)
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


def apply_cable_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply material changes through the focused generated-material service.
    """
    from .cable_solid_materials import apply_cable_group_materials as apply_materials

    return apply_materials(design, harness, definition)


def restore_cable_group_stripe_graphics(
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Restore transient stripe graphics through the focused material service.
    """
    from .cable_solid_materials import restore_cable_group_stripe_graphics as restore_graphics

    return restore_graphics(harness, definition)
