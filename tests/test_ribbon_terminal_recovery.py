"""
Verify bounded deferred terminal recovery and full finite-box material-sheet separation.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.reversal_model import ReversalModel
from experiments.experiment_ribbon_terminal_hardware.sheet import Sheet
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_terminal_gate import _constructor


def test_consulted_contraction_recovery_cannot_renew_its_allowance_for_terminal_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Even no-candidate preparation may spend work, so do not reserve another full phase afterward.
    """
    route = _route((Straight(10),))
    terminal = Mock(spec=Gate)
    terminal.permits.return_value = False
    terminal.detail.return_value = {"enabled": True}
    monkeypatch.setitem(vars(solver_v2), "construct", _constructor(route))
    monkeypatch.setitem(vars(solver_v2), "Gate", Mock(return_value=terminal))
    monkeypatch.setitem(vars(solver_v2), "correct_terminal", Mock(return_value=None))
    contraction = Result(
        route, None, {"status": "baseline_retained"}, ((route, ContactResult("unresolved", 1)),)
    )
    monkeypatch.setitem(vars(solver_v2), "contract", Mock(return_value=contraction))
    prepared = Mock(return_value=None)
    late = Mock(side_effect=AssertionError("No renewed feasibility allowance"))
    monkeypatch.setitem(vars(solver_v2), "recover_contracted", prepared)
    monkeypatch.setitem(vars(solver_v2), "recover_terminal", late)
    monkeypatch.setitem(
        vars(solver_v2),
        "smooth_with_contact",
        Mock(return_value=SimpleNamespace(route=route, contact=None, stages={})),
    )
    result = solver_v2.solve(
        route.targets, Settings(0, False, True, True), lambda: None, lambda e: None
    )
    assert result.route is None
    prepared.assert_called_once()
    late.assert_not_called()


def test_sheet_uses_whole_straight_bounds_and_rejects_unsupported_evidence() -> None:
    """
    A demonstrated return defines a finite-box plane; unresolved evidence grants no action.
    """
    route = _route((fold(1, 1.2, math.pi, 0, 0), Straight(3)))
    hardware = Hardware.create(route.targets, Dimensions(3, 5, 3))
    report = inspect(route, hardware)
    assert report.status == "blocked" and report.witness is not None
    model = ReversalModel(route, 0)
    sheet = Sheet.create(model, route, report, hardware)
    assert sheet is not None and sheet.region.straight
    piece: PlacedPiece = route.pieces[report.witness.piece]
    assert sheet._gap_piece(piece) < 0
    assert Sheet.create(model, route, Report("unresolved", 32), hardware) is None


@pytest.mark.parametrize(
    "field,value",
    (
        ("remaining_pairs", 2049),
        ("remaining_pairs", 0),
        ("maximum_cpu_seconds", 0.36),
        ("maximum_seconds", 2.1),
        ("maximum_updates", 0),
        ("maximum_updates", 5),
        ("maximum_updates", True),
    ),
)
def test_deferred_recovery_cannot_enlarge_existing_allowances(field: str, value: Any) -> None:
    """
    Reject renewed time/pair limits before geometry work.
    """
    route = _route((Straight(10),))
    options = {
        "maximum_length_mm": 10.0,
        "minimum_straight_mm": 1e-5,
        "remaining_pairs": 100,
        "maximum_cpu_seconds": 0.35,
        "maximum_seconds": 2.0,
        field: value,
    }
    with pytest.raises(ValueError):
        recovery.recover(route, Mock(spec=Gate), lambda: None, lambda e: None, **options)


def test_missing_actual_witness_cannot_start_deferred_joint_work() -> None:
    """
    A completed unresolved certificate is not evidence for guessing an event or a plane.
    """
    route = _route((Straight(10),))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report("unresolved", 512)
    assert (
        recovery.recover(
            route,
            terminal,
            lambda: None,
            lambda e: None,
            maximum_length_mm=10,
            minimum_straight_mm=1e-5,
            remaining_pairs=1024,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
        )
        is None
    )
