"""
Verify read-only readiness and native callback acknowledgement preservation without Fusion.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    Load a separate presentation module against only a mocked native API boundary.
    """
    native = ModuleType("adsk")
    monkeypatch.setitem(sys.modules, "adsk", native)
    for part in ("core", "fusion"):
        module = ModuleType(f"adsk.{part}")
        setattr(native, part, module)
        monkeypatch.setitem(sys.modules, module.__name__, module)
    native.core.HTMLEventHandler = object
    native.core.HTMLEventArgs = SimpleNamespace(cast=lambda value: value)
    name = "devtools.ribbon_analysis.construction._bridge_test"
    source = Path(__file__).parents[1] / "devtools/ribbon_analysis/construction/host.py"
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("data", ["{}", "[]", '{"index":1}'])
def test_readiness_never_draws_geometry(bridge: Any, data: str) -> None:
    """
    A bounded startup retry validates ownership and acknowledges without replaying a scene.
    """
    viewer = SimpleNamespace(guard=Mock(), draw=Mock(), index=7, last_error=None)
    event = SimpleNamespace(action="construction_ready", data=data, returnData="")
    bridge.Incoming(viewer).notify(event)
    response = json.loads(event.returnData)
    viewer.draw.assert_not_called()
    if data == "{}":
        viewer.guard.assert_called_once_with()
        assert response == {"ok": True, "index": 7}
        assert viewer.last_error is None
    else:
        viewer.guard.assert_not_called()
        assert "Malformed" in response["error"]


def test_native_callback_preserves_acknowledgement(bridge: Any) -> None:
    """
    The retained native callback passes the original event through the presentation policy.
    """
    palette = SimpleNamespace(incomingFromHTML=SimpleNamespace(add=Mock(return_value=True)))
    viewer = SimpleNamespace(guard=Mock(), draw=Mock(), index=2, last_error=None)
    handler = bridge.bind(palette, bridge.Incoming(viewer))
    event = SimpleNamespace(action="construction_ready", data="{}", returnData="")
    handler.notify(event)
    assert json.loads(event.returnData) == {"ok": True, "index": 2}
    viewer.draw.assert_not_called()
    palette.incomingFromHTML.add.assert_called_once_with(handler)


@pytest.mark.parametrize("auto_zoom", [False, True])
@pytest.mark.parametrize("changed", [False, True])
def test_navigation_preserves_camera_when_auto_zoom_is_off(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, auto_zoom: bool, changed: bool
) -> None:
    """
    Every step refreshes its frozen scene, while camera fitting remains explicitly optional.
    """
    viewport = SimpleNamespace(fit=Mock(), refresh=Mock())
    bridge.adsk.core.Application = SimpleNamespace(
        get=Mock(return_value=SimpleNamespace(activeViewport=viewport))
    )
    monkeypatch.setitem(
        vars(bridge), "budget", Mock(return_value=SimpleNamespace(check=Mock(), samples=[]))
    )
    viewer = bridge.Viewer.__new__(bridge.Viewer)
    viewer.guard = Mock()
    viewer.packet = {"steps": [{"scene": [], "status": "reference"}] * 2, "features": {}}
    viewer.index = 0 if changed else 1
    viewer.auto_zoom = auto_zoom
    viewer.group = Mock(deleteMe=Mock(return_value=True))
    viewer.component = SimpleNamespace(customGraphicsGroups=SimpleNamespace(add=Mock()))
    viewer.draw(1)
    assert viewer.index == 1
    assert viewport.fit.call_count == int(changed and auto_zoom)
    viewport.refresh.assert_called_once_with()


@pytest.mark.parametrize("enabled", [False, True])
def test_selection_carries_auto_zoom_preference(bridge: Any, enabled: bool) -> None:
    """
    The shared navigation request carries a strict boolean before drawing the requested scene.
    """
    viewer = SimpleNamespace(draw=Mock(), index=2, auto_zoom=not enabled, last_error=None)
    event = SimpleNamespace(
        action="construction_select",
        data=json.dumps({"index": 2, "feature": "", "auto_zoom": enabled}),
        returnData="",
    )
    bridge.Incoming(viewer).notify(event)
    assert viewer.auto_zoom is enabled
    viewer.draw.assert_called_once_with(2, "")
    assert json.loads(event.returnData)["ok"] is True
