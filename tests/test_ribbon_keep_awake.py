"""
Verify owned wake assertions and release at every terminal tester boundary without real power changes.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_locked_solver.tester import awake
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification
from tests.fusion_ui_support import _PaletteLifecycleModule
from tests.test_ribbon_range_sequence import specification
from tests.test_ribbon_range_tester import make_tester


@pytest.fixture
def process(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    """
    Observe helper launch, parent watching and cleanup independently of the operating system.
    """
    child = Mock(pid=42)
    child.poll.return_value = None
    launch = Mock(return_value=child)
    monkeypatch.setattr(awake.sys, "platform", "darwin")
    monkeypatch.setattr(awake.subprocess, "Popen", launch)
    monkeypatch.setattr(awake.atexit, "register", Mock())
    monkeypatch.setattr(awake.atexit, "unregister", Mock())
    return child, launch


def test_one_owned_helper_uses_temporary_assertions_and_parent_watch(
    process: tuple[Mock, Mock],
) -> None:
    """
    Acquire once, hold display/idle sleep and release without changing global Mac preferences.
    """
    child, launch = process
    lease = awake.KeepAwake()
    assert not lease.state()["active"]
    lease.acquire()
    lease.acquire()
    assert launch.call_count == 1
    assert launch.call_args.args[0] == [
        "/usr/bin/caffeinate",
        "-d",
        "-i",
        "-w",
        str(awake.os.getpid()),
    ]
    assert lease.state() == {"active": True, "pid": 42}
    lease.release()
    lease.release()
    child.terminate.assert_called_once()
    child.wait.assert_called_once_with(timeout=1)
    assert not lease.state()["active"]


def test_slow_termination_is_killed_with_a_second_bounded_wait(process: tuple[Mock, Mock]) -> None:
    """
    Avoid leaving a power assertion behind when graceful helper termination stalls.
    """
    child, _ = process
    child.wait.side_effect = [subprocess.TimeoutExpired("caffeinate", 1), 0]
    lease = awake.KeepAwake()
    lease.acquire()
    lease.release()
    child.kill.assert_called_once()
    assert child.wait.call_count == 2 and lease.process is None


def test_failed_or_exited_helpers_are_never_reported_as_active(process: tuple[Mock, Mock]) -> None:
    """
    Surface a missing assertion instead of silently continuing an unattended run.
    """
    child, launch = process
    launch.side_effect = OSError("missing helper")
    lease = awake.KeepAwake()
    with pytest.raises(OSError):
        lease.acquire()
    assert lease.process is None
    launch.side_effect = None
    child.poll.return_value = 1
    with pytest.raises(RuntimeError, match="no longer running"):
        lease.acquire()
    assert not lease.state()["active"] and lease.process is None


def test_preference_is_optional_boolean_and_does_not_change_layout_sequence() -> None:
    """
    Read old plans without acquiring power assertions and preserve case inputs with either preference.
    """
    payload = specification()
    payload.pop("keep_awake", None)
    old = Specification.parse(payload)
    assert not old.keep_awake
    payload["keep_awake"] = True
    selected = Specification.parse(payload)
    assert selected.payload()["keep_awake"] is True
    assert [old.scene(i) for i in range(4)] == [selected.scene(i) for i in range(4)]
    payload["keep_awake"] = "yes"
    with pytest.raises(ValueError, match="keep the Mac awake"):
        Specification.parse(payload)


def runtime(tmp_path: Path, outcomes: list[str], enabled: bool) -> Any:
    """
    Bind the real scheduler and host dispatch to a fake wake manager and no native operations.
    """
    module = importlib.import_module("experiments.experiment_ribbon_locked_solver.tester.runtime")
    host: Any = object.__new__(module.Runtime)
    host.engine, _, _ = make_tester(tmp_path, outcomes)
    host.awake = Mock()
    host.awake.state.return_value = {"active": enabled, "pid": 42 if enabled else None}
    payload = specification()
    payload.update(keep_awake=enabled, maximum_cases=1)
    host.dispatch(
        "start",
        {
            "specification": payload,
            "selection": {
                "id": "guide-material-v2",
                "settings": {
                    "smoothing_percent": 0,
                    "material_uv": False,
                    "first_pass_optimization": True,
                },
            },
        },
    )
    return host


@pytest.mark.parametrize("outcome", ["completed", "unresolved"])
def test_completion_and_failure_release_the_assertion(
    addin_module: _PaletteLifecycleModule, tmp_path: Path, outcome: str
) -> None:
    """
    Release on the terminal poll, keeping protection across numerical/native work and between cases.
    """
    del addin_module
    host = runtime(tmp_path, [outcome], True)
    host.awake.acquire.assert_called_once()
    host.dispatch("poll", {})
    host.awake.release.assert_not_called()
    host.dispatch("poll", {})
    assert not host.engine.active
    host.awake.release.assert_called_once()


def test_stop_releases_immediately_while_worker_cancellation_is_pending(
    addin_module: _PaletteLifecycleModule, tmp_path: Path
) -> None:
    """
    A closing palette or Stop click removes wake protection without waiting for another UI poll.
    """
    del addin_module
    host = runtime(tmp_path, ["completed"], True)
    host.dispatch("poll", {})
    host.dispatch("stop", {})
    assert host.engine.phase == "stopping"
    host.awake.release.assert_called_once()
    host.dispatch("poll", {})
    assert not host.engine.active


def test_disabled_and_failed_wake_protection_never_silently_launch_work(
    addin_module: _PaletteLifecycleModule, tmp_path: Path
) -> None:
    """
    Leave an opt-out alone and stop before launching if a requested assertion is lost.
    """
    del addin_module
    disabled = runtime(tmp_path / "off", ["completed"], False)
    disabled.dispatch("poll", {})
    disabled.awake.acquire.assert_not_called()
    disabled.awake.check.assert_not_called()
    guarded = runtime(tmp_path / "on", ["completed"], True)
    guarded.awake.check.side_effect = RuntimeError("helper exited")
    guarded.dispatch("poll", {})
    assert not guarded.engine.active and guarded.engine.attempted == 0
    assert "Keep-awake stopped unexpectedly" in guarded.engine.reason
    guarded.awake.release.assert_called()


def test_launch_failure_stops_before_any_case_and_invalid_stop_keeps_an_active_lease(
    addin_module: _PaletteLifecycleModule, tmp_path: Path
) -> None:
    """
    Preserve an existing run on malformed input and latch an explicit helper-launch failure.
    """
    del addin_module
    host = runtime(tmp_path, ["completed"], True)
    with pytest.raises(ValueError, match="do not accept input edits"):
        host.dispatch("stop", {"unexpected": True})
    host.awake.release.assert_not_called()
    payload, selection = host.engine.specification.payload(), host.engine.selection
    host.dispatch("stop", {})
    host.awake.acquire.side_effect = OSError("helper launch failed")
    with pytest.raises(OSError, match="helper launch failed"):
        host.dispatch("start", {"specification": payload, "selection": selection})
    assert not host.engine.active and host.engine.attempted == 0
    assert host.engine.phase == "problem" and "Keep-awake could not start" in host.engine.reason


def test_native_palette_close_requests_stop_without_waiting_for_another_poll(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Wire Fusion's actual close-event contract to cancellation and immediate wake release.
    """
    del addin_module
    module = importlib.import_module("devtools.ribbon_analysis.inspection.palette_lifecycle")
    monkeypatch.setitem(vars(module.adsk.core), "UserInterfaceGeneralEventHandler", object)
    host = runtime(tmp_path, ["completed"], True)
    host.dispatch("poll", {})
    viewer = SimpleNamespace(tester=host, last_event_error=None)
    handler = module.closed_handler(viewer)
    handler.notify(None)
    assert host.engine.phase == "stopping"
    host.awake.release.assert_called_once()
    assert viewer.last_event_error is None
