"""
Verify native HTML-event conversion and acknowledgements through the palette boundary.
"""

from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def palette_module(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    Supply Fusion's generic-event cast without importing a live application.
    """
    core = ModuleType("adsk.core")
    core.HTMLEventHandler = object
    core.HTMLEventArgs = SimpleNamespace(cast=Mock())
    fusion = ModuleType("adsk.fusion")
    host = ModuleType("adsk")
    host.core, host.fusion = core, fusion
    for name, module in (("adsk", host), ("adsk.core", core), ("adsk.fusion", fusion)):
        monkeypatch.setitem(sys.modules, name, module)
    result = importlib.import_module("devtools.ribbon_analysis.inspection.fusion_view")
    monkeypatch.setitem(vars(result), "adsk", host)
    return result


def _incoming(module: Any, event: SimpleNamespace) -> tuple[Any, Mock]:
    """
    Bind one SDK event to a fresh viewer mock with observable callback state.
    """
    module.adsk.core.HTMLEventArgs.cast.return_value = event
    viewer = Mock(spec=module.DiagnosticViewer)
    viewer.received_requests, viewer.last_request = 0, None
    viewer.received_events = 0
    viewer.palette = Mock()
    return module.PaletteIncomingHandler(viewer), viewer


def test_generic_native_event_casts_before_reading_payload_and_returns_state(
    palette_module: Any,
) -> None:
    """
    A generic SDK event exposes its HTML payload only through HTMLEventArgs.cast.
    """
    outer = object()
    converted = SimpleNamespace(
        action="ribbon_inspection_section", data='{"index":8}', returnData=""
    )
    handler, viewer = _incoming(palette_module, converted)
    state = {"section": 8, "snapshot": {"identifier": "fixed"}}
    viewer.dispatch.return_value = state
    handler.notify(outer)
    palette_module.adsk.core.HTMLEventArgs.cast.assert_called_once_with(outer)
    viewer.dispatch.assert_called_once_with("section", {"index": 8})
    assert json.loads(converted.returnData) == {"ok": True, "state": state}
    assert (viewer.received_requests, viewer.last_request) == (1, "section")


def test_malformed_request_returns_error_and_next_native_request_can_succeed(
    palette_module: Any,
) -> None:
    """
    Reply on the cast SDK arguments after failure, leaving reconnection possible.
    """
    converted = SimpleNamespace(action="ribbon_inspection_section", data="null", returnData="")
    handler, viewer = _incoming(palette_module, converted)
    handler.notify(object())
    assert not json.loads(converted.returnData)["ok"]
    viewer.dispatch.assert_not_called()
    assert viewer.received_requests == 0
    converted.action, converted.data = "ribbon_inspection_ready", "{}"
    viewer.dispatch.return_value = {"solver": "reference"}
    handler.notify(object())
    assert json.loads(converted.returnData) == {"ok": True, "state": {"solver": "reference"}}
    assert (viewer.received_requests, viewer.last_request) == (1, "ready")


def test_native_html_response_notification_does_not_start_an_event_loop(
    palette_module: Any,
) -> None:
    """
    Fusion's response notification is an acknowledgement, not a new JSON command.
    """
    converted = SimpleNamespace(action="response", data="OK", returnData="")
    handler, viewer = _incoming(palette_module, converted)
    handler.notify(object())
    viewer.dispatch.assert_not_called()
    viewer.palette.sendInfoToHTML.assert_not_called()
    assert viewer.received_requests == 0
