"""
Bound contact-resolution reuse to one active design and a finite number of proxies.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

MAX_CONTACT_RESOLUTIONS = 512
MAX_RESOLUTIONS_PER_TOKEN = 16
_entries: OrderedDict[str, tuple[Any, ...]] = OrderedDict()
_design_key = ""


def clear_contact_resolutions() -> None:
    """
    Release all Fusion references after geometry edits, document transitions, or stop.
    """
    global _design_key
    _entries.clear()
    _design_key = ""


def _activate(design: Any) -> bool:
    """
    Scope entries by root identity without retaining the Design or Document wrapper.
    """
    global _design_key
    key = getattr(getattr(design, "rootComponent", None), "entityToken", "")
    if not isinstance(key, str) or not key:
        clear_contact_resolutions()
        return False
    if key != _design_key:
        clear_contact_resolutions()
        _design_key = key
    return True


def remember_contact_entity(design: Any, entity: Any) -> None:
    """
    Reuse an explicitly picked, unambiguous entity without re-resolving its token.
    """
    if _activate(design):
        _store(entity.entityToken, (entity,))


def _store(token: str, entities: tuple[Any, ...]) -> None:
    """
    Bound both entry count and ambiguous-token fanout; never retain missing entities.
    """
    if not entities or len(entities) > MAX_RESOLUTIONS_PER_TOKEN:
        return
    _entries[token] = entities
    _entries.move_to_end(token)
    while len(_entries) > MAX_CONTACT_RESOLUTIONS:
        _entries.popitem(last=False)


def resolve_contact_entities(design: Any, token: str) -> tuple[Any, ...]:
    """
    Resolve a contact once per design epoch, checking cached proxy validity on use.
    """
    cacheable = _activate(design)
    found = _entries.get(token) if cacheable else None
    if found is not None:
        try:
            valid = all(entity.isValid for entity in found)
        except (AttributeError, RuntimeError):
            valid = False
        if valid:
            _entries.move_to_end(token)
            return found
        _entries.pop(token, None)
    found = tuple(design.findEntityByToken(token) or ())
    if cacheable:
        _store(token, found)
    return found
