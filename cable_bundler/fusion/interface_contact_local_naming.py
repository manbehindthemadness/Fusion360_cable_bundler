"""
Copy saved Interface contact metadata to uniquely owned local Fusion names.
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ..domain import AttachmentTargetKind, InterfaceContact, loads
from .attachment_targets import attachment_target_kind
from .interface_contact_cache import resolve_contact_entities
from .ui.support import _create_harness_gateway, _require_active_design


def _name_owner(entity: object, kind: AttachmentTargetKind) -> object | None:
    """
    Return the Fusion object whose name represents this contact geometry.
    """
    if kind in (AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE):
        return getattr(entity, "body", None)
    if kind in (AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT):
        return getattr(entity, "parentSketch", None)
    return entity


def _local_owner(entity: object, kind: AttachmentTargetKind) -> tuple[str, object] | None:
    """
    Resolve one stable, editable-document owner without crossing a link.
    """
    owner = _name_owner(entity, kind)
    if owner is None:
        return None
    occurrence = getattr(owner, "assemblyContext", None) or getattr(entity, "assemblyContext", None)
    if getattr(occurrence, "isReferencedComponent", False):
        return None
    native = getattr(owner, "nativeObject", None) or owner
    if getattr(native, "isReadOnly", False):
        return None
    token = getattr(native, "entityToken", None)
    if not isinstance(token, str) or not token:
        return None
    return token, native


def _resolved_owner(design: object, contact: InterfaceContact) -> tuple[str, object] | None:
    """
    Require one live entity, treating unavailable host proxies as skips.
    """
    try:
        entities = tuple(
            entity
            for entity in resolve_contact_entities(design, contact.entity_token)
            if attachment_target_kind(entity) is contact.kind
        )
        if len(entities) != 1:
            return None
        return _local_owner(entities[0], contact.kind)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _local_name(
    contact: InterfaceContact, include_values: bool = True, include_pins: bool = True
) -> str:
    """
    Format only selected saved fields without deriving either from geometry.
    """
    pin = contact.pin.strip() if include_pins else ""
    value = contact.name.strip() if include_values else ""
    if pin and value:
        return f"Pin {pin}: {value}"
    return f"Pin {pin}" if pin else value


def name_interface_contact_locals(
    application: adsk.core.Application,
    harness_id: UUID,
    interface_id: UUID,
    selected_ids: tuple[UUID, ...],
    include_values: bool = True,
    include_pins: bool = True,
) -> str:
    """
    Rename only unique local owners, skipping links and read-only geometry.

    An empty selection scopes every contact in the Interface. Sharing is checked
    across every saved Interface in this harness before any name is assigned.
    """
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if interface is None:
        raise ValueError("Selected Interface no longer exists.")
    if not isinstance(include_values, bool) or not isinstance(include_pins, bool):
        raise ValueError("Name Locals options must be booleans.")
    if not include_values and not include_pins:
        raise ValueError("Name Locals requires Values, Pins, or both.")
    known = {contact.contact_id for contact in interface.contacts}
    if len(selected_ids) != len(set(selected_ids)) or not set(selected_ids).issubset(known):
        raise ValueError("Name Locals selection contains an invalid contact identity.")
    scope = set(selected_ids) if selected_ids else known
    owners = {
        (item.interface_id, contact.contact_id): _resolved_owner(design, contact)
        for item in definition.interfaces
        for contact in item.contacts
    }
    sharing = Counter(owner[0] for owner in owners.values() if owner is not None)
    renamed = 0
    unchanged = 0
    skipped: Counter[str] = Counter()
    for contact in interface.contacts:
        if contact.contact_id not in scope:
            continue
        desired = _local_name(contact, include_values, include_pins)
        if not desired:
            skipped["no selected Pin or Value"] += 1
            continue
        resolved = owners[(interface_id, contact.contact_id)]
        if resolved is None:
            skipped["unresolved or non-editable geometry"] += 1
            continue
        token, owner = resolved
        if sharing[token] != 1:
            skipped["shared geometry"] += 1
            continue
        try:
            previous = getattr(owner, "name", None)
            if not isinstance(previous, str):
                skipped["no writable name"] += 1
                continue
            if previous == desired:
                unchanged += 1
                continue
            owner.name = desired
            if owner.name != desired:
                skipped["name write rejected"] += 1
                continue
        except (AttributeError, RuntimeError, TypeError, ValueError):
            skipped["name write rejected"] += 1
            continue
        renamed += 1
    notice = f"Named {renamed} local geometries; {unchanged} already matched."
    if skipped:
        reasons = ", ".join(f"{count} {reason}" for reason, count in sorted(skipped.items()))
        notice += f" Skipped: {reasons}."
    return notice
