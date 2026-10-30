"""
Verify frozen gym inputs survive optional diagnostic runs and independent draft edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, Goal, generate
from devtools.ribbon_analysis.gym.handoff import freeze, identity, validate
from devtools.ribbon_analysis.inspection.archive import canonical, write_document
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_diagnostic_viewer import controller, interactive_worker
from experiments.experiment_ribbon_diagnostic_viewer.procedures import ROOT
from experiments.experiment_ribbon_route_discovery import broad_chart


@pytest.mark.parametrize("diameter", (1, 1.5))
def test_handoff_is_endpoint_only_stable_and_independent_of_later_edits(
    tmp_path: Path, diameter: float
) -> None:
    """
    Reuse unchanged inputs but retain separate cases after any face or orientation edit.
    """
    scene = generate(Config(lines=2, diameter_mm=diameter, void_percent=450, zone_percent=175))
    manifest = freeze(scene, tmp_path)
    original_bytes = manifest.read_bytes()
    session = Session(manifest)
    assert session.targets == scene.targets
    assert canonical(session.gym) == canonical(scene.payload())
    assert session.snapshot is None and session.methods[0]["history_count"] == 0
    assert freeze(scene, tmp_path) == manifest
    changed = scene.choose("b", Goal(scene.b.zone, scene.b.face, (scene.b.roll + 1) % 4))
    other = Session(freeze(changed, tmp_path))
    assert other.targets.end == session.targets.end
    assert other.targets.end_width != session.targets.end_width
    assert identity(other.gym) != identity(session.gym)
    assert manifest.read_bytes() == original_bytes
    assert session.state()["gym"]["side_mm"] == 9 * diameter


@pytest.mark.parametrize("part", ("config", "geometry", "target", "role"))
def test_malformed_or_relabelled_context_cannot_enter_replay(part: str) -> None:
    """
    Reject unrelated drawing data and target drift before the renderer sees a payload.
    """
    scene = generate()
    payload = json.loads(canonical(scene.payload()))
    if part == "config":
        payload["config"]["lines"] = 129
    elif part == "geometry":
        payload["drawing"]["surfaces"][0]["points"][0]["x"] += 1
    elif part == "target":
        payload["targets"]["end"]["z"] += 1
    else:
        payload["drawing"]["strokes"][0]["role"] = "unregistered"
    with pytest.raises(ValueError):
        validate(payload, scene.targets)


def test_controller_worker_and_import_preserve_the_same_frozen_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Exercise an opt-in two-conductor transport through the actual recording boundary.

    The numerical adapter is a single deterministic transport; this checks the
    handoff contract and history capture, not nonlinear solver quality or feasibility.
    """
    scene = generate(Config(lines=2))
    manifest = freeze(scene, tmp_path / "layouts")
    session = Session(manifest)
    process = Mock()
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    monkeypatch.setattr(controller.budget, "resident_kib", lambda: 10000)
    monkeypatch.setattr(controller.procedures, "source_pins", lambda: {"test": "fixed"})
    runner = controller.ProcedureController(ROOT / ".venv/bin/python", tmp_path / "runs")
    identifier = runner.register_layout(manifest, "My gym layout")
    assert runner.open_example(identifier) == manifest.resolve()
    assert runner.state()["examples"][-1] == {"id": identifier, "label": "My gym layout"}
    launch.assert_not_called()
    request = {
        "procedures": [{"id": "ordinary", "settings": {"coarse": 1, "fine": 0, "transports": 16}}]
    }
    runner.start(request, session.targets, gym=session.gym)
    job = Path(runner.state()["directory"])
    plan_bytes = (job / "plan.json").read_bytes()
    assert json.loads(plan_bytes)["gym_id"] == identifier
    assert Session(job / "input.json").gym == session.gym
    with pytest.raises(ValueError, match="active job"):
        runner.register_layout(manifest, "Cannot switch")
    with pytest.raises(ValueError, match="active job"):
        runner.open_example("single")

    def execute(
        _identifier: str, case: Any, _settings: dict[str, Any], checkpoint: Any
    ) -> tuple[Any, dict[str, Any]]:
        """
        Supply one complete transport without searching for or selecting a feasible path.
        """
        return broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, checkpoint), {"score": 1.0}

    monkeypatch.setattr(interactive_worker.adapters, "execute", execute)
    result = interactive_worker.run(job)
    incoming = Session(result)
    assert incoming.gym == session.gym and incoming.targets == scene.targets
    assert incoming.methods[0]["history_count"] == 1
    assert incoming.snapshot is not None
    process.poll.return_value, process.returncode = 0, 0
    assert runner.poll() == result and runner.poll() is None
    added = session.import_results(result)
    session.select(added[0], 0)
    assert session.state()["gym"] == incoming.gym
    assert session.snapshot is not None
    assert (job / "plan.json").read_bytes() == plan_bytes
    assert json.loads(result.read_text())["native_solid_attempts"] == 0


def test_import_rejects_a_result_that_drops_its_environment(tmp_path: Path) -> None:
    """
    Identical endpoints cannot mask a missing frozen-layout association.
    """
    manifest = freeze(generate(), tmp_path)
    session = Session(manifest)
    data = json.loads(manifest.read_text())
    del data["gym"]
    data["solvers"][0]["id"] = "result"
    result = tmp_path / "wrong.json"
    write_document(result, data)
    with pytest.raises(ValueError, match="frozen gym"):
        session.import_results(result)
    assert len(session.methods) == 1 and session.snapshot is None
