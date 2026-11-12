"""
Carry correction debt without treating missing or scoped history as an unused Newton pool.
"""

from __future__ import annotations

from typing import Any

import pytest

from experiments.experiment_ribbon_locked_solver import terminal_allowance
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def test_zero_remaining_corrections_preserve_other_exact_work_without_renewal() -> None:
    """
    An exhausted angle pool need not erase unused root, proof, update or clock allocations.
    """
    work = Work(4, 2048, 0.35, 2, 3)
    first = work.remaining(updates=1, pairs=10, cpu_seconds=0.1, wall_seconds=0.1, newton_steps=2)
    assert first is not None and first.newton_steps == 1 and first.updates == 3
    second = first.remaining(updates=1, pairs=10, cpu_seconds=0.1, wall_seconds=0.1, newton_steps=1)
    assert second is not None and second.newton_steps == 0 and second.updates == 2
    with pytest.raises(ArithmeticError, match="original allowance"):
        second.remaining(updates=2, pairs=0, cpu_seconds=0, wall_seconds=0, newton_steps=1)


@pytest.mark.parametrize("value", (-1, 25, True, 0.5))
def test_malformed_correction_allocations_reject_before_geometry(value: Any) -> None:
    """
    Counts are genuine nonnegative integers within the original twenty-four-step ceiling.
    """
    with pytest.raises(ValueError, match="corrections"):
        Work(4, 2048, 0.35, 2, value)


@pytest.mark.parametrize(
    "prior_steps,scope,expected",
    (
        (17, None, 6),
        (18, None, 6),
        (None, None, 0),
        (5, "terminal_reclosure_only", 0),
        (24, None, None),
        (True, None, None),
    ),
)
def test_completed_recovery_leaves_only_provable_shared_corrections(
    prior_steps: Any, scope: str | None, expected: int | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Unknown or terminal-only receipts permit exact work but cannot grant another correction pool.
    """
    monkeypatch.setitem(vars(terminal_allowance), "perf_counter", lambda: 1)
    detail = {
        "status": "separated",
        "iterations": 3,
        "cpu_seconds": 0.1,
        "contacts": 1,
        "pairs": 10,
    }
    if prior_steps is not None:
        detail["newton_steps"] = prior_steps
    if scope is not None:
        detail["newton_steps_scope"] = scope
    left = terminal_allowance.remaining_completed(detail, 0, 4)
    if expected is None:
        assert left is None
    else:
        assert left is not None and left.newton_steps == expected
        assert left.used_newton_steps == (prior_steps if scope is None else None)


def test_selection_only_deferral_cannot_erase_started_corrections() -> None:
    """
    Preparation-only ledger updates cannot relabel geometric work as untouched.
    """
    prior = {
        "status": "deferred",
        "iterations": 0,
        "contacts": 0,
        "pairs": 0,
        "cpu_seconds": 0.1,
        "newton_steps": 1,
    }
    with pytest.raises(ValueError, match="untouched"):
        terminal_allowance.defer_unentered(prior, 0, 0)
