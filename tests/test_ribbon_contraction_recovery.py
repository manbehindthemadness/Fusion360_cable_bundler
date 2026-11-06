"""
Use measured contraction failures without discarding a safe route or replenishing work budgets.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result as Contraction
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_locked_solver import contraction_recovery
from tests.test_ribbon_branch_recovery import _construction


@pytest.mark.parametrize("outcome", ("improved", "failed", "not_better"))
def test_only_certified_monotonic_improvement_replaces_the_baseline(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Reuse remaining pairs and original time limits while counting even unsuccessful work.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    contact = source.rejected[0][1]
    contraction = Contraction(source.route, None, {}, ((compact.route, contact),))
    corrected = (
        compact.route
        if outcome == "improved"
        else source.route
        if outcome == "not_better"
        else None
    )
    certificate = ContactResult("separated", 245) if corrected else None
    attempt = Mock(return_value=Recovery(corrected, certificate, 245, 1, 0.03, {"iterations": 2}))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    result = contraction_recovery.recover_contracted(
        contraction, frames, 447, 1e-5, lambda: None, lambda event: None
    )
    assert result is not None and result.pairs == 245
    assert attempt.call_args.args[0] is compact.route and attempt.call_args.args[2] == 447
    assert attempt.call_args.kwargs["cap_policy"] is CapPolicy.ANALYTIC_SUPPORT
    assert 0 < attempt.call_args.kwargs["maximum_cpu_seconds"] <= 0.35
    assert 0 < attempt.call_args.kwargs["maximum_seconds"] <= 2
    assert result.detail["accepted_improvement"] is (outcome == "improved")
    assert (result.route is not None) is (outcome == "improved")


@pytest.mark.parametrize("condition", ("unmeasured", "not_shorter", "no_pairs"))
def test_no_speculative_work_without_improvement_evidence_or_unused_pairs(
    monkeypatch: pytest.MonkeyPatch, condition: str
) -> None:
    """
    Skip pair-limit-only evidence, non-improving geometry and exhausted original work.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    route = source.route if condition == "not_shorter" else compact.route
    contact = (
        ContactResult("unresolved", 1024, limit="pairs")
        if condition == "unmeasured"
        else source.rejected[0][1]
    )
    contraction = Contraction(source.route, None, {}, ((route, contact),))
    attempt = Mock(side_effect=AssertionError("No eligible measured correction"))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    result = contraction_recovery.recover_contracted(
        contraction,
        frames,
        0 if condition == "no_pairs" else 447,
        1e-5,
        lambda: None,
        lambda event: None,
    )
    assert result is None
    attempt.assert_not_called()


def test_explicit_cpu_reservation_is_not_replenished(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Subtract preparation from a reduced caller allowance before invoking the strict correction.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    contraction = Contraction(source.route, None, {}, ((compact.route, source.rejected[0][1]),))
    clock = iter((0.0, 0.05, 0.06))
    monkeypatch.setitem(vars(contraction_recovery), "process_time", lambda: next(clock))
    attempt = Mock(return_value=Recovery(None, None, 0, 0, 0, {"iterations": 0}))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    contraction_recovery.recover_contracted(
        contraction, frames, 610, 1e-5, lambda: None, lambda e: None, maximum_cpu_seconds=0.2
    )
    assert attempt.call_args.kwargs["maximum_cpu_seconds"] == pytest.approx(0.15)


@pytest.mark.parametrize("allowance", (0.0, 0.36, True, float("nan")))
def test_cpu_sublimits_cannot_expand_or_disable_the_original_cap(allowance: Any) -> None:
    """
    Reject malformed or enlarged scheduling allowances before optional work.
    """
    source, frames, _ = _construction()
    assert source.route is not None
    with pytest.raises(ValueError, match="remaining CPU"):
        contraction_recovery.recover_contracted(
            Contraction(source.route, None, {}),
            frames,
            610,
            1e-5,
            lambda: None,
            lambda e: None,
            maximum_cpu_seconds=allowance,
        )
