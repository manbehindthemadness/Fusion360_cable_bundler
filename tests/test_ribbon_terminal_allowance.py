"""
Verify nonrenewing completed-recovery allocation and sub-native zero-slot linear projection.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_locked_solver import solver_v2, terminal_allowance
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.native_projection import native_slot_step
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_terminal_gate import _constructor


@pytest.mark.parametrize(
    "status,updates,cpu",
    (
        ("unresolved", 2, 0.1),
        ("deferred", 0, 0.1),
        ("separated", 4, 0.1),
        ("separated", True, 0.1),
        ("separated", 3, float("nan")),
        ("separated", 3, 0.35),
    ),
)
def test_incomplete_or_exhausted_history_cannot_grant_more_work(
    status: str,
    updates: Any,
    cpu: float,
) -> None:
    """
    Reject failed, malformed, fully spent and preparation-only histories without allocation.
    """
    assert (
        terminal_allowance.remaining_completed(
            {
                "status": status,
                "iterations": updates,
                "cpu_seconds": cpu,
                "contacts": 2,
                "pairs": 13,
            },
            0,
            1,
        )
        is None
    )


def test_completed_history_deducts_updates_cpu_and_intervening_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A completed three-update phase leaves one update and shares its original deadline.
    """
    monkeypatch.setitem(vars(terminal_allowance), "perf_counter", lambda: 10.0)
    prior = {
        "status": "separated",
        "iterations": 3,
        "cpu_seconds": 0.24,
        "contacts": 2,
        "pairs": 13,
    }
    allocation = terminal_allowance.remaining_completed(prior, 8.4, 3)
    assert allocation is not None
    assert allocation.updates == 1
    assert allocation.cpu_seconds == pytest.approx(0.11)
    assert allocation.wall_seconds == pytest.approx(0.4)
    assert terminal_allowance.remaining_completed(prior, 8.0, 3) is None
    assert terminal_allowance.remaining_completed(prior, 9.5, 0) is None


def test_zero_native_slot_is_reprojected_instead_of_clamped_after_closure() -> None:
    """
    Keep x absent when tiny motion would create an invalid piece, while y closes x+y=1.
    """
    model = Mock(spec=SignedJoints)
    model.straight_indices, model.scale = (0,), 1.0
    model.bounds.return_value = (-10.0, 10.0)
    delta = (1e-12, 1 - 1e-12)
    result = native_slot_step(model, (0.0, 0.0), [[1.0, 1.0]], (-1.0,), delta, 1e-5)
    assert result == pytest.approx((0.0, 1.0))
    assert native_slot_step(model, (1.0, 0.0), [[1.0, 1.0]], (-1.0,), delta, 1e-5) is delta
    growth = (0.01, 0.99)
    assert native_slot_step(model, (0.0, 0.0), [[1.0, 1.0]], (-1.0,), growth, 1e-5) is growth


@pytest.mark.parametrize("hardware_clear", (False, True))
def test_only_rejected_hardware_uses_remaining_completed_work(
    monkeypatch: pytest.MonkeyPatch,
    hardware_clear: bool,
) -> None:
    """
    Preserve a successful legacy route, or carry one recorded update without renewing counters.
    """
    source = _route((Straight(10),))
    constructor = _constructor(source)
    prior = {"status": "separated", "iterations": 3, "cpu_seconds": 0.2, "contacts": 2, "pairs": 13}
    monkeypatch.setitem(vars(solver_v2), "construct", constructor)
    monkeypatch.setitem(
        vars(solver_v2),
        "recover_construction",
        Mock(return_value=(constructor.return_value, prior)),
    )
    terminal = Mock(spec=Gate)
    terminal.permits.return_value = hardware_clear
    terminal.detail.return_value = {"enabled": True}
    monkeypatch.setitem(vars(solver_v2), "Gate", Mock(return_value=terminal))
    monkeypatch.setitem(vars(solver_v2), "correct_terminal", Mock(return_value=None))
    monkeypatch.setitem(
        vars(solver_v2),
        "contract",
        Mock(return_value=Result(source, None, {"status": "baseline_retained"})),
    )
    monkeypatch.setitem(
        vars(solver_v2),
        "smooth_with_contact",
        Mock(return_value=SimpleNamespace(route=source, contact=None, stages={})),
    )
    contact = ContactResult("separated", 7)
    late = Mock(
        return_value=Result(
            source,
            contact,
            {
                "status": "separated",
                "iterations": 1,
                "newton_steps": 5,
                "contacts": 1,
                "contact_pairs": 7,
                "contact_seconds": 0.01,
                "cpu_seconds": 0.03,
                "elapsed_seconds": 0.04,
            },
        )
    )
    monkeypatch.setitem(vars(solver_v2), "recover_terminal", late)
    result = solver_v2.solve(
        source.targets, Settings(0, False, True, True), lambda: None, lambda e: None
    )
    assert result.route is source
    if hardware_clear:
        late.assert_not_called()
    else:
        late.assert_called_once()
        assert late.call_args.kwargs["maximum_updates"] == 1
        assert 0 < late.call_args.kwargs["maximum_cpu_seconds"] < 0.15
        assert late.call_args.kwargs["remaining_pairs"] == 2048 - 749
        detail = result.detail["construction"]["recovery"]
        assert (
            detail["iterations"] == 4 and detail["contacts"] == 3 and detail["contact_pairs"] == 20
        )
        assert result.detail["construction"]["contact_pairs"] == 756
