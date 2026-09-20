"""
Build persistent wire-group solids from the exact curves used by previews.
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

from ..application import WireGroupRouteLeg
from ..domain import (
    HarnessDefinition,
    validate_harness,
)
from ..routing import (
    RoutePreview,
)
from .harness_gateway import ATTRIBUTE_GROUP
from .route_preview import solve_wire_group_centerlines
from .wire_solid_parts.constants import (
    GENERATED_STRIPE_GROUP_ID,
    GENERATED_WIRE_GROUP_ATTRIBUTE,
)
from .wire_solid_parts.materials import material_metadata, wire_appearance
from .wire_solid_parts.metadata import group_routes_from_metadata, world_to_harness
from .wire_solid_parts.solid_builder import build_wire_group_solid
from .wire_solid_parts.stripes import (
    build_continuous_segment_stripes,
    clear_all_stripe_graphics,
    clear_group_stripe_graphics,
    generated_stripe_graphics_groups,
    replace_group_stripe_graphics,
)
from .wire_solid_parts.sweep_geometry import prepare_group_sweep_segments

_build_continuous_segment_stripes = build_continuous_segment_stripes
_prepare_group_sweep_segments = prepare_group_sweep_segments
_replace_group_stripe_graphics = replace_group_stripe_graphics

__all__ = [
    "GENERATED_STRIPE_GROUP_ID",
    "_build_continuous_segment_stripes",
    "_prepare_group_sweep_segments",
    "_replace_group_stripe_graphics",
    "WireSolidVisibilityState",
    "generated_wire_group_occurrences",
    "hide_generated_wire_group_solids",
    "restore_generated_wire_group_visibility",
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
class WireSolidVisibilityState:
    """
    Capture generated body and stripe visibility for one harness.
    """

    occurrences: tuple[tuple[_VisibilityOccurrence, bool], ...]
    stripe_groups: tuple[tuple[_VisibilityGraphicsGroup, bool], ...]


def generate_wire_group_solids(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    replace_existing: bool = False,
    notices: Optional[list[str]] = None,
) -> int:
    """
    Build one multi-body component per wire group before replacing managed output.
    """
    issues = validate_harness(definition)
    if issues:
        raise ValueError(
            "Cannot generate wire groups: " + "; ".join(issue.message for issue in issues)
        )
    if not definition.wire_groups:
        raise ValueError("Create at least one wire group before generating solids.")
    previous = generated_wire_group_occurrences(harness)
    if previous and not replace_existing:
        raise ValueError(
            "Generated solids already exist; confirm rebuilding before replacing them."
        )
    routes, legs = solve_wire_group_centerlines(design, definition, notices)
    routes_by_id = {route.wire_id: route for route in routes}
    if not routes or set(routes_by_id) != {leg.route_id for leg in legs}:
        raise ValueError("Every wire group must have complete route geometry before generation.")
    legs_by_group: dict[UUID, list[tuple[WireGroupRouteLeg, RoutePreview]]] = {}
    for leg in legs:
        legs_by_group.setdefault(leg.wire_group_id, []).append((leg, routes_by_id[leg.route_id]))
    local_transform = world_to_harness(design, harness)
    created: list[adsk.fusion.Occurrence] = []
    try:
        for group_index, group in enumerate(definition.wire_groups):
            group_legs = legs_by_group.get(group.wire_group_id, [])
            if not group_legs:
                raise ValueError(f"Wire Group {group_index + 1} has no route legs.")
            occurrence = harness.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if occurrence is None:
                raise RuntimeError(
                    f"Fusion could not create a component for Wire Group {group_index + 1}."
                )
            created.append(occurrence)
            try:
                build_wire_group_solid(
                    occurrence.component,
                    harness,
                    group,
                    group_index,
                    tuple(route for _leg, route in group_legs),
                    local_transform,
                    definition.harness_id,
                    definition.wire_group_materials(group),
                    design,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Wire Group {group_index + 1} could not be generated: {error}"
                ) from error
        for occurrence in previous:
            if not occurrence.deleteMe():
                raise RuntimeError("Fusion could not remove old generated wire-group geometry.")
    except Exception as error:
        for group in definition.wire_groups:
            clear_group_stripe_graphics(harness, group.wire_group_id)
        for occurrence in reversed(created):
            if occurrence.isValid and not occurrence.deleteMe():
                raise RuntimeError(
                    "Fusion could not clean incomplete grouped-wire geometry; undo this command."
                ) from error
        if previous:
            restore_wire_group_stripe_graphics(harness, definition)
        raise
    return len(created)


def generated_wire_group_occurrences(
    harness: adsk.fusion.Component,
) -> tuple[adsk.fusion.Occurrence, ...]:
    """
    Find direct children explicitly marked as generated wire-group output.
    """
    return tuple(
        occurrence
        for occurrence in harness.occurrences
        if occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE
        )
        is not None
    )


def hide_generated_wire_group_solids(
    harness: adsk.fusion.Component,
) -> WireSolidVisibilityState:
    """
    Hide managed wire-group occurrences and capture their exact prior visibility.

    If Fusion rejects a visibility update, every occurrence changed so far is
    restored before the error is propagated.
    """
    occurrence_visibility = tuple(
        (occurrence, occurrence.isLightBulbOn)
        for occurrence in generated_wire_group_occurrences(harness)
    )
    stripe_visibility = tuple(
        (group, group.isVisible) for group in generated_stripe_graphics_groups(harness)
    )
    visibility = WireSolidVisibilityState(occurrence_visibility, stripe_visibility)
    try:
        for occurrence, was_visible in visibility.occurrences:
            if was_visible:
                occurrence.isLightBulbOn = False
        for group, was_visible in visibility.stripe_groups:
            if was_visible:
                group.isVisible = False
    except (AttributeError, RuntimeError) as error:
        restore_generated_wire_group_visibility(visibility)
        raise RuntimeError("Fusion could not hide generated wire solids.") from error
    return visibility


def restore_generated_wire_group_visibility(
    visibility: WireSolidVisibilityState,
) -> None:
    """
    Restore managed wire-group occurrences to their captured light-bulb states.
    """
    for occurrence, was_visible in visibility.occurrences:
        if occurrence.isValid:
            occurrence.isLightBulbOn = was_visible
    for group, was_visible in visibility.stripe_groups:
        if group.isValid:
            group.isVisible = was_visible


def generated_wire_group_bodies(
    root: adsk.fusion.Component,
    harness: adsk.fusion.Component,
    wire_group_ids: tuple[UUID, ...],
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Resolve root-context bodies for persistent wire-group identities.

    Malformed metadata is ignored so palette hover remains a harmless,
    best-effort operation.
    """
    selected_ids = {str(group_id) for group_id in wire_group_ids}
    bodies: list[adsk.fusion.BRepBody] = []
    for occurrence in generated_wire_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE)
        if attribute is None:
            continue
        try:
            group_id = json.loads(attribute.value).get("wire_group_id")
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


def clear_wire_solids(harness: adsk.fusion.Component) -> int:
    """
    Delete direct child components marked as generated wire output.

    Callers should invoke this inside a native Fusion command transaction so a
    failed deletion rolls the complete operation back and Undo can restore it.
    """
    occurrences = generated_wire_group_occurrences(harness)
    for occurrence in occurrences:
        if not occurrence.deleteMe():
            raise RuntimeError("Fusion could not delete a generated wire component.")
    clear_all_stripe_graphics(harness)
    return len(occurrences)


# noinspection DuplicatedCode
def apply_wire_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply resolved materials to existing generated wire-group components.

    Material changes do not rebuild route solids. Stored component-local leg
    curves are reused to replace stripe presentation over the grouped bodies.
    """
    groups = {group.wire_group_id: group for group in definition.wire_groups}
    applied = 0
    for occurrence in generated_wire_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE)
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["wire_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated wire group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        materials = definition.wire_group_materials(group)
        bodies = component.bRepBodies
        if bodies.count == 0:
            raise RuntimeError(f"Generated Wire Group {group_id} has no bodies to color.")
        appearance = wire_appearance(design, materials.main_color, materials.appearance)
        for body_index in range(bodies.count):
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = appearance
        routes = group_routes_from_metadata(metadata)
        if not routes and materials.stripes:
            raise RuntimeError(
                "Generated wire-group metadata has no routes for applying stripe patterns."
            )
        clear_group_stripe_graphics(component, group_id, include_legacy=True)
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
def restore_wire_group_stripe_graphics(
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Recreate transient stripe meshes for existing generated wire-group solids.

    Generated components retain their exact component-local route curves, while
    the harness definition remains authoritative for current stripe settings.
    Rebuilding only Custom Graphics keeps existing solid geometry untouched.
    """
    groups = {group.wire_group_id: group for group in definition.wire_groups}
    restored = 0
    for occurrence in generated_wire_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE)
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["wire_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated wire group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        stripes = definition.wire_group_materials(group).stripes
        routes = group_routes_from_metadata(metadata)
        if not routes and stripes:
            raise RuntimeError(
                "Generated wire-group metadata has no routes for restoring stripe patterns."
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
