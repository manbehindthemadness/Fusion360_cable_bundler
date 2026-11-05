"""
Keep branch handoffs within one shared recovery allowance and require fresh separation evidence.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_feature_insertion import contact_recovery
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    ContactContinuation,
    Recovery,
)
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_locked_solver import recovery_queue, solver_v2
from experiments.experiment_ribbon_locked_solver.recovery_selection import Selection
from experiments.experiment_ribbon_locked_solver.settings import Settings
from tests.test_ribbon_branch_recovery import _construction


def _queue(monkeypatch: pytest.MonkeyPatch) -> tuple[Result, Branch]:
    """
    Supply two already-ranked shared-cap branches without invoking numerical prediction.
    """
    source, _, branch = _construction()
    other = replace(branch, roots=(0, 0))
    measurement = source.rejected[0][1]
    selection = Selection(
        (branch, measurement), 0.30, 1.9, {"status": "selected"}, ((other, measurement),)
    )
    monkeypatch.setitem(vars(recovery_queue), "select_recovery", Mock(return_value=selection))
    return source, other


def test_new_collision_yields_only_unused_updates_pairs_and_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Transfer two unused updates without restarting any of the original work allowances.
    """
    source, other = _queue(monkeypatch)
    clock = iter((0.0, 0.05, 0.15, 0.30))
    monkeypatch.setitem(vars(recovery_queue), "process_time", lambda: next(clock))
    certificate = ContactResult("separated", 471)
    attempt = Mock(
        side_effect=(
            Recovery(
                None, None, 108, 1, 0.01, {"iterations": 2, "stop_reason": "different_contact_pair"}
            ),
            Recovery(other.route, certificate, 471, 1, 0.02, {"iterations": 2}),
        )
    )
    monkeypatch.setitem(vars(recovery_queue), "recover", attempt)
    result = recovery_queue.recover_failed(
        source.rejected, 1181, 1e-5, lambda: None, lambda event: None
    )
    first, second = attempt.call_args_list
    assert first.kwargs["maximum_updates"] == 4 and second.kwargs["maximum_updates"] == 2
    assert first.args[2] == 1181 and second.args[2] == 1073
    assert first.kwargs["maximum_cpu_seconds"] == pytest.approx(0.30)
    assert second.kwargs["maximum_cpu_seconds"] == pytest.approx(0.20)
    assert first.kwargs["continuation"] is ContactContinuation.YIELD_ON_NEW_PAIR
    assert second.kwargs["continuation"] is ContactContinuation.FOLLOW
    assert first.kwargs["cap_policy"] is second.kwargs["cap_policy"] is CapPolicy.ANALYTIC_SUPPORT
    assert result.route is other.route and result.contact is certificate
    assert (
        result.pairs == 579
        and result.contacts == 2
        and result.contact_seconds == pytest.approx(0.03)
    )
    assert result.detail["iterations"] == 4 and result.detail["remaining_pair_budget"] == 602
    assert result.detail["cpu_seconds"] == pytest.approx(0.30)
    assert result.detail["cap_support_policy"] == "analytic_support"


def test_reversed_gym_recovery_certifies_the_existing_correction_inside_remaining_work() -> None:
    """
    Finish the four-conductor gym correction without exhausting the original construction pair pool.
    """
    scene = Scene(
        Config(1607811975, 4, 0.75, 300, 300),
        Goal.from_degrees(21, 10, 5),
        Goal.from_degrees(3, 1, 32),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(scene.targets, Settings(1, False, True), lambda: None, events.append)
    assert result.route is not None and result.detail["contact"] == "separated"
    detail = result.detail["construction"]
    assert 0 < detail["contact_pairs"] < 2048
    recovery = detail["recovery"]
    assert (
        recovery["status"] == "separated" and recovery["cap_support_policy"] == "analytic_support"
    )
    assert recovery["iterations"] == recovery["contacts"] == 1
    assert 0 < recovery["pairs"] <= 447 and recovery["remaining_pair_budget"] > 0
    initial = sum(
        e["contact"]["pairs_checked"]
        for e in events
        if e.get("stage") == "feature_contact" and "contact" in e
    )
    assert initial + recovery["pairs"] == detail["contact_pairs"]
    assert result.route.targets == scene.targets
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10


@pytest.mark.parametrize(
    "stop", ("no_gap_improvement", "local_budget", "update_budget", "pair_budget")
)
def test_failure_does_not_silently_start_another_full_recovery(
    monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    """
    Permit a handoff only for a newly measured collision and available original work.
    """
    source, _ = _queue(monkeypatch)
    updates = 4 if stop == "update_budget" else 2
    pairs = 1181 if stop == "pair_budget" else 108
    reason = "different_contact_pair" if stop in ("update_budget", "pair_budget") else stop
    attempt = Mock(
        return_value=Recovery(
            None, None, pairs, 1, 0.01, {"iterations": updates, "stop_reason": reason}
        )
    )
    monkeypatch.setitem(vars(recovery_queue), "recover", attempt)
    result = recovery_queue.recover_failed(
        source.rejected, 1181, 1e-5, lambda: None, lambda event: None
    )
    attempt.assert_called_once()
    assert result.route is None and result.detail["stop_reason"] == stop


def test_elapsed_cpu_blocks_a_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Count selection and first-branch time before scheduling another branch.
    """
    source, _ = _queue(monkeypatch)
    clock = iter((0.0, 0.05, 0.36, 0.36))
    monkeypatch.setitem(vars(recovery_queue), "process_time", lambda: next(clock))
    attempt = Mock(
        return_value=Recovery(
            None, None, 108, 1, 0.01, {"iterations": 2, "stop_reason": "different_contact_pair"}
        )
    )
    monkeypatch.setitem(vars(recovery_queue), "recover", attempt)
    result = recovery_queue.recover_failed(
        source.rejected, 1181, 1e-5, lambda: None, lambda event: None
    )
    attempt.assert_called_once()
    assert result.route is None and result.detail["stop_reason"] == "local_budget"


def test_gym_reversal_uses_two_existing_branches_within_four_total_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Resolve the changed collision while retaining exact caps, material rules and strict contact.
    """
    # Check geometry deterministically; clock-stop contracts have separate tests.
    monkeypatch.setitem(vars(recovery_queue), "process_time", lambda: 0.0)
    monkeypatch.setitem(vars(contact_recovery), "process_time", lambda: 0.0)
    scene = Scene(
        Config(2433123344, 5, 0.75, 300, 300),
        Goal(23, 8, roll_degrees=1),
        Goal(9, 3, roll_degrees=30),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(scene.targets, Settings(0), lambda: None, events.append)
    assert result.route is not None and result.detail["contact"] == "separated"
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    recovery = result.detail["construction"]["recovery"]
    assert recovery["iterations"] == 4 and recovery["contacts"] == 2
    assert [row["roots"] for row in recovery["attempts"]] == [(0, 1), (0, 0)]
    assert recovery["attempts"][0]["stop_reason"] == "different_contact_pair"
    assert result.detail["construction"]["contact_pairs"] <= 2048
