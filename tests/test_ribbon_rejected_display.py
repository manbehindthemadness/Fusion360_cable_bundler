"""
Keep rejected route inspection separate from numerical acceptance and native construction.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.gym import generate
from devtools.ribbon_analysis.inspection.archive import SCHEMA, write_document
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_locked_solver import controller, worker
from experiments.experiment_ribbon_locked_solver.lock import ROOT
from experiments.experiment_ribbon_locked_solver.rejected_display import retain
from experiments.experiment_ribbon_locked_solver.solver import Result
from experiments.experiment_ribbon_locked_solver.versions import V2


def _route() -> FoldRoute:
    """
    Supply a synthetic recorded route without running any endpoint solver.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    targets = Targets("display boundary", Vector3(0, 0, 0), Vector3(10, 0, 0), x, x, y, y, 2, 0.75)
    return FoldRoute(targets, (PlacedPiece(Pose(targets.start, x, y), Straight(10), "run"),), 1)


def _events(route: FoldRoute) -> list[dict[str, Any]]:
    """
    Record four branches, preserving failed, unresolved and unattempted dispositions.
    """
    return [
        *(
            {
                "stage": "feature_branch",
                "status": "closed",
                "roots": roots,
                "route": snapshot(route),
            }
            for roots in ([0, 0], [0, 1], [1, 0], [1, 1])
        ),
        {
            "stage": "feature_contact",
            "status": "penetration",
            "roots": [0, 0],
            "contact": {"pairs_checked": 234},
        },
        {"stage": "feature_contact", "status": "unresolved", "roots": [0, 1]},
        {"stage": "feature_contact", "status": "unresolved", "roots": [1, 0]},
    ]


def _method() -> dict[str, Any]:
    """
    Declare an unresolved result before optional inspection attachment.
    """
    return {
        "id": "rejected",
        "label": "Solver",
        "source": "synthetic recorded fixture",
        "status": "unresolved",
        "detail": "No accepted route.",
        "rules": [],
    }


def _ledger(path: Path, events: list[dict[str, Any]]) -> None:
    """
    Preserve the event order and complete JSONL records used by the worker.
    """
    path.write_text("".join(json.dumps(event) + "\n" for event in events))


def test_rejected_history_displays_without_native_ready_output(tmp_path: Path) -> None:
    """
    Existing inspection sessions expose every branch while preserving its failed status.
    """
    route, method = _route(), _method()
    trials = tmp_path / "trials.jsonl"
    _ledger(trials, _events(route))
    original = trials.read_bytes()
    assert retain(method, trials, tmp_path, route.targets, lambda: None) == 4
    manifest = tmp_path / "manifest.json"
    write_document(
        manifest, {"schema": SCHEMA, "targets": asdict(route.targets), "solvers": [method]}
    )
    session = Session(manifest)
    assert session.snapshot is not None
    assert session.methods[0]["status"] == "unresolved"
    assert session.methods[0]["history_count"] == 4
    session.select("rejected", 3)
    assert session.snapshot is not None
    branches = json.loads((tmp_path / "rejected-geometry.json").read_text())["branches"]
    assert [branch["disposition"] for branch in branches] == [
        "penetration",
        "unresolved",
        "unresolved",
        "contact unattempted",
    ]
    assert trials.read_bytes() == original
    assert "NOT ACCEPTED" in method["detail"]
    assert not (tmp_path / "route.json").exists()


@pytest.mark.parametrize(
    "events", ([], [{"stage": "feature_branch", "status": "position_unresolved"}])
)
def test_missing_closed_geometry_is_not_invented(
    tmp_path: Path, events: list[dict[str, Any]]
) -> None:
    """
    Failed algebra without a closed recorded path has no displayable route.
    """
    trials, method = tmp_path / "trials.jsonl", _method()
    _ledger(trials, events)
    assert retain(method, trials, tmp_path, _route().targets, lambda: None) == 0
    assert "snapshot" not in method
    assert not (tmp_path / "rejected-history.jsonl").exists()


def test_wrong_targets_and_cancelled_display_preserve_failure(tmp_path: Path) -> None:
    """
    Inspection cannot cross input identity or override cooperative resource cancellation.
    """
    route, method = _route(), _method()
    trials = tmp_path / "trials.jsonl"
    _ledger(trials, _events(route))
    with pytest.raises(ValueError, match="fixed targets"):
        retain(
            method, trials, tmp_path, replace(route.targets, name="different case"), lambda: None
        )
    with pytest.raises(TimeoutError):
        retain(method, trials, tmp_path, route.targets, Mock(side_effect=TimeoutError("cancelled")))
    assert "snapshot" not in method


@pytest.mark.parametrize("display_error", (False, True))
def test_worker_failure_attaches_geometry_but_controller_skips_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, display_error: bool
) -> None:
    """
    Exercise the real worker/archive/controller boundary without solving or building solids.
    """
    scene, pins = generate(), {"source": "digest"}
    route = replace(_route(), targets=scene.targets)
    plan = {
        "version": V2,
        "result_id": "rejected",
        "targets": asdict(scene.targets),
        "gym": scene.payload(),
        "settings": {"smoothing_percent": 0, "material_uv": False, "first_pass_optimization": True},
        "sources": pins,
    }
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    monkeypatch.setitem(vars(worker), "verify", lambda: pins)
    if display_error:
        monkeypatch.setitem(
            vars(worker), "retain", Mock(side_effect=ValueError("bad display record"))
        )

    def rejected(*args: Any, **_kwargs: Any) -> Result:
        """
        Emit precomputed test records instead of launching numerical construction.
        """
        for event in _events(route):
            args[3](event)
        return Result(None, None, {"status": "unresolved"}, None)

    monkeypatch.setattr(worker, "solve_v2", rejected)
    manifest = worker.run(tmp_path)
    session = Session(manifest)
    assert (session.snapshot is None) == display_error
    assert session.methods[0]["status"] == "unresolved"
    native = Mock()
    runner = controller.Controller(ROOT / ".venv/bin/python", tmp_path, "owned", native)
    runner._job = tmp_path
    runner._process = Mock(returncode=0, poll=Mock(return_value=0))
    runner._seconds = float("inf")
    monkeypatch.setattr(
        "experiments.experiment_ribbon_diagnostic_viewer.controller.budget.resident_kib", lambda: 0
    )
    assert runner.poll() == manifest
    assert runner.state()["status"] == "unresolved"
    native.assert_not_called()
