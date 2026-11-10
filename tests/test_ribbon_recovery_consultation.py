"""
Preserve genuinely unused recovery work while charging all selection-only preparation.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_locked_solver import (
    contraction_recovery,
    solver_v2,
    terminal_allowance,
)
from tests.test_ribbon_branch_recovery import _construction


def test_no_eligible_strategy_clears_a_stale_entry_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Pair-budget-only uncertainty provides no geometric strategy and cannot consume updates by consultation alone.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    rejected = ((compact.route, ContactResult("unresolved", 1024, limit="pairs")),)
    receipt = contraction_recovery.RecoveryConsultation(entered=True)
    forbidden = Mock(side_effect=AssertionError("No supported strategy"))
    monkeypatch.setitem(vars(contraction_recovery), "recover", forbidden)
    outcome = contraction_recovery.recover_contracted(
        Result(source.route, None, {}, rejected),
        frames,
        447,
        1e-5,
        lambda: None,
        Mock(),
        consultation=receipt,
    )
    assert outcome is None and not receipt.entered
    forbidden.assert_not_called()


def test_entered_strategy_with_no_replacement_still_consumes_consultation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Zero reported progress does not authorize another allocation after a strategy has run.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    receipt = contraction_recovery.RecoveryConsultation()
    attempted = Mock(return_value=Recovery(None, None, 0, 0, 0.0, {"iterations": 0}))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempted)
    outcome = contraction_recovery.recover_contracted(
        Result(source.route, None, {}, ((compact.route, source.rejected[0][1]),)),
        frames,
        447,
        1e-5,
        lambda: None,
        Mock(),
        consultation=receipt,
    )
    assert outcome is not None and outcome.route is None and receipt.entered
    attempted.assert_called_once()


@pytest.mark.parametrize("prior_cpu", (None, 0.06, 0.31))
def test_preparation_handoff_deducts_cpu_and_retains_original_wall_origin(
    monkeypatch: pytest.MonkeyPatch,
    prior_cpu: float | None,
) -> None:
    """
    Preparation can hand off only remaining time, including when it exhausts the original pool.
    """
    prior = (
        None
        if prior_cpu is None
        else {
            "status": "deferred",
            "iterations": 0,
            "contacts": 0,
            "pairs": 0,
            "cpu_seconds": prior_cpu,
        }
    )
    charged = terminal_allowance.defer_unentered(prior, 0.07, 1.5)
    assert charged["cpu_seconds"] == pytest.approx((prior_cpu or 0.0) + 0.07)
    assert charged["iterations"] == charged["contacts"] == charged["pairs"] == 0
    monkeypatch.setitem(vars(solver_v2), "perf_counter", lambda: 10.0)
    allocation = solver_v2._remaining_recovery(charged, 8.5, 3.0)
    if prior_cpu == 0.31:
        assert allocation is None
    else:
        assert allocation == pytest.approx((0.35 - (prior_cpu or 0.0) - 0.07, 0.5))


@pytest.mark.parametrize("status,updates", (("unresolved", 0), ("separated", 1), ("deferred", 1)))
def test_spent_or_failed_history_cannot_be_relabelled_as_preparation(
    status: str, updates: int
) -> None:
    """
    Only an untouched reservation is eligible for selection-only handoff.
    """
    with pytest.raises(ValueError, match="untouched"):
        terminal_allowance.defer_unentered(
            {
                "status": status,
                "iterations": updates,
                "contacts": 0,
                "pairs": 0,
                "cpu_seconds": 0.01,
            },
            0.01,
            0.02,
        )


@pytest.mark.parametrize("cpu,wall", ((-0.1, 0.1), (float("nan"), 0.1), (0.1, float("inf"))))
def test_nonfinite_or_negative_preparation_cannot_create_an_allowance(
    cpu: float, wall: float
) -> None:
    """
    Invalid timing evidence must not turn into new recovery work.
    """
    with pytest.raises(ValueError, match="finite and nonnegative"):
        terminal_allowance.defer_unentered(None, cpu, wall)
