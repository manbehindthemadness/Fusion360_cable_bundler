"""
Verify native HTML-event conversion and acknowledgements through the palette boundary.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.gym.handoff import identity
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_diagnostic_viewer import examples


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


def test_switching_examples_retains_each_session_and_its_selected_section(
    palette_module: Any, tmp_path: Path
) -> None:
    """
    Preserve per-example history/selection while hiding the previous native inventory.
    """
    single = examples.create(tmp_path / "single", "single", lambda: None)
    ribbon = examples.create(tmp_path / "ribbon", "ribbon", lambda: None)
    viewer: Any = object.__new__(palette_module.DiagnosticViewer)
    viewer.session = Session(single)
    viewer.session.select_section(16)
    original = viewer.session
    old_occurrence = SimpleNamespace(isValid=True, isLightBulbOn=True)
    viewer._methods = {"reference": old_occurrence}
    viewer._sessions = {single.resolve(): (original, viewer._methods)}
    viewer.runner = Mock()
    viewer.runner.open_example.side_effect = [ribbon, single]
    viewer._register_method = Mock(
        side_effect=lambda item: viewer._methods.update({item["id"]: Mock()})
    )
    viewer._draw = Mock()
    viewer._open_example("ribbon")
    assert viewer.session.targets.lines == 3 and not old_occurrence.isLightBulbOn
    viewer._open_example("single")
    assert viewer.session is original and viewer.session.section == 16
    assert len(viewer._sessions) == 2


@pytest.mark.parametrize("visible", (True, False))
def test_linking_gym_keeps_existing_context_owned_across_repeated_layout_changes(
    palette_module: Any, monkeypatch: pytest.MonkeyPatch, visible: bool
) -> None:
    """
    Re-linking navigation must not orphan a drawn context or reset manual layer visibility.
    """
    viewer: Any = object.__new__(palette_module.DiagnosticViewer)
    scene = generate()
    viewer.root = object()
    viewer.session = SimpleNamespace(
        solver="input", snapshot=None, gym=scene.payload(), targets=scene.targets
    )
    viewer._gym_group = Mock(isValid=True)
    original = viewer._gym_group
    viewer._gym_id = identity(scene.payload())
    viewer._visibility = {"gym": visible}
    viewer._scene = viewer._solver_sketch = None
    viewer._methods = {"input": SimpleNamespace(isValid=True, component=object())}
    viewer._apply_visibility = Mock()
    viewer._budget = Mock(return_value=SimpleNamespace(check=Mock(), memory=lambda: 0))
    monkeypatch.setitem(vars(palette_module), "retain_end_profiles", Mock())
    replacements = [Mock(isValid=True), Mock(isValid=True)]
    draw = Mock(side_effect=replacements)
    monkeypatch.setitem(vars(palette_module), "draw_gym", draw)
    callback = Mock()
    viewer.enable_gym(callback)
    viewer.enable_gym(callback)
    viewer._draw()
    assert viewer._gym_group is original
    assert viewer.on_gym is callback
    assert viewer._visibility["gym"] is visible
    draw.assert_not_called()
    for seed in (42, 43):
        scene = generate(Config(seed=seed))
        viewer.session.gym, viewer.session.targets = scene.payload(), scene.targets
        viewer._draw()
    assert draw.call_count == 2
    original.deleteMe.assert_called_once_with()
    replacements[0].deleteMe.assert_called_once_with()
    replacements[1].deleteMe.assert_not_called()
    assert viewer._gym_group is replacements[1]


@pytest.mark.parametrize("running", (True, False))
def test_retiring_workspace_hides_only_its_views_without_interrupting_jobs(
    palette_module: Any, running: bool
) -> None:
    """
    Retire explicit owned view handles only after job completion, retaining their data.
    """
    del palette_module
    module = importlib.import_module("experiments.experiment_ribbon_test_gym.workspace")
    workspace: Any = object.__new__(module.Workspace)
    runner = Mock()
    runner.state.return_value = {"status": "running" if running else "completed"}
    workspace.diagnostics = SimpleNamespace(
        runner=runner, palette=Mock(isValid=True, isVisible=True)
    )
    workspace.gym = SimpleNamespace(palette=Mock(isValid=True, isVisible=True))
    workspace.diagnostic_occurrence = Mock(isValid=True, isLightBulbOn=True)
    workspace.gym_occurrence = Mock(isValid=True, isLightBulbOn=True)
    if running:
        with pytest.raises(ValueError, match="active job"):
            workspace.deactivate()
        assert workspace.diagnostic_occurrence.isLightBulbOn
        assert workspace.gym.palette.isVisible
    else:
        workspace.deactivate()
        assert not workspace.diagnostic_occurrence.isLightBulbOn
        assert not workspace.gym_occurrence.isLightBulbOn
        assert not workspace.diagnostics.palette.isVisible
        assert not workspace.gym.palette.isVisible
        workspace.diagnostic_occurrence.deleteMe.assert_not_called()
    runner.cancel.assert_not_called()
