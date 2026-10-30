"""
Verify frozen gym inputs survive optional diagnostic runs and independent draft edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym import Config, Goal, generate
from devtools.ribbon_analysis.gym.handoff import freeze, identity, validate
from devtools.ribbon_analysis.inspection.archive import canonical, write_document
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_diagnostic_viewer import controller
from experiments.experiment_ribbon_diagnostic_viewer.procedures import ROOT


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


def test_gym_handoff_remains_available_without_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep frozen layouts selectable and importable while stale solve requests reject.
    """
    scene = generate(Config(lines=2))
    manifest = freeze(scene, tmp_path / "layouts")
    session = Session(manifest)
    original = manifest.read_bytes()
    launch = Mock(side_effect=AssertionError("Discovery must not launch"))
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    runner = controller.ProcedureController(ROOT / ".venv/bin/python", tmp_path / "runs")
    identifier = runner.register_layout(manifest, "My gym layout")
    assert runner.open_example(identifier) == manifest.resolve()
    assert runner.state()["examples"][-1] == {"id": identifier, "label": "My gym layout"}
    with pytest.raises(ValueError, match="have been removed"):
        runner.start(
            {"procedures": [{"id": "ordinary", "settings": {}}]}, session.targets, gym=session.gym
        )
    launch.assert_not_called()
    assert not runner.directory.exists()
    assert manifest.read_bytes() == original
    assert canonical(session.gym) == canonical(scene.payload())
    assert session.snapshot is None


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
