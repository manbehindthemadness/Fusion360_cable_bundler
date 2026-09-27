"""
Copy saved Interface fields through projected assembly-space geometry.
"""

from __future__ import annotations

from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ..application import fill_interface_contact_details
from ..application.interface_projection_copy import (
    OrientedContact,
    match_projected_interface_contacts,
    projected_interface_candidates,
)
from ..domain import InterfaceContact, InterfaceDefinition, loads
from .attachment_targets import attachment_target_kind
from .interface_contact_cache import resolve_contact_entities
from .interface_contact_projection import _parent_axes
from .interface_contact_rows import describe_row_target
from .interface_targets import resolve_interface_target
from .ui.support import _create_harness_gateway, _require_active_design


def picked_source_interface(
    design: object,
    interfaces: tuple[InterfaceDefinition, ...],
    destination_id: UUID,
    entity: object,
) -> InterfaceDefinition:
    """
    Resolve a clicked saved target to exactly one other Interface.

    An arbitrary body, sketch, or occurrence is never a naming source.
    """
    token = getattr(entity, "entityToken", None)
    if not isinstance(token, str) or not token:
        raise ValueError("Pick a saved target of another Interface.")
    matches = [
        interface
        for interface in interfaces
        if interface.interface_id != destination_id
        and any(
            resolved is not None
            and (resolved == entity or getattr(resolved, "entityToken", None) == token)
            for target in interface.targets
            for resolved in (resolve_interface_target(design, target),)
        )
    ]
    if len(matches) != 1:
        raise ValueError("Pick a target belonging to exactly one other Interface in this harness.")
    return matches[0]


def _oriented_contacts(
    design: object, contacts: tuple[InterfaceContact, ...]
) -> tuple[OrientedContact, ...]:
    """
    Resolve saved contacts to their first usable local orientation and center.
    """
    oriented = []
    for contact in contacts:
        for entity in resolve_contact_entities(design, contact.entity_token):
            if attachment_target_kind(entity) is not contact.kind:
                continue
            try:
                target = describe_row_target(entity)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            axes = _parent_axes(entity)
            normal = target.normal or (tuple(axes[2]) if axes else (0.0, 0.0, 1.0))
            oriented.append(OrientedContact(contact.contact_id, target.center_mm, normal))
            break
    return tuple(oriented)


def copy_projected_interface_details(
    application: adsk.core.Application,
    harness_id: UUID,
    destination_id: UUID,
    source_id: UUID,
    selected_ids: tuple[UUID, ...],
    copy_pins: bool,
    choices: dict[UUID, UUID] | None = None,
    copy_values: bool = True,
) -> tuple[str, tuple[dict[str, object], ...]]:
    """
    Fill selected fields from unique or reviewed matches, returning conflicts.
    """
    if destination_id == source_id:
        raise ValueError("Select another Interface as the source.")
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    destination = next(
        (item for item in definition.interfaces if item.interface_id == destination_id), None
    )
    source = next((item for item in definition.interfaces if item.interface_id == source_id), None)
    if destination is None or source is None:
        raise ValueError("The selected Interfaces are no longer saved in this harness.")
    known = {contact.contact_id for contact in destination.contacts}
    if len(selected_ids) != len(set(selected_ids)) or not set(selected_ids).issubset(known):
        raise ValueError("Geo Import selection contains an invalid contact identity.")
    if not isinstance(copy_values, bool) or not isinstance(copy_pins, bool):
        raise ValueError("Copy Values and Pins must be enabled or disabled.")
    if not copy_values and not copy_pins:
        raise ValueError("Copy Values, Pins, or both.")
    scoped_ids = set(selected_ids) if selected_ids else known
    if not source.contacts:
        raise ValueError("The source Interface has no saved contacts to copy.")
    destination_points = _oriented_contacts(design, destination.contacts)
    source_points = _oriented_contacts(design, source.contacts)
    matches = {
        contact_id: source_id
        for contact_id, source_id in match_projected_interface_contacts(
            destination_points, source_points
        ).items()
        if contact_id in scoped_ids
    }
    candidates = projected_interface_candidates(destination_points, source_points)
    conflicts = {
        contact_id: source_ids
        for contact_id, source_ids in candidates.items()
        if contact_id in scoped_ids and source_ids and contact_id not in matches
    }
    if choices is not None:
        if any(
            contact_id not in conflicts or source_id not in conflicts[contact_id]
            for contact_id, source_id in choices.items()
        ):
            raise ValueError("A reviewed source pad no longer matches its destination.")
        if len(set((*matches.values(), *choices.values()))) != len(matches) + len(choices):
            raise ValueError("The same source pad cannot fill multiple contacts.")
        matches.update(choices)
    source_by_id = {contact.contact_id: contact for contact in source.contacts}
    destination_by_id = {contact.contact_id: contact for contact in destination.contacts}
    details = {
        destination_contact_id: (
            source_by_id[source_contact_id].name if copy_values else "",
            source_by_id[source_contact_id].pin if copy_pins else "",
        )
        for destination_contact_id, source_contact_id in matches.items()
        if destination_contact_id in scoped_ids
    }
    values, pins = fill_interface_contact_details(
        harness_id, destination_id, details, copy_pins, gateway
    )
    skipped = len(scoped_ids) - len(details)
    notice = (
        f"Copied {values} Values and {pins} Pins from {source.name}; "
        f"{skipped} contacts had no unique projected match."
    )
    review = tuple(
        {
            "contactId": str(contact_id),
            "currentName": destination_by_id[contact_id].name,
            "suggestions": [
                {
                    "sourceContactId": str(source_id),
                    "value": source_by_id[source_id].name,
                    "pin": source_by_id[source_id].pin,
                }
                for source_id in source_ids
            ],
        }
        for contact_id, source_ids in conflicts.items()
        if choices is None or contact_id not in choices
    )
    return notice, review
