"""
Manage generated cable-body and transient stripe visibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Protocol
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.fusion

from .cable_solid_parts.constants import (
    FINALIZED_OUTPUT_MODE,
    GENERATED_CABLE_GROUP_ATTRIBUTE,
    GENERATED_OUTPUT_MODE_KEY,
    SOLID_OUTPUT_MODE,
)
from .cable_solid_parts.metadata import connection_branches_from_metadata
from .cable_solid_parts.stripes import (
    clear_all_stripe_graphics,
    generated_stripe_graphics_groups,
)
from .harness_gateway import ATTRIBUTE_GROUP


def _cable_solid_services() -> ModuleType:
    """
    Resolve the active facade module so Fusion reloads and test isolation stay coherent.
    """
    return import_module("cable_bundler.fusion.cable_solids")


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
    if not isinstance(metadata, dict):
        return SOLID_OUTPUT_MODE
    mode = metadata.get(GENERATED_OUTPUT_MODE_KEY)
    return FINALIZED_OUTPUT_MODE if mode == FINALIZED_OUTPUT_MODE else SOLID_OUTPUT_MODE


def has_finalized_cable_group_output(harness: adsk.fusion.Component) -> bool:
    """
    Report whether every generated cable group uses persistent finalized output.

    A harness without generated output remains in its working state.
    """
    occurrences = _cable_solid_services().generated_cable_group_occurrences(harness)
    return bool(occurrences) and all(
        generated_cable_group_output_mode(occurrence) == FINALIZED_OUTPUT_MODE
        for occurrence in occurrences
    )


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
        for occurrence in _cable_solid_services().generated_cable_group_occurrences(harness)
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
    for occurrence in _cable_solid_services().generated_cable_group_occurrences(harness):
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


def generated_attachment_bodies(
    root: adsk.fusion.Component,
    harness: adsk.fusion.Component,
    attachment_id: UUID,
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Resolve generated sweep-body proxies owned by one cable-end attachment.

    Malformed or legacy metadata is ignored because palette hover is a
    best-effort interaction. Weld bodies are excluded because they are not
    part of the attachment's swept cable segment.
    """
    bodies: list[adsk.fusion.BRepBody] = []
    for occurrence in _cable_solid_services().generated_cable_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_CABLE_GROUP_ATTRIBUTE
        )
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            branches = connection_branches_from_metadata(metadata)
        except (AttributeError, TypeError, json.JSONDecodeError, RuntimeError):
            continue
        branch_body_count = sum(
            branch.insulation_body_count + branch.pullback_body_count + branch.weld_body_count
            for branch in branches
        )
        body_count = component.bRepBodies.count
        if branch_body_count > body_count:
            continue
        body_index = body_count - branch_body_count
        selected_indices: list[int] = []
        for branch in branches:
            sweep_body_count = branch.insulation_body_count + branch.pullback_body_count
            if branch.attachment_id == attachment_id:
                selected_indices.extend(range(body_index, body_index + sweep_body_count))
            body_index += sweep_body_count + branch.weld_body_count
        bodies.extend(_root_context_bodies_at_indices(root, component, selected_indices))
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


def _root_context_bodies_at_indices(
    root: adsk.fusion.Component,
    component: adsk.fusion.Component,
    body_indices: list[int],
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Return selected generated-body proxies in every root assembly context.
    """
    bodies: list[adsk.fusion.BRepBody] = []
    root_occurrences = root.allOccurrencesByComponent(component)
    for occurrence_index in range(root_occurrences.count):
        root_occurrence = root_occurrences.item(occurrence_index)
        if root_occurrence is None:
            continue
        for body_index in body_indices:
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
    occurrences = _cable_solid_services().generated_cable_group_occurrences(harness)
    for occurrence in occurrences:
        if not occurrence.deleteMe():
            raise RuntimeError("Fusion could not delete a generated cable component.")
    clear_all_stripe_graphics(harness)
    return len(occurrences)
