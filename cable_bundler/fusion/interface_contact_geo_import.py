"""
Import explicit Fusion geometry names into empty Interface contact Values.
"""

from __future__ import annotations

from collections import Counter
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
    Fill empty Values from the preferred live geometry in one edit.

    An empty selection considers every contact. Pins and existing Values stay intact.
    The first matching entity is Fusion's preferred resolution of a split token,
    matching the contact diagram. If it is unnamed, use another match only when
    its explicit name is unambiguous.
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
    skipped: Counter[str] = Counter()
    for contact in interface.contacts:
        if contact.contact_id not in scope:
            continue
        if contact.name:
            skipped["already set"] += 1
            continue
        entities = resolve_contact_entities(design, contact.entity_token)
        if not entities:
            skipped["unresolved"] += 1
            continue
        sources = [
            explicit_attachment_target_name(entity, contact.kind)
            for entity in entities
            if attachment_target_kind(entity) is contact.kind
        ]
        if not sources:
            skipped["wrong geometry kind"] += 1
            continue
        name = sources[0]
        if not name:
            explicit_names = {source for source in sources if source}
            if not explicit_names:
                skipped["unnamed geometry"] += 1
                continue
            if len(explicit_names) > 1:
                skipped["conflicting names"] += 1
                continue
            name = explicit_names.pop()
        if len(name) > 80:
            skipped["overlong name"] += 1
            continue
        names[contact.contact_id] = name
    if names:
        name_interface_contacts(harness_id, interface_id, names, gateway)
    notice = f"Imported geometry Values for {len(names)} of {len(scope)} Interface contacts."
    if skipped:
        reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(skipped.items()))
        notice += f" Skipped: {reasons}."
    return notice
