"""
Initialize the embedded viewport after visibility and keep layout reports separate from geometry actions.
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
    Mock only the native event boundary; do not import or reload the live spatial inspector.
    """
    core = ModuleType("adsk.core")
    core.HTMLEventHandler = object
    core.HTMLEventArgs = SimpleNamespace(cast=Mock())
    host = ModuleType("adsk")
    host.core = core
    monkeypatch.setitem(sys.modules, "adsk", host)
    monkeypatch.setitem(sys.modules, "adsk.core", core)
    result = importlib.import_module(
        "experiments.experiment_ribbon_spatial_inspection.palette_layout"
    )
    monkeypatch.setitem(vars(result), "adsk", host)
    return result


class _Surface:
    """
    Model a native child browser that starts tiny and ignores size assignments made while hidden.
    """

    def __init__(self) -> None:
        """
        Keep separate native-window and embedded-browser bounds.
        """
        self._visible = False
        self._width, self._height = 1100, 900
        self.browser_width = self.browser_height = 0

    def _get_visible(self) -> bool:
        """
        Expose only the SDK presentation property used by initialization.
        """
        return self._visible

    def _set_visible(self, value: bool) -> None:
        """
        Create the tiny child surface on first visibility, matching the observed host failure.
        """
        if value and not self._visible:
            self.browser_width, self.browser_height = 150, 30
        self._visible = value

    isVisible = property(_get_visible, _set_visible)

    @property
    def width(self) -> int:
        """
        Return the owned native window width.
        """
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        """
        Apply browser sizing only after the child surface exists.
        """
        self._width = value
        if self._visible:
            self.browser_width = value

    @property
    def height(self) -> int:
        """
        Return the owned native window height.
        """
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        """
        Apply browser sizing only after the child surface exists.
        """
        self._height = value
        if self._visible:
            self.browser_height = value


def _report() -> dict[str, Any]:
    """
    Retain viewport/paint diagnostics without any geometry or executable command fields.
    """
    return {
        "fingerprint": "a" * 64,
        "viewport_width": 1000,
        "viewport_height": 850,
        "painted_views": 4,
        "canvases": [
            {"view": name, "width": 450, "height": 260, "pixel_width": 900, "pixel_height": 520}
            for name in ("top", "front", "side", "iso")
        ],
    }


def test_first_open_sizes_the_browser_without_collapsing(palette_module: Any) -> None:
    """
    Final native bounds reach a newly visible child instead of leaving its tiny initial viewport.
    """
    surface = _Surface()
    palette_module.show(surface, 1000, 850)
    assert surface.isVisible and (surface.browser_width, surface.browser_height) == (1000, 850)
    surface.width, surface.height = 1620, 1050
    palette_module.refresh(surface)
    assert (surface.width, surface.height, surface.browser_width, surface.browser_height) == (
        1620,
        1050,
        1620,
        1050,
    )


@pytest.mark.parametrize("action", ("ribbon_spatial", "response", "unknown"))
def test_existing_bridge_actions_are_delegated_unchanged(palette_module: Any, action: str) -> None:
    """
    The layout adapter cannot execute, reinterpret or suppress selection/prediction/probe guards.
    """
    event = SimpleNamespace(action=action, data='{"action":"probe","data":{}}', returnData="")
    palette_module.adsk.core.HTMLEventArgs.cast.return_value = event
    original = Mock()
    wrapper = palette_module.LayoutIncoming(original)
    outer = object()
    wrapper.notify(outer)
    original.notify.assert_called_once_with(outer)
    assert wrapper.last_layout is None and wrapper.layout_reports == 0


def test_first_tiny_browser_report_refreshes_once_and_recovers(palette_module: Any) -> None:
    """
    A child initialized asynchronously gets one size correction after its first paint, never a retry loop.
    """
    surface = _Surface()
    surface.isVisible = True
    original = Mock()
    wrapper = palette_module.LayoutIncoming(original, surface)
    report = _report()
    report.update(viewport_width=150, viewport_height=30)
    event = SimpleNamespace(action="ribbon_spatial_layout", data=json.dumps(report), returnData="")
    palette_module.adsk.core.HTMLEventArgs.cast.return_value = event
    wrapper.notify(object())
    assert wrapper.surface_refreshes == 1 and json.loads(event.returnData) == {"ok": True}
    assert (surface.browser_width, surface.browser_height) == (1100, 900)
    wrapper.notify(object())
    assert wrapper.surface_refreshes == 1
    event.data = json.dumps(_report())
    wrapper.notify(object())
    assert wrapper.layout_reports == 3 and wrapper.last_layout["painted_views"] == 4
    assert wrapper.last_layout_error is None
    original.notify.assert_not_called()


@pytest.mark.parametrize(
    "kind", ("null", "nan", "negative", "duplicate", "unknown", "paint_count", "fingerprint")
)
def test_malformed_layout_cannot_mutate_geometry_and_a_later_report_recovers(
    palette_module: Any, kind: str
) -> None:
    """
    Validate external metadata and preserve the acknowledged geometry bridge after invalid input.
    """
    report: Any = _report()
    if kind == "null":
        report = None
    elif kind == "nan":
        report["viewport_width"] = float("nan")
    elif kind == "negative":
        report["canvases"][0]["width"] = -1
    elif kind in ("duplicate", "unknown"):
        report["canvases"][1]["view"] = "top" if kind == "duplicate" else "bogus"
    elif kind == "paint_count":
        report["painted_views"] = 5
    else:
        report["fingerprint"] = None
    event = SimpleNamespace(action="ribbon_spatial_layout", data=json.dumps(report), returnData="")
    palette_module.adsk.core.HTMLEventArgs.cast.return_value = event
    original = Mock()
    wrapper = palette_module.LayoutIncoming(original)
    wrapper.notify(object())
    assert "error" in json.loads(event.returnData) and wrapper.last_layout is None
    event.data = json.dumps(_report())
    wrapper.notify(object())
    assert json.loads(event.returnData) == {"ok": True} and wrapper.layout_reports == 1
    original.notify.assert_not_called()
