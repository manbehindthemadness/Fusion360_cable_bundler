"""
Verify opt-in settings, isolated worker ownership and immutable result import.
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
from experiments.experiment_ribbon_route_discovery import broad_chart


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
    "settings",
    ({"seconds": True}, {"seconds": float("nan")}, {"coarse": 1.5}, {"fine": -1}, {"bogus": 1}),
)
def test_settings_reject_invalid_values_before_execution(settings: dict[str, Any]) -> None:
    """
    Keep malformed control values out of archived run plans and numerical calls.
    """
    with pytest.raises(ValueError):
        selections([{"id": "ordinary", "settings": settings}])


def test_selection_defaults_are_real_and_unavailable_inputs_are_explicit() -> None:
    """
    Expose genuine procedure parameters and enforce per-click aggregate budgets.
    """
    configured = selections(
        [{"id": "tightening", "settings": {"start_window": "0", "end_window": "0.125"}}]
    )
    assert configured[0]["settings"] == {
        "seconds": 8.0,
        "paths": 512,
        "excerpt": 0,
        "coarse": 8,
        "fine": 3,
        "transports": 158,
        "start_window": "0",
        "end_window": "0.125",
    }
    with pytest.raises(ValueError, match="Requires"):
        selections([{"id": "tube", "settings": {}}])
    with pytest.raises(ValueError, match="same procedure"):
        selections([{"id": "ordinary", "settings": {}}] * 2)
    with pytest.raises(ValueError, match="120-second"):
        selections(
            [
                {"id": identifier, "settings": {"seconds": 30}}
                for identifier in ("ordinary", "generalized", "broad", "director", "compatible")
            ]
        )


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


def test_controller_is_opt_in_and_owns_only_one_sdk_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Validate before spawning, retain a plan, and cancel only the owned worker.
    """
    process = Mock()
    process.poll.return_value = None
    process.returncode = -15
    launch = Mock(return_value=process)
    monkeypatch.setattr(controller.subprocess, "Popen", launch)
    monkeypatch.setattr(controller.budget, "resident_kib", lambda: 10000)
    monkeypatch.setattr(controller.procedures, "source_pins", lambda: {"test": "fixed"})
    runner = controller.ProcedureController(ROOT / ".venv/bin/python", tmp_path)
    launch.assert_not_called()
    runner.state()
    launch.assert_not_called()
    targets = Session(_input(tmp_path)).targets
    with pytest.raises(ValueError):
        runner.start({"procedures": [{"id": "tube", "settings": {}}]}, targets)
    launch.assert_not_called()
    runner.start({"procedures": [{"id": "ordinary", "settings": {}}]}, targets)
    job = Path(runner.state()["directory"])
    plan = (job / "plan.json").read_bytes()
    assert json.loads(plan)["procedures"][0]["settings"]["transports"] == 158
    command = launch.call_args.args[0]
    assert command[:3] == [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "experiments.experiment_ribbon_diagnostic_viewer.interactive_worker",
    ]
    assert "PYTHONHOME" not in launch.call_args.kwargs["env"]
    with pytest.raises(ValueError, match="already"):
        runner.start({"procedures": [{"id": "ordinary", "settings": {}}]}, targets)
    assert launch.call_count == 1
    (job / "progress.json").write_text('{"status":"completed"}')
    assert runner.poll() is None
    assert runner.state()["status"] == "running"
    runner.cancel()
    assert (job / "cancel").is_file()
    assert runner.state()["status"] == "cancelling"
    process.poll.return_value = -15
    assert runner.poll() is None
    assert runner.state()["status"] == "stopped"
    assert (job / "plan.json").read_bytes() == plan


@pytest.mark.parametrize("stop", (False, True))
def test_worker_preserves_paths_and_all_procedure_dispositions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: bool
) -> None:
    """
    Archive interrupted transports and skip later methods after a latched error.
    """
    _input(tmp_path)
    requested = selections(
        [{"id": "ordinary", "settings": {}}, {"id": "tightening", "settings": {}}]
    )
    write_document(
        tmp_path / "plan.json",
        {
            "run_id": "run-test",
            "procedures": requested,
            "sources": {"test": "fixed"},
            "minimum_radius_mm": 4.5,
        },
    )
    monkeypatch.setattr(interactive_worker.procedures, "source_pins", lambda: {"test": "fixed"})
    monkeypatch.setattr(interactive_worker.budget, "resident_kib", lambda: 10000)
    calls: list[str] = []

    def execute(
        identifier: str, case: Any, settings: dict[str, Any], checkpoint: Any
    ) -> tuple[Any, dict[str, Any]]:
        """
        Exercise the real transport recorder without nonlinear optimization work.
        """
        assert settings["paths"] == 512
        calls.append(identifier)
        path = broad_chart.integrate(case, (0.0,) * 9 + (1.2,), 64, checkpoint)
        if stop:
            raise interactive_worker.SchedulingStop("Test checkpoint stop")
        return path, {"score": 1.0}

    monkeypatch.setattr(interactive_worker.adapters, "execute", execute)
    result_path = interactive_worker.run(tmp_path)
    result = json.loads(result_path.read_text())
    assert result["native_solid_attempts"] == 0
    assert result["independent_configurations"] == 1
    assert len(result["solvers"]) == 2
    assert len(read_history(tmp_path / "ordinary.jsonl")) == 1
    assert len(Session(result_path).methods) == 2
    if stop:
        assert calls == ["ordinary"]
        assert [method["status"] for method in result["solvers"]] == ["stopped", "not_run"]
        assert result["solvers"][0]["snapshot"] is not None
    else:
        assert calls == ["ordinary", "tightening"]
        assert all(method["status"] == "unresolved" for method in result["solvers"])


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
