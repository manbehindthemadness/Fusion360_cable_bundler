"""
Verify explicit gym-output deletion preserves unrelated geometry and diagnostic history.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import generate
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.fixture
def native_host(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Any]:
    """
    Import the native boundary against Fusion stubs with an explicitly owned idle document.
    """
    del addin_module
    module: Any = importlib.import_module("experiments.experiment_ribbon_locked_solver.native")
    app = SimpleNamespace(
        activeDocument=SimpleNamespace(creationId="owned"),
        userInterface=SimpleNamespace(activeCommand="SelectCommand"),
    )
    monkeypatch.setitem(vars(module.adsk.core), "Application", SimpleNamespace(get=lambda: app))
    return module, app


def test_clear_removes_only_latest_output_and_is_repeatable(native_host: tuple[Any, Any]) -> None:
    """
    Delete the retained occurrence once, leaving earlier bodies and numerical records untouched.
    """
    module, _ = native_host
    owner: Any = module.NativeOwner("owned")
    latest = SimpleNamespace(
        isValid=True,
        component=SimpleNamespace(bRepBodies=SimpleNamespace(count=1)),
        deleteMe=Mock(return_value=True),
    )
    owner.displayed = latest
    assert owner.has_geometry()
    owner.clear()
    assert not owner.has_geometry()
    owner.clear()
    latest.deleteMe.assert_called_once_with()
    assert owner.displayed is None


@pytest.mark.parametrize("kind", ("document", "command", "delete"))
def test_clear_rejects_wrong_context_or_failed_deletion_without_losing_handle(
    native_host: tuple[Any, Any], kind: str
) -> None:
    """
    Keep output ownership intact when Fusion cannot safely complete an explicit clear action.
    """
    module, app = native_host
    owner: Any = module.NativeOwner("owned")
    occurrence = SimpleNamespace(isValid=True, deleteMe=Mock(return_value=False))
    owner.displayed = occurrence
    if kind == "document":
        app.activeDocument.creationId = "unrelated"
    elif kind == "command":
        app.userInterface.activeCommand = "SomeUserCommand"
    with pytest.raises(RuntimeError):
        owner.clear()
    assert owner.displayed is occurrence
    assert occurrence.deleteMe.call_count == (1 if kind == "delete" else 0)


def test_externally_deleted_output_is_harmless(native_host: tuple[Any, Any]) -> None:
    """
    Drop an invalid retained occurrence without attempting a second native deletion.
    """
    module, _ = native_host
    owner: Any = module.NativeOwner("owned")
    occurrence = SimpleNamespace(isValid=False, deleteMe=Mock())
    owner.displayed = occurrence
    assert not owner.has_geometry()
    owner.clear()
    occurrence.deleteMe.assert_not_called()
    assert owner.displayed is None


def test_rejected_inspection_uses_normal_output_ownership(
    native_host: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    A rejected body participates in hide/clear without becoming accepted output.
    """
    module, _ = native_host
    owner = module.NativeOwner("owned")
    occurrence = SimpleNamespace(
        isValid=True,
        isLightBulbOn=False,
        component=SimpleNamespace(bRepBodies=SimpleNamespace(count=1)),
        deleteMe=Mock(return_value=True),
    )
    result = {"built": 1, "accepted": False}
    monkeypatch.setitem(vars(module), "build_rejected", Mock(return_value=(occurrence, result)))
    assert owner.inspect_rejected(tmp_path) is result
    assert owner.has_geometry() and owner.rejected_job == tmp_path.resolve()
    owner.hide()
    assert not occurrence.isLightBulbOn
    owner.clear()
    assert not owner.has_geometry() and owner.rejected_job is None


def test_closed_progress_view_does_not_abort_native_stage_logging(
    native_host: tuple[Any, Any], tmp_path: Path
) -> None:
    """
    Preserve durable progress when optional palette delivery fails during native construction.
    """
    from experiments.experiment_ribbon_locked_solver import progress

    module, _ = native_host
    view_module = importlib.import_module("devtools.ribbon_analysis.inspection.fusion_view")
    viewer: Any = view_module.DiagnosticViewer.__new__(view_module.DiagnosticViewer)
    viewer.palette = SimpleNamespace(
        isValid=True, sendInfoToHTML=Mock(side_effect=RuntimeError("closed"))
    )
    viewer.last_event_error = None
    owner: Any = module.NativeOwner("owned")
    owner.on_progress = viewer.report_progress
    owner._progress(tmp_path, "native", "Building body")
    assert progress.read(tmp_path)[-1]["message"] == "Building body"
    assert "closed" in viewer.last_event_error


@pytest.mark.parametrize("status", ("running", "cancelling", "idle"))
def test_viewer_clear_dispatch_preserves_session_and_blocks_active_work(
    native_host: tuple[Any, Any], status: str
) -> None:
    """
    Dispatch only an empty explicit action, preserving recorded targets, methods and latest job.
    """
    del native_host
    module = importlib.import_module("devtools.ribbon_analysis.inspection.fusion_view")
    viewer: Any = module.DiagnosticViewer.__new__(module.DiagnosticViewer)
    scene = generate()
    session = SimpleNamespace(
        targets=scene.targets,
        gym=scene.payload(),
        section=0,
        state=Mock(return_value={"solver": "recorded"}),
    )
    viewer.session = session
    viewer.runner = SimpleNamespace(state=lambda: {"status": status})
    viewer.tester = None
    viewer.on_gym = None
    viewer._visibility = {}
    viewer._sections = []
    viewer.palette = SimpleNamespace(sendInfoToHTML=Mock())
    available = [True]

    def clear() -> None:
        """
        Model the owner releasing its latest native output without editing replay state.
        """
        available[0] = False

    callback = Mock(side_effect=clear)
    viewer.enable_geometry_clear(callback, lambda: available[0])
    if status != "idle":
        with pytest.raises(ValueError, match="active job"):
            viewer.dispatch("clear_geometry", {})
        callback.assert_not_called()
    else:
        with pytest.raises(ValueError, match="callback"):
            viewer.dispatch("clear_geometry", {"all": True})
        callback.assert_not_called()
        state = viewer.dispatch("clear_geometry", {})
        callback.assert_called_once_with()
        assert state["geometry_clear_available"] is False
        assert state["solver"] == "recorded" and viewer.session is session
