"""
Verify selected solver dispatch freezes gym inputs and never revives retired discovery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, generate
from devtools.ribbon_analysis.gym.handoff import freeze
from experiments.experiment_ribbon_locked_solver import VERSION, controller, lock
from experiments.experiment_ribbon_locked_solver.lock import ROOT
from experiments.experiment_ribbon_locked_solver.versions import V2


def _controller(tmp_path: Path) -> tuple[controller.Controller, Mock]:
    """
    Use the actual configured module SDK path but mock all subprocess/native boundaries.
    """
    native = Mock(return_value={"status": "built_and_named_fidelity_checks_pass"})
    runner = controller.Controller(
        ROOT / ".venv/bin/python", tmp_path / "runs", "owned-test-design", native
    )
    return runner, native


@pytest.mark.parametrize("optimization", (True, False))
@pytest.mark.parametrize("version,hardware", ((VERSION, False), (V2, False), (V2, True)))
def test_selected_run_freezes_settings_targets_gym_and_version_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    optimization: bool,
    version: str,
    hardware: bool,
) -> None:
    """
    A new procedure starts only from its explicit gym context and immutable public settings.
    """
    runner, native = _controller(tmp_path)
    scene = generate(Config(seed=123, lines=2))
    process = Mock()
    launch = Mock(return_value=process)
    monkeypatch.setenv("PYTHONHOME", "/fusion/embedded/python")
    monkeypatch.setenv("PYTHONPATH", "/fusion/embedded/site-packages")
    monkeypatch.setattr(lock, "verify", lambda: {"locked-source": "digest"})
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    request = {
        "procedures": [
            {
                "id": version,
                "settings": {
                    "smoothing_percent": 2.5,
                    "material_uv": True,
                    "first_pass_optimization": optimization,
                    "terminal_hardware": hardware,
                },
            }
        ]
    }
    runner.start(request, scene.targets, gym=scene.payload())
    assert launch.call_count == 1
    assert "PYTHONHOME" not in launch.call_args.kwargs["env"]
    assert "PYTHONPATH" not in launch.call_args.kwargs["env"]
    command = launch.call_args.args[0]
    assert command[:3] == [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "experiments.experiment_ribbon_locked_solver.worker",
    ]
    plan = json.loads((Path(command[-1]) / "plan.json").read_text())
    assert plan["version"] == version
    assert plan["settings"] == request["procedures"][0]["settings"]
    assert plan["gym"] == json.loads(json.dumps(scene.payload()))
    assert plan["targets"] == scene.payload()["targets"]
    assert plan["sources"] == {"locked-source": "digest"}
    assert runner.state()["discovery_available"] is False
    assert runner.state()["active_solver"]["settings"] == request["procedures"][0]["settings"]
    native.assert_not_called()
    assert runner._log is not None
    runner._log.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"procedures": [{"id": "ordinary", "settings": {}}]},
        {
            "procedures": [
                {"id": VERSION, "settings": {"smoothing_percent": True, "material_uv": False}}
            ]
        },
    ],
)
def test_retired_or_malformed_runs_do_not_create_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]
) -> None:
    """
    Reject stale search settings and invalid active controls before external work.
    """
    runner, native = _controller(tmp_path)
    launch = Mock(side_effect=AssertionError("No subprocess permitted"))
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    scene = generate()
    with pytest.raises(ValueError):
        runner.start(payload, scene.targets, gym=scene.payload())
    assert not runner.directory.exists()
    launch.assert_not_called()
    native.assert_not_called()


def test_endpoint_only_run_requires_actual_frozen_gym_provenance(tmp_path: Path) -> None:
    """
    Equal targets without their frozen surrounding layout cannot silently enter gym coverage.
    """
    runner, _ = _controller(tmp_path)
    with pytest.raises(ValueError, match="frozen gym"):
        runner.start(
            {
                "procedures": [
                    {"id": VERSION, "settings": {"smoothing_percent": 5.0, "material_uv": False}}
                ]
            },
            generate().targets,
        )


def test_completed_job_remains_available_to_counters_after_layout_navigation(
    tmp_path: Path,
) -> None:
    """
    Retain the explicit latest job independently of temporary selected-layout status.
    """
    runner, _ = _controller(tmp_path)
    runner._job = tmp_path / "completed-job"
    runner._status = {"status": "idle", "detail": "Another frozen layout selected"}
    assert runner.state()["job"] == str(runner._job)
    assert runner.state()["status"] == "idle"


def test_inspecting_tester_input_retains_terminal_status_and_log_job(tmp_path: Path) -> None:
    """
    Select the stopped case without hiding its failure behind an idle example disposition.
    """
    runner, _ = _controller(tmp_path)
    job = tmp_path / "failed-job"
    runner._job = job
    runner._status = {"status": "stopped", "detail": "Native construction failed"}
    layout = freeze(generate(), tmp_path / "inputs")
    assert runner.inspect_layout(layout, "Failed range case") == layout.resolve()
    state = runner.state()
    assert state["status"] == "stopped" and state["detail"] == "Native construction failed"
    assert state["job"] == str(job)
    assert state["example"].startswith("gym-")


def test_worker_launch_failure_is_logged_without_replacing_last_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Surface a subprocess launch error and retain the previous valid panel settings.
    """
    runner, native = _controller(tmp_path)
    scene = generate()
    previous = runner.state()["active_solver"]["settings"]
    monkeypatch.setattr(lock, "verify", lambda: {"source": "digest"})
    monkeypatch.setattr(
        controller.subprocess, "Popen", Mock(side_effect=OSError("SDK unavailable"))
    )
    request = {
        "procedures": [
            {
                "id": VERSION,
                "settings": {
                    "smoothing_percent": 1,
                    "material_uv": False,
                    "first_pass_optimization": False,
                },
            }
        ]
    }
    with pytest.raises(OSError, match="SDK unavailable"):
        runner.start(request, scene.targets, gym=scene.payload())
    state = runner.state()
    assert state["status"] == "stopped" and "SDK unavailable" in state["build_log"][-1]["message"]
    assert state["active_solver"]["settings"] == previous
    assert runner._log is None
    native.assert_not_called()
