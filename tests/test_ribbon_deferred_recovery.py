"""
Transfer genuinely unused optional recovery work without replenishing its original limits.
"""

from __future__ import annotations

from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_feature_insertion.contact_recovery import recover
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from tests.test_ribbon_branch_recovery import _construction


def _deferred() -> dict[str, Any]:
    """
    Retain a measured initial prediction that spent preparation time without moving or certifying geometry.
    """
    return {"status": "deferred", "cpu_seconds": 0.05, "iterations": 0, "contacts": 0, "pairs": 0}


def test_preparation_cpu_and_intervening_wall_time_reduce_the_remaining_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Charge earlier prediction and intervening contraction rather than restarting the recovery clocks.
    """
    monkeypatch.setitem(vars(solver_v2), "perf_counter", lambda: 10.0)
    assert solver_v2._remaining_recovery(_deferred(), 9.5, 4.0) == pytest.approx((0.30, 1.5))
    assert solver_v2._remaining_recovery(None, 0.0, 0.2) == (0.35, 0.2)


@pytest.mark.parametrize("reason", ("consumed", "cpu", "wall", "first_pass"))
def test_consumed_or_exhausted_work_never_authorizes_another_recovery(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    """
    Retain ordinary recovery outcomes and all scheduling ceilings.
    """
    detail = _deferred()
    if reason == "consumed":
        detail["status"] = "unresolved"
    if reason == "cpu":
        detail["cpu_seconds"] = 0.35
    monkeypatch.setitem(vars(solver_v2), "perf_counter", lambda: 12.0 if reason == "wall" else 10.0)
    assert (
        solver_v2._remaining_recovery(detail, 9.5, 0.0 if reason == "first_pass" else 4.0) is None
    )


@pytest.mark.parametrize("field", ("iterations", "contacts", "pairs"))
def test_a_deferral_cannot_hide_previous_geometry_work(field: str) -> None:
    """
    Require evidence of zero actual updates and certificates before sharing the remaining allowance.
    """
    detail = _deferred()
    detail[field] = 1
    with pytest.raises(ArithmeticError, match="consumed geometry"):
        solver_v2._remaining_recovery(detail, 0.0, 4.0)


def test_unknown_initial_policy_is_rejected() -> None:
    """
    Keep the new scheduling choice explicit without changing historical defaults.
    """
    source, _, branch = _construction()
    with pytest.raises(ValueError, match="initial recovery policy"):
        recover(
            branch.route,
            source.rejected[0][1],
            610,
            1e-5,
            lambda: None,
            lambda e: None,
            initial_policy="defer_overflow",  # type: ignore[arg-type]
        )


def test_excursion_uses_only_unspent_recovery_after_existing_contraction() -> None:
    """
    Preserve raw routes and preparation cost while accepting only the newly certified compact material route.
    """
    scene = Scene(
        Config(3594523284, 8, 0.75, 300, 300),
        Goal.from_degrees(10, 6, 36),
        Goal.from_degrees(23, 0, 9),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(scene.targets, Settings(1, False, True), lambda: None, events.append)
    assert result.route is not None and result.route.material_length_mm < 55
    assert result.detail["contact"] == "separated"
    construction = result.detail["construction"]
    recovery = construction["recovery"]
    deferred = recovery["deferred_before_contraction"]
    assert deferred["status"] == "deferred" and deferred["initial_fraction"] < 0.25
    assert deferred["iterations"] == deferred["contacts"] == deferred["pairs"] == 0
    assert recovery["purpose"] == "recover_contraction" and recovery["accepted_improvement"]
    assert 1 <= recovery["contacts"] <= recovery["iterations"] <= 4
    assert 0 < recovery["pairs"] <= 610 and construction["contact_pairs"] <= 2048
    assert deferred["cpu_seconds"] < recovery["cpu_seconds"] <= 0.35
    assert recovery["elapsed_seconds"] <= 2.0
    assert any(
        event.get("stage") == "feature_branch" and event["route"]["material_length_mm"] > 850
        for event in events
    )
    assert result.route.targets == scene.targets
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
