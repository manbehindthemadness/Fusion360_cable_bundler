"""
Verify cheap radius preflight and deferred strict certification preserve bounded geometry.
"""

from __future__ import annotations

import math
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_aesthetic import solve
from experiments.experiment_ribbon_aesthetic.model import curvature_score, peak_curvature
from experiments.experiment_ribbon_aesthetic.solve import ContactSchedule
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


def _corner() -> FoldRoute:
    """
    Provide radius runway while holding both complete cap frames fixed.
    """
    return _route((Straight(6), fold(1, 1.2, math.pi / 2, 0, 0), Straight(8)))


def test_deferred_schedule_checks_only_the_completed_mathematical_descent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Separate mathematical proposals from contact acceptance and retain the original result.
    """
    source = _corner()
    events: list[dict[str, Any]] = []

    def audit(route: FoldRoute, *, checkpoint: Callable[[], None] | None = None) -> ContactResult:
        """
        Observe the real stage boundary without paying for independent contact geometry.
        """
        del checkpoint
        assert events[-1]["status"] == "contact_started"
        assert any(e["status"] == "curvature_improved_contact_unmeasured" for e in events)
        assert snapshot(route) == events[-1]["route"]
        assert not any(e["status"] == "accepted" for e in events)
        return ContactResult("separated", 123)

    checking = Mock(side_effect=audit)
    monkeypatch.setitem(vars(solve), "inspect_contact", checking)
    final, status = solve.ease(
        source, 0.05, lambda: None, events.append, contact_schedule=ContactSchedule.FINAL_DESCENT
    )
    assert status == "certified_math_descent"
    checking.assert_called_once()
    assert len([e for e in events if e["status"] == "accepted"]) == 1
    assert len([e for e in events if e["status"] == "curvature_improved_contact_unmeasured"]) <= 8
    assert curvature_score(final) < curvature_score(source)
    assert peak_curvature(final) <= peak_curvature(source)
    assert cap_error(final) < 1e-7 and material_error(final) < 1e-10
    assert final.material_length_mm <= source.material_length_mm * 1.05 + 1e-8
    checking.side_effect = None
    checking.return_value = ContactResult("separated", 123)
    historical, _ = solve.ease(source, 0.05, lambda: None, lambda event: None)
    assert snapshot(final) == snapshot(historical)


@pytest.mark.parametrize("second_status", ("separated", "penetration", "unresolved"))
def test_failed_final_checks_are_bounded_and_never_replace_a_safe_input(
    monkeypatch: pytest.MonkeyPatch, second_status: str
) -> None:
    """
    Check at most one predecessor and retain baseline if neither proposal is certified.
    """
    source = _corner()
    events: list[dict[str, Any]] = []
    check = Mock(
        side_effect=[
            ContactResult("unresolved", 20000, limit="pairs"),
            ContactResult(second_status, 234),
        ]
    )
    monkeypatch.setitem(vars(solve), "inspect_contact", check)
    final, status = solve.ease(
        source, 0.05, lambda: None, events.append, contact_schedule=ContactSchedule.FINAL_DESCENT
    )
    assert check.call_count == 2
    if second_status == "separated":
        assert final is check.call_args_list[1].args[0]
        assert status == "certified_math_descent"
    else:
        assert final is source and status == "baseline_retained"
        assert not any(event["status"] == "accepted" for event in events)


def test_stationary_radius_preflight_skips_all_contact_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Return an unchanged straight route with an explicit local stop reason.
    """
    source = _route((Straight(10),))
    check = Mock(side_effect=AssertionError("No radius change needs certification"))
    monkeypatch.setitem(vars(solve), "inspect_contact", check)
    events: list[dict[str, Any]] = []
    final, reason = solve.ease(
        source, 0.01, lambda: None, events.append, contact_schedule=ContactSchedule.FINAL_DESCENT
    )
    assert final is source and reason == "no_projected_curvature_descent"
    assert events == [{"stage": "radius_math", "status": reason, "proposals": 0}]
    check.assert_not_called()


def test_cancellation_and_logging_errors_stop_before_certification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Propagate boundary failures instead of certifying incomplete mathematical work.
    """
    check = Mock()
    monkeypatch.setitem(vars(solve), "inspect_contact", check)
    with pytest.raises(TimeoutError, match="cancelled"):
        solve.ease(
            _corner(),
            0.05,
            Mock(side_effect=TimeoutError("cancelled")),
            lambda event: None,
            contact_schedule=ContactSchedule.FINAL_DESCENT,
        )
    with pytest.raises(OSError, match="logging failed"):
        solve.ease(
            _corner(),
            0.05,
            lambda: None,
            Mock(side_effect=OSError("logging failed")),
            contact_schedule=ContactSchedule.FINAL_DESCENT,
        )
    check.assert_not_called()
