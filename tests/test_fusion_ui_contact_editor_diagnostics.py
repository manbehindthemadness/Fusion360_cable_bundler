"""
Regress the bounded Fusion log contract for Contacts Editor lifecycle events.
"""

from __future__ import annotations

import importlib
import json

import pytest

from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.fixture
def lifecycle_payload() -> dict[str, object]:
    """
    Provide one valid observation with fields that must never reach the log.
    """
    return {
        "event": "close",
        "reason": "document-scope-changed",
        "instance": 2,
        "sequence": 3,
        "elapsedMs": 90,
        "harnessId": "00000000-0000-0000-0000-000000000001",
        "interfaceId": "00000000-0000-0000-0000-000000000002",
        "contactCount": 4,
        "suspendedCloses": 0,
        "open": False,
        "attached": True,
        "scopeMatches": False,
        "loaded": True,
        "requestPending": False,
        "targetPreview": False,
        "contactValues": ["private pin value"],
    }


def test_lifecycle_dispatch_logs_only_bounded_fields_even_for_stale_document(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_payload: dict[str, object],
) -> None:
    """
    Record a closing editor after document scope changes without dumping contents.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    diagnostics = importlib.import_module("cable_bundler.fusion.ui.contact_editor_diagnostics")
    messages: list[str] = []
    monkeypatch.setitem(diagnostics.__dict__, "_log_to_fusion", messages.append)
    monkeypatch.setitem(
        palette_module.__dict__,
        "_stale_palette_document_request",
        lambda *_args: (_ for _ in ()).throw(AssertionError("stale guard must be bypassed")),
    )

    result = palette_module._dispatch_palette_action(
        object(), "log_contact_editor_lifecycle", json.dumps(lifecycle_payload)
    )

    assert json.loads(result) == {"ok": True}
    assert len(messages) == 1
    assert '"reason": "document-scope-changed"' in messages[0]
    assert "private pin value" not in messages[0]
    assert "contactValues" not in messages[0]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("event", ["close"]),
        ("reason", "unknown"),
        ("sequence", True),
        ("contactCount", -1),
        ("open", "false"),
        ("interfaceId", "not-a-uuid"),
    ],
)
def test_lifecycle_rejects_malformed_observations(
    addin_module: _PaletteLifecycleModule,
    lifecycle_payload: dict[str, object],
    key: str,
    value: object,
) -> None:
    """
    Reject malformed local bridge payloads before they enter the Fusion log.
    """
    diagnostics = importlib.import_module("cable_bundler.fusion.ui.contact_editor_diagnostics")
    lifecycle_payload[key] = value

    with pytest.raises(ValueError):
        diagnostics.record_contact_editor_lifecycle(json.dumps(lifecycle_payload))
