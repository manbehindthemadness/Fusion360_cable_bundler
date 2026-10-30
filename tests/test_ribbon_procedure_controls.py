"""
Verify discovery retirement and immutable historical result import.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.inspection.archive import (
    SCHEMA,
    snapshot_payload,
    targets_payload,
    write_document,
)
from devtools.ribbon_analysis.inspection.capture import SearchRecorder, read_history
from devtools.ribbon_analysis.inspection.geometry import freeze_curve
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_cap_transition.director_fields import development
from experiments.experiment_ribbon_cap_transition.director_transport import integrate
from experiments.experiment_ribbon_diagnostic_viewer import controller, interactive_worker
from experiments.experiment_ribbon_diagnostic_viewer.fixture import SpatialSBend
from experiments.experiment_ribbon_diagnostic_viewer.procedures import ROOT, selections


def _input(directory: Path) -> Path:
    """
    Freeze the development fixture once without invoking a numerical solver.
    """
    curve = SpatialSBend()
    manifest = directory / "input.json"
    write_document(
        manifest,
        {
            "schema": SCHEMA,
            "targets": targets_payload(curve.targets()),
            "solvers": [
                {
                    "id": "reference",
                    "label": "Reference",
                    "source": "fixture",
                    "status": "reference",
                    "detail": "Authored development input.",
                    "rules": [],
                    "snapshot": snapshot_payload(
                        freeze_curve("reference", curve, 1.5, intervals=16)
                    ),
                }
            ],
        },
    )
    return manifest


@pytest.mark.parametrize(
    "identifier",
    (
        "generalized",
        "ordinary",
        "redistribution",
        "tightening",
        "combined",
        "compatible",
        "director",
        "discovery",
        "broad",
    ),
)
def test_retired_discovery_rejects_even_explicit_historical_settings(identifier: str) -> None:
    """
    Neither a stale palette nor historical mode can restore removed discovery methods.
    """
    for settings in ({}, {"path_rules": "historical", "bend_model": "legacy"}):
        with pytest.raises(ValueError, match="have been removed"):
            selections([{"id": identifier, "settings": settings}])


def test_inventory_has_no_executable_search_settings() -> None:
    """
    Preserve recognizable historical method identities without offering new runs.
    """
    assert len(controller.procedures.catalog()) == 12
    assert all(
        item["unavailable"] and not item["settings"] for item in controller.procedures.catalog()
    )
    assert controller.procedures.demonstration() == []


def test_legacy_axis_transport_records_actual_completed_geometry(tmp_path: Path) -> None:
    """
    Include baseline director policies in the same history contract as rotation policies.
    """
    recorder = SearchRecorder(tmp_path / "axes.jsonl", "director", lambda: None)
    with recorder.recording():
        path = integrate(development()[0], 64, lambda: None)
    records = read_history(tmp_path / "axes.jsonl")
    assert len(records) == 1
    assert recorder.last is not None
    center = next(guide for guide in recorder.last.guides if guide.number == 0)
    assert center.curves[0].start == path.lane(0, 0)[0]


def test_controller_rejects_stale_launch_without_creating_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Refuse old run and comparison requests before spawning or changing evidence.
    """
    launch = Mock(side_effect=AssertionError("No discovery subprocess may launch"))
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    output = tmp_path / "runs"
    runner = controller.ProcedureController(ROOT / ".venv/bin/python", output)
    targets = Session(_input(tmp_path)).targets
    request: dict[str, Any] = {"procedures": [{"id": "ordinary", "settings": {"coarse": 10}}]}
    for payload in (
        request,
        dict(request, comparison={"origin": "old", "disabled_rules": ["lane_bend"]}),
    ):
        with pytest.raises(ValueError, match="have been removed"):
            runner.start(payload, targets)
    launch.assert_not_called()
    assert not output.exists()
    assert runner.state()["discovery_available"] is False
    assert runner.state()["ablation_controls"] == {}
    assert runner.poll() is None
    runner.cancel()


def test_stale_worker_plan_is_preserved_without_loading_inputs(tmp_path: Path) -> None:
    """
    Reject an already frozen old job without touching its plan or archived paths.
    """
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"procedures": [{"id": "generalized", "settings": {}}]}))
    history = tmp_path / "generalized.jsonl"
    history.write_text("retained historical evidence\n")
    original = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="have been removed"):
        interactive_worker.run(tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == original


def test_import_appends_results_without_changing_fixed_inputs_or_selection(tmp_path: Path) -> None:
    """
    Keep original evidence and reject a mismatched run before altering the session.
    """
    original = Session(_input(tmp_path))
    original.select_section(7)
    snapshot = original.snapshot
    source = json.loads((tmp_path / "input.json").read_text())
    source["solvers"][0]["id"] = "run-new:ordinary"
    destination = tmp_path / "result.json"
    write_document(destination, source)
    assert original.import_results(destination) == ("run-new:ordinary",)
    assert (
        original.snapshot is snapshot and original.section == 7 and original.solver == "reference"
    )
    with pytest.raises(ValueError, match="duplicate"):
        original.import_results(destination)
    source["targets"]["end"]["x"] += 1
    source["solvers"][0]["id"] = "run-other:ordinary"
    wrong = tmp_path / "wrong.json"
    write_document(wrong, source)
    with pytest.raises(ValueError, match="fixed endpoint"):
        original.import_results(wrong)
    assert len(original.methods) == 2
