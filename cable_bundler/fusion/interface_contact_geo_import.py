"""
Import explicit Fusion geometry names into empty Interface contact fields.
"""

from __future__ import annotations

import re
from collections import Counter
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ..application import fill_interface_contact_details
from ..domain import loads
from .attachment_targets import attachment_target_kind, explicit_attachment_target_name
from .interface_contact_cache import resolve_contact_entities
from .ui.support import _create_harness_gateway, _require_active_design

_PIN_AND_VALUE = re.compile(r"^Pin (\S[^:]*): (.+)$")
_PIN_ONLY = re.compile(r"^Pin (\S+)$")


def _geometry_details(name: str) -> tuple[str, str]:
    """
    Split the recognizable Name Locals format, otherwise preserve a plain Value.
    """
    paired = _PIN_AND_VALUE.fullmatch(name)
    if paired:
        return paired.group(2), paired.group(1)
    pin_only = _PIN_ONLY.fullmatch(name)
    if pin_only:
        return "", pin_only.group(1)
    return name, ""


def import_interface_contact_geometry_names(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    selected_ids: tuple[UUID, ...],
    import_values: bool = True,
    import_pins: bool = False,
) -> str:
    """
    Fill selected empty fields from the preferred live geometry in one edit.

    An empty selection considers every contact. Existing fields stay intact.
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
    if not isinstance(import_values, bool) or not isinstance(import_pins, bool):
        raise ValueError("Geo Import options must be booleans.")
    if not import_values and not import_pins:
        raise ValueError("Geo Import requires Values, Pins, or both.")
    known = {contact.contact_id for contact in interface.contacts}
    if len(set(selected_ids)) != len(selected_ids) or not set(selected_ids).issubset(known):
        raise ValueError("Geo Import selection contains an invalid contact identity.")
    scope = set(selected_ids) if selected_ids else known
    details: dict[UUID, tuple[str, str]] = {}
    skipped: Counter[str] = Counter()
    for contact in interface.contacts:
        if contact.contact_id not in scope:
            continue
        if (not import_values or contact.name) and (not import_pins or contact.pin):
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
        value, pin = _geometry_details(name)
        if len(value) > 80 or len(pin) > 80:
            skipped["overlong name"] += 1
            continue
        if (import_values and value and not contact.name) or (
            import_pins and pin and not contact.pin
        ):
            details[contact.contact_id] = (value if import_values else "", pin)
    values_filled = pins_filled = 0
    if details:
        values_filled, pins_filled = fill_interface_contact_details(
            harness_id, interface_id, details, import_pins, gateway
        )
    if import_pins:
        notice = (
            f"Imported geometry Values for {values_filled} and Pins for {pins_filled} "
            f"of {len(scope)} Interface contacts."
        )
    else:
        notice = f"Imported geometry Values for {values_filled} of {len(scope)} Interface contacts."
    if skipped:
        reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(skipped.items()))
        notice += f" Skipped: {reasons}."
    return notice
