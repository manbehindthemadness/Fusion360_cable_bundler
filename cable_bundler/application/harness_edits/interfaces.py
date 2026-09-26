"""
Transactional edits for geometry-reference Interfaces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID, uuid4

from ...domain import (
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    next_available_name,
    validate_harness,
)
from .support import persist_definition, read_definition
from .types import HarnessEditGateway


def add_interface(
    harness_id: UUID,
    name: str,
    targets: tuple[InterfaceTarget, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> InterfaceDefinition:
    """
    Persist one independent Interface without changing route topology.
    """
    original, definition = read_definition(harness_id, gateway)
    if not isinstance(name, str):
        raise ValueError("Interface name must be text.")
    interface = InterfaceDefinition(
        interface_id=id_factory(),
        name=next_available_name(name.strip(), (item.name for item in definition.interfaces)),
        targets=targets,
    )
    updated = replace(definition, interfaces=(*definition.interfaces, interface))
    if any(issue.code == "duplicate_id" for issue in validate_harness(updated)):
        raise ValueError("Generated Interface identity is already in use.")
    persist_definition(harness_id, original, updated, gateway)
    return interface


def rename_interface(
    harness_id: UUID,
    interface_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> InterfaceDefinition:
    """
    Rename one Interface while retaining identity and target order.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Interface name must not be empty.")
    original, definition = read_definition(harness_id, gateway)
    current = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if current is None:
        raise ValueError("Selected Interface no longer exists.")
    if any(
        item.interface_id != interface_id and item.name.casefold() == name.strip().casefold()
        for item in definition.interfaces
    ):
        raise ValueError("Interface name is already in use.")
    updated_interface = replace(current, name=name.strip())
    updated = replace(
        definition,
        interfaces=tuple(
            updated_interface if item.interface_id == interface_id else item
            for item in definition.interfaces
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_interface


def remove_interface(
    harness_id: UUID,
    interface_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Delete one reference-only Interface without changing its Fusion geometry.
    """
    original, definition = read_definition(harness_id, gateway)
    if all(item.interface_id != interface_id for item in definition.interfaces):
        raise ValueError("Selected Interface no longer exists.")
    updated = replace(
        definition,
        interfaces=tuple(
            item for item in definition.interfaces if item.interface_id != interface_id
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def add_interface_contacts(
    harness_id: UUID,
    interface_id: UUID,
    contacts: tuple[InterfaceContact, ...],
    gateway: HarnessEditGateway,
) -> InterfaceDefinition:
    """
    Append unique contacts in picker order without altering existing identities.
    """
    original, definition = read_definition(harness_id, gateway)
    current = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if current is None:
        raise ValueError("Selected Interface no longer exists.")
    existing_tokens = {contact.entity_token for contact in current.contacts}
    additions = tuple(
        contact for contact in contacts if contact.entity_token not in existing_tokens
    )
    updated_interface = replace(current, contacts=(*current.contacts, *additions))
    updated = replace(
        definition,
        interfaces=tuple(
            updated_interface if item.interface_id == interface_id else item
            for item in definition.interfaces
        ),
    )
    if any(issue.code == "duplicate_id" for issue in validate_harness(updated)):
        raise ValueError("Interface contact identity is already in use.")
    persist_definition(harness_id, original, updated, gateway)
    return updated_interface


def remove_interface_contacts(
    harness_id: UUID,
    interface_id: UUID,
    contact_ids: tuple[UUID, ...],
    gateway: HarnessEditGateway,
) -> InterfaceDefinition:
    """
    Delete selected contact references in one transaction, preserving survivor order.
    """
    original, definition = read_definition(harness_id, gateway)
    current = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if current is None:
        raise ValueError("Selected Interface no longer exists.")
    selected = set(contact_ids)
    if not selected or not selected.issubset(contact.contact_id for contact in current.contacts):
        raise ValueError("Contact deletion requires known selected identities.")
    updated_interface = replace(
        current,
        contacts=tuple(
            contact for contact in current.contacts if contact.contact_id not in selected
        ),
    )
    updated = replace(
        definition,
        interfaces=tuple(
            updated_interface if item.interface_id == interface_id else item
            for item in definition.interfaces
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_interface


def name_interface_contacts(
    harness_id: UUID,
    interface_id: UUID,
    names: dict[UUID, str],
    gateway: HarnessEditGateway,
) -> InterfaceDefinition:
    """
    Persist confidently matched contact names in one transaction.

    Unmentioned contacts retain their names and identity. Unknown identities and
    whitespace-only or oversized proposed names fail before the harness is written.
    """
    original, definition = read_definition(harness_id, gateway)
    current = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if current is None:
        raise ValueError("Selected Interface no longer exists.")
    known = {contact.contact_id for contact in current.contacts}
    if not set(names).issubset(known):
        raise ValueError("Contact naming request contains an unknown identity.")
    if any(
        not isinstance(name, str) or (name and not name.strip()) or len(name.strip()) > 80
        for name in names.values()
    ):
        raise ValueError("Contact names must be text of at most 80 characters.")
    updated_interface = replace(
        current,
        contacts=tuple(
            replace(contact, name=names[contact.contact_id].strip())
            if contact.contact_id in names
            else contact
            for contact in current.contacts
        ),
    )
    updated = replace(
        definition,
        interfaces=tuple(
            updated_interface if item.interface_id == interface_id else item
            for item in definition.interfaces
        ),
    )
    if names:
        persist_definition(harness_id, original, updated, gateway)
    return updated_interface


def set_interface_contact_details(
    harness_id: UUID,
    interface_id: UUID,
    contact_id: UUID,
    value: str,
    pin: str,
    gateway: HarnessEditGateway,
) -> InterfaceDefinition:
    """
    Save one contact's display value and optional pin in a single transaction.
    """
    if not isinstance(value, str) or not isinstance(pin, str):
        raise ValueError("Contact value and pin must be text.")
    original, definition = read_definition(harness_id, gateway)
    current = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if current is None:
        raise ValueError("Selected Interface no longer exists.")
    contact = next((item for item in current.contacts if item.contact_id == contact_id), None)
    if contact is None:
        raise ValueError("Selected contact no longer exists.")
    updated_contact = replace(contact, name=value.strip(), pin=pin.strip())
    if updated_contact == contact:
        return current
    updated_interface = replace(
        current,
        contacts=tuple(
            updated_contact if item.contact_id == contact_id else item for item in current.contacts
        ),
    )
    updated = replace(
        definition,
        interfaces=tuple(
            updated_interface if item.interface_id == interface_id else item
            for item in definition.interfaces
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return updated_interface
