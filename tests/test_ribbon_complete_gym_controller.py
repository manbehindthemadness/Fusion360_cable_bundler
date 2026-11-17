"""
Check one-shot manual worker ownership and interrupted-prefix collection without Fusion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from experiments.experiment_ribbon_complete_gym import controller, lock
from tests.test_ribbon_complete_gym_job import scene


class Process:
    """
    Represent one owned subprocess whose exit is explicitly controlled by the test.
    """

    def __init__(self) -> None:
        """
        Begin active without spawning external work.
        """
        self.returncode: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        """
        Return the retained exit state without changing it.
        """
        return self.returncode

    def terminate(self) -> None:
        """
        Record termination of this owned worker only.
        """
        self.terminated = True
        self.returncode = -15


@pytest.fixture
def owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[controller.Controller, Process, list[Any]]:
    """
    Replace the subprocess and input-freezer boundary while retaining lifecycle and files.
    """
    monkeypatch.setattr(lock, "ROOT", tmp_path)
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []
    process = Process()

    def freeze(*args: Any) -> Path:
        """
        Record immutable input completion before the external launch boundary.
        """
        directory = args[2]
        directory.mkdir(parents=True)
        path = directory / "plan.json"
        path.write_text("{}")
        calls.append("frozen")
        return path

    def launch(*args: Any, **kwargs: Any) -> Process:
        """
        Refuse launch before inputs exist, without running an interpreter.
        """
        assert calls == ["frozen"]
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(controller.job, "freeze", freeze)
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    value = controller.Controller(python, tmp_path / "artifacts/verification/gym/jobs")
    return value, process, calls


def test_start_freezes_first_refuses_overlap_and_collects_once_with_interrupted_tail(
    owner: tuple[controller.Controller, Process, list[Any]],
) -> None:
    """
    Polling and a truncated optional tail cannot relaunch or erase a completed material event.
    """
    value, process, calls = owner
    assert value.poll() == {"status": "idle"} and not calls
    value.start(scene(), 1e-5)
    assert value.poll()["status"] == "running" and len(calls) == 2
    with pytest.raises(ValueError, match="active"):
        value.start(scene(), 1e-5)
    assert value.job is not None
    (value.job / "result.json").write_text(json.dumps({"status": "planned_material_violation"}))
    (value.job / "events.jsonl").write_text(
        '{"stage":"complete_material_witness","findings":[]}\n{"stage"'
    )
    process.returncode = 0
    result = value.poll()
    assert result["status"] == "planned_material_violation" and result["material"]["findings"] == []
    assert value.process is None and value.log is None
    assert value.poll() == result and len(calls) == 2


def test_cancellation_is_idempotent_and_missing_receipt_stays_stopped(
    owner: tuple[controller.Controller, Process, list[Any]],
) -> None:
    """
    A worker with no final report contributes a stop, never a geometry success or retry.
    """
    value, process, calls = owner
    value.start(scene(), 1e-5)
    value.cancel()
    value.cancel()
    assert value.job is not None and (value.job / "cancel").exists()
    process.returncode = -15
    result = value.poll()
    assert result["status"] == "stopped" and "partial files retained" in result["error"]
    assert len(calls) == 2


def test_watchdog_terminates_only_after_cancellation_grace(
    owner: tuple[controller.Controller, Process, list[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The UI watchdog cannot turn an unresponsive worker into an automatic replacement run.
    """
    value, process, calls = owner
    value.start(scene(), 1e-5)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_complete_gym.controller.perf_counter",
        lambda: value.started + 16,
    )
    assert value.poll()["status"] == "cancelling" and not process.terminated
    monkeypatch.setattr(
        "experiments.experiment_ribbon_complete_gym.controller.perf_counter",
        lambda: value.started + 19,
    )
    assert value.poll()["status"] == "stopped" and process.terminated
    assert len(calls) == 2


def test_source_lock_rejects_changed_bytes_and_paths_outside_its_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A plausible source filename cannot bypass exact code identity or owned-root scope.
    """
    monkeypatch.setattr(lock, "ROOT", tmp_path)
    path = tmp_path / "source.py"
    path.write_text("original")
    pins = {"source.py": lock.manifest.digest(path)}
    lock.verify(pins)
    path.write_text("changed")
    with pytest.raises(RuntimeError, match="source drift"):
        lock.verify(pins)
    with pytest.raises(RuntimeError, match="source drift"):
        lock.verify({"../outside.py": "irrelevant"})
