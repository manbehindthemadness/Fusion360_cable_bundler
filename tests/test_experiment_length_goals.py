"""
Keep mechanical goal misses nonblocking without waiving geometry constraints.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_cap_transition.accuracy import length_goal, separate_length_goals


@pytest.mark.parametrize(
    "spread,status", ((0.0, "met"), (0.01, "met"), (0.02, "missed"), (None, "unmeasured"))
)
def test_length_goal_is_never_a_build_gate(spread: float | None, status: str) -> None:
    """
    Preserve measured goal outcomes and unknowns independently of construction.
    """
    result = length_goal(spread)
    assert result["relative_spread"] == spread
    assert result["status"] == status
    assert result["blocking"] is False


@pytest.mark.parametrize(
    "hard_failure",
    (None, "end_A_lane_1:combined_end_region_length", "neighbor_pitch", "trunk_input_curvature"),
)
def test_only_length_findings_move_to_warnings(hard_failure: str | None) -> None:
    """
    Let a goal-only miss proceed while retaining unrelated rejection evidence.
    """
    failures = ["trunk_lane_length_spread", "complete_sampled_lane_length_spread"]
    if hard_failure is not None:
        failures.append(hard_failure)
    report: dict[str, object] = {"failures": failures, "complete_sampled_lane_spread": 0.06}
    separate_length_goals(report, 0.07)
    assert report["warnings"] == ["trunk_lane_length_spread", "complete_sampled_lane_length_spread"]
    assert report["failures"] == ([] if hard_failure is None else [hard_failure])
    assessment = report["geometry_assessment"]
    assert isinstance(assessment, dict)
    assert assessment["status"] == (
        "no_detected_violation" if hard_failure is None else "known_rule_rejection"
    )
    assert assessment["construction"] == "not_attempted"
    accuracy = report["mechanical_accuracy"]
    assert isinstance(accuracy, dict)
    assert accuracy["native_complete_length"]["status"] == "unmeasured"


@pytest.mark.parametrize("spread", (-0.1, float("nan"), float("inf")))
def test_invalid_measurements_are_not_goal_passes(spread: float) -> None:
    """
    Reject malformed evidence rather than normalizing it into a warning or pass.
    """
    with pytest.raises(ValueError, match="finite and nonnegative"):
        length_goal(spread)
