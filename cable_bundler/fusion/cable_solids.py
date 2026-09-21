"""
Build persistent cable-group solids from the exact curves used by previews.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Protocol
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import (
    HarnessDefinition,
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
from .cable_solid_parts.metadata import group_routes_from_metadata, world_to_harness
from .cable_solid_parts.solid_builder import build_cable_group_solid
from .cable_solid_parts.stripes import (
    build_continuous_segment_stripes,
    clear_all_stripe_graphics,
    clear_group_stripe_graphics,
    generated_stripe_graphics_groups,
    replace_group_stripe_bodies,
    replace_group_stripe_graphics,
)
from .cable_solid_parts.sweep_geometry import prepare_group_sweep_segments
from .harness_gateway import ATTRIBUTE_GROUP
from .route_preview import solve_cable_group_centerlines

_build_continuous_segment_stripes = build_continuous_segment_stripes
_prepare_group_sweep_segments = prepare_group_sweep_segments
_replace_group_stripe_graphics = replace_group_stripe_graphics
_replace_group_stripe_bodies = replace_group_stripe_bodies

__all__ = [
    "GENERATED_STRIPE_GROUP_ID",
    "_build_continuous_segment_stripes",
    "_prepare_group_sweep_segments",
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
    routes, legs = solve_cable_group_centerlines(design, definition, notices)
    routes_by_id = {route.cable_id: route for route in routes}
    if not routes or set(routes_by_id) != {leg.route_id for leg in legs}:
        raise ValueError("Every cable group must have complete route geometry before generation.")
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
    if not affected_ids:
        return 0
    previous_by_id: dict[UUID, adsk.fusion.Occurrence] = {}
    for occurrence in generated_cable_group_occurrences(harness):
        attribute = occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP,
            GENERATED_CABLE_GROUP_ATTRIBUTE,
        )
        if attribute is None:
            continue
        try:
            group_id = UUID(json.loads(attribute.value)["cable_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated cable group has invalid identity metadata.") from error
        if group_id in affected_ids:
            if group_id in previous_by_id:
                raise RuntimeError("A cable group has duplicate generated geometry.")
            previous_by_id[group_id] = occurrence
    if not previous_by_id:
        return 0

    routes, legs = solve_cable_group_centerlines(design, definition, notices)
    routes_by_id = {route.cable_id: route for route in routes}
    if not routes or set(routes_by_id) != {leg.route_id for leg in legs}:
        raise ValueError("Every cable group must have complete route geometry before generation.")
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


# noinspection DuplicatedCode
def apply_cable_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply resolved materials to existing generated cable-group components.

    Material changes do not rebuild route solids. Stored component-local leg
    curves are reused to replace stripe presentation over the grouped bodies.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    applied = 0
    for occurrence in generated_cable_group_occurrences(harness):
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
        bodies = component.bRepBodies
        if bodies.count == 0:
            raise RuntimeError(f"Generated Cable Group {group_id} has no bodies to color.")
        appearance = cable_appearance(design, materials.main_color, materials.appearance)
        for body_index in range(bodies.count):
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = appearance
        routes = group_routes_from_metadata(metadata)
        if not routes and materials.stripes:
            raise RuntimeError(
                "Generated cable-group metadata has no routes for applying stripe patterns."
            )
        clear_group_stripe_graphics(component, group_id, include_legacy=True)
        clear_group_stripe_graphics(harness, group_id)
        if generated_cable_group_output_mode(occurrence) == FINALIZED_OUTPUT_MODE:
            replace_group_stripe_bodies(
                component,
                routes,
                materials.stripes,
                group.diameter_mm / 2.0,
                design,
            )
        else:
            _replace_group_stripe_graphics(
                harness,
                routes,
                materials.stripes,
                group.diameter_mm / 2.0,
                group_id,
                is_visible=occurrence.isLightBulbOn,
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
        )
    return restored
