"""
Verify recovery selects a repairable existing branch while sharing its original resource limits.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion import contact_recovery
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_feature_insertion.separation_step import SeparationStep
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_locked_solver import recovery_selection
from experiments.experiment_ribbon_locked_solver.recovery_prediction import PredictionPolicy
from tests.test_ribbon_branch_recovery import _construction


@pytest.mark.parametrize(
    "fractions, expected",
    (((0.07, 1.0), 1), ((1.0, 1.0), 0), ((0.814, 0.879), 0), ((0.26, 0.5), 1)),
)
def test_initial_trust_steps_precede_length_and_priority_breaks_ties(
    monkeypatch: pytest.MonkeyPatch, fractions: tuple[float, float], expected: int
) -> None:
    """
    Prefer fewer initial trust steps, keeping material priority when the required count ties.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    longer = Branch.measure((1, 0), source.route, frames.guide)
    failed = source.rejected[0][1]
    candidates = ((compact, failed), (longer, failed))
    planning = Mock(
        side_effect=[SeparationStep(Side.BEFORE, -0.1, (), fraction) for fraction in fractions]
    )
    monkeypatch.setitem(vars(recovery_selection), "plan_step", planning)
    monkeypatch.setitem(
        vars(recovery_selection),
        "Separation",
        SimpleNamespace(from_measurement=Mock(return_value=object())),
    )
    events: list[dict[str, Any]] = []
    result = recovery_selection.select_recovery(candidates, lambda: None, events.append)
    assert result.choice == candidates[expected]
    assert result.alternatives == (candidates[1 - expected],)
    assert len(result.initial_steps) == 2
    assert all(
        cached.source is candidate[0].route and cached.measurement is candidate[1]
        for cached, candidate in zip(result.initial_steps, candidates)
    )
    assert planning.call_count == 2
    assert 0 < result.maximum_cpu_seconds <= 0.35
    assert 0 < result.maximum_seconds <= 2
    assert result.detail["cpu_seconds"] + result.maximum_cpu_seconds == pytest.approx(0.35)
    assert result.detail["elapsed_seconds"] + result.maximum_seconds == pytest.approx(2)
    assert events[-1]["roots"] == candidates[expected][0].roots


def test_unsupported_measurements_never_become_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve unresolved pair-only evidence instead of inventing a correction or a certificate.
    """
    source, _, branch = _construction()
    del source
    checking = Mock(side_effect=AssertionError("No separation bound is available"))
    monkeypatch.setitem(vars(recovery_selection), "plan_step", checking)
    measurement = ContactResult("unresolved", 1024, limit="pairs")
    result = recovery_selection.select_recovery(
        ((branch, measurement),), lambda: None, lambda event: None
    )
    assert result.choice is None
    assert result.detail["status"] == "no_supported_separation_step"
    checking.assert_not_called()


def test_selection_exhaustion_prevents_another_correction(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Charge prediction time to the existing cap before starting a recovery.
    """
    source, _, _ = _construction()
    clock = iter((0.0, 0.36, 0.36))
    monkeypatch.setitem(vars(recovery_selection), "process_time", lambda: next(clock))
    result = recovery_selection.select_recovery(source.rejected, lambda: None, lambda event: None)
    assert result.choice is None and result.maximum_cpu_seconds == 0
    assert result.detail["status"] == "selection_budget"


def test_caller_source_failure_propagates_during_selection() -> None:
    """
    Keep hard caller stops distinct from optional recovery exhaustion.
    """
    source, _, _ = _construction()
    with pytest.raises(RuntimeError, match="source changed"):
        recovery_selection.select_recovery(
            source.rejected, Mock(side_effect=RuntimeError("source changed")), lambda event: None
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("maximum_cpu_seconds", 0.36),
        ("maximum_seconds", 2.1),
        ("maximum_cpu_seconds", 0),
        ("maximum_seconds", True),
        ("maximum_updates", 5),
        ("maximum_updates", 0),
        ("maximum_updates", True),
    ),
)
def test_explicit_sublimits_cannot_enlarge_original_recovery_caps(field: str, value: Any) -> None:
    """
    Permit selection to reserve resources without authorizing a larger solver allowance.
    """
    source, _, branch = _construction()
    with pytest.raises(ValueError, match="sublimits"):
        contact_recovery.recover(
            branch.route,
            source.rejected[0][1],
            736,
            1e-5,
            lambda: None,
            lambda event: None,
            **{field: value},
        )


@pytest.mark.parametrize("gap, expected", ((0.01, False), (0.0, True), (-0.1, True), (None, True)))
def test_verified_selection_intervenes_only_after_a_failed_full_prediction(
    monkeypatch: pytest.MonkeyPatch,
    gap: float | None,
    expected: bool,
) -> None:
    """
    Preserve working initial choices and retain the original if no verified sheet replacement exists.
    """
    source, _, _ = _construction()
    monkeypatch.setitem(
        vars(recovery_selection),
        "plan_step",
        Mock(return_value=SeparationStep(Side.BEFORE, -0.1, (), 1.0)),
    )
    monkeypatch.setitem(
        vars(recovery_selection),
        "Separation",
        SimpleNamespace(from_measurement=Mock(return_value=object())),
    )
    check = Mock(return_value=gap)
    prepare = Mock(return_value=None)
    monkeypatch.setitem(vars(recovery_selection), "first_gap", check)
    monkeypatch.setitem(vars(recovery_selection), "verified_sheets", prepare)
    result = recovery_selection.select_recovery(
        source.rejected,
        lambda: None,
        lambda event: None,
        prediction_policy=PredictionPolicy.VERIFIED_SHEETS,
    )
    assert result.choice == source.rejected[0]
    check.assert_called_once()
    assert prepare.called is expected
    assert 0 < result.maximum_cpu_seconds <= 0.35


def test_clipped_prediction_never_authorizes_the_optional_sheet_preparation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A planned partial motion makes no one-step promise and retains its historical execution.
    """
    source, _, _ = _construction()
    monkeypatch.setitem(
        vars(recovery_selection),
        "plan_step",
        Mock(return_value=SeparationStep(Side.BEFORE, -0.1, (), 0.5)),
    )
    monkeypatch.setitem(
        vars(recovery_selection),
        "Separation",
        SimpleNamespace(from_measurement=Mock(return_value=object())),
    )
    check = Mock(side_effect=AssertionError("No full-step prediction"))
    monkeypatch.setitem(vars(recovery_selection), "first_gap", check)
    result = recovery_selection.select_recovery(
        source.rejected,
        lambda: None,
        lambda event: None,
        prediction_policy=PredictionPolicy.VERIFIED_SHEETS,
    )
    assert result.choice == source.rejected[0]
    check.assert_not_called()
