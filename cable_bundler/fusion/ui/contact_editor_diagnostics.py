"""
Validate and record privacy-bounded Contacts Editor lifecycle observations.
"""

from __future__ import annotations

import json

from .payloads import _read_palette_payload, _read_payload_uuid
from .support import _log_to_fusion

_EVENTS = frozenset(("open-request", "open-shown", "open-failed", "close", "close-suspended"))
_REASONS = frozenset(
    (
        "initial",
        "show-failed",
        "replaced",
        "button",
        "escape",
        "document-scope-changed",
        "interface-missing",
        "stale-contact-response",
        "auto-connect-target-pick",
        "auto-connect-target-preview",
        "auto-connect-target-cancelled",
        "unclassified",
    )
)


def record_contact_editor_lifecycle(serialized_data: str) -> str:
    """
    Log only known lifecycle fields, excluding contact values and geometry.
    """
    payload = _read_palette_payload(serialized_data)
    event = payload.get("event")
    reason = payload.get("reason")
    if (
        not isinstance(event, str)
        or not isinstance(reason, str)
        or event not in _EVENTS
        or reason not in _REASONS
    ):
        raise ValueError("Contacts Editor lifecycle event or reason is invalid.")
    instance = payload.get("instance")
    sequence = payload.get("sequence")
    elapsed_ms = payload.get("elapsedMs")
    contact_count = payload.get("contactCount")
    suspended_closes = payload.get("suspendedCloses")
    numbers = (instance, sequence, elapsed_ms, contact_count, suspended_closes)
    if any(type(value) is not int or value < 0 or value > 1_000_000_000 for value in numbers):
        raise ValueError("Contacts Editor lifecycle counters are invalid.")
    flags = ("open", "attached", "scopeMatches", "loaded", "requestPending", "targetPreview")
    if any(type(payload.get(key)) is not bool for key in flags):
        raise ValueError("Contacts Editor lifecycle flags are invalid.")
    observation = {
        "event": event,
        "reason": reason,
        "instance": instance,
        "sequence": sequence,
        "elapsedMs": elapsed_ms,
        "harnessId": str(_read_payload_uuid(payload, "harnessId", "harness")),
        "interfaceId": str(_read_payload_uuid(payload, "interfaceId", "Interface")),
        "contactCount": contact_count,
        "suspendedCloses": suspended_closes,
        **{key: payload[key] for key in flags},
    }
    _log_to_fusion(f"Contacts Editor lifecycle: {json.dumps(observation, sort_keys=True)}")
    return json.dumps({"ok": True})
