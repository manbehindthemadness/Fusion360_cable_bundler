"""
Import explicit Fusion geometry names into empty Interface contact Values.
"""

from __future__ import annotations

from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ..application import name_interface_contacts
from ..domain import loads
from .attachment_targets import attachment_target_kind, explicit_attachment_target_name
from .interface_contact_cache import resolve_contact_entities
from .ui.support import _create_harness_gateway, _require_active_design


def import_interface_contact_geometry_names(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    selected_ids: tuple[UUID, ...],
) -> str:
    """
    Fill empty Values from live, unambiguous geometry names in one edit.

    An empty selection considers every contact. Pins and existing Values stay intact;
    unresolved, unnamed, conflicting, or overlong source names are skipped.
    """
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if interface is None:
        raise ValueError("Selected Interface no longer exists.")
    known = {contact.contact_id for contact in interface.contacts}
    if len(set(selected_ids)) != len(selected_ids) or not set(selected_ids).issubset(known):
        raise ValueError("Geo Import selection contains an invalid contact identity.")
    scope = set(selected_ids) if selected_ids else known
    names: dict[UUID, str] = {}
    for contact in interface.contacts:
        if contact.contact_id not in scope or contact.name:
            continue
        sources = [
            explicit_attachment_target_name(entity, contact.kind)
            for entity in resolve_contact_entities(design, contact.entity_token)
            if attachment_target_kind(entity) is contact.kind
        ]
        if sources and all(sources) and len(set(sources)) == 1 and len(sources[0]) <= 80:
            names[contact.contact_id] = sources[0]
    if names:
        name_interface_contacts(harness_id, interface_id, names, gateway)
    return f"Imported geometry Values for {len(names)} of {len(scope)} Interface contacts."
