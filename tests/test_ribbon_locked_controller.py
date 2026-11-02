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
from experiments.experiment_ribbon_locked_solver import VERSION, Settings, controller, lock
from experiments.experiment_ribbon_locked_solver.lock import ROOT


def _controller(tmp_path: Path) -> tuple[controller.Controller, Mock]:
    """
    Use the actual configured module SDK path but mock all subprocess/native boundaries.
    """
    native = Mock(return_value={"status": "built_and_named_fidelity_checks_pass"})
    runner = controller.Controller(
        ROOT / ".venv/bin/python", tmp_path / "runs", "owned-test-design", native
    )
    return runner, native


def test_selected_run_freezes_settings_targets_gym_and_version_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
        "procedures": [{"id": VERSION, "settings": {"smoothing_percent": 2.5, "material_uv": True}}]
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
    assert plan["version"] == VERSION
    assert plan["settings"] == request["procedures"][0]["settings"]
    assert plan["gym"] == json.loads(json.dumps(scene.payload()))
    assert plan["targets"] == scene.payload()["targets"]
    assert plan["sources"] == {"locked-source": "digest"}
    assert runner.state()["discovery_available"] is False
    assert runner.state()["active_solver"]["settings"] == {
        "smoothing_percent": Settings().smoothing_percent,
        "material_uv": False,
    }
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
