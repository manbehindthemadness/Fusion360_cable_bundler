"""
Verify original dimensional goals and the exclusive0.01mm diagnostic warning ceiling.
"""

from __future__ import annotations

from typing import Any

import pytest

from devtools.ribbon_analysis.inspection.archive import RuleObservation
from experiments.experiment_ribbon_locked_solver.accuracy import (
    DISPLAY_ACCURACY,
    STRICT_ACCURACY,
    DimensionalAccuracy,
    warning_summary,
)


@pytest.mark.parametrize(
    "error,strict,display,warning",
    [
        (0, True, True, False),
        (1e-6, True, True, False),
        (4e-6, False, True, True),
        (0.005, False, True, True),
        (0.009999999, False, True, True),
        (0.01, False, False, False),
        (0.010001, False, False, False),
        (-1e-9, False, False, False),
        (float("nan"), False, False, False),
        (float("inf"), False, False, False),
        (True, False, False, False),
        (None, False, False, False),
    ],
)
def test_dimensional_boundaries_retain_goal_and_exclusive_ceiling(
    error: Any, strict: bool, display: bool, warning: bool
) -> None:
    """
    Never round an at-limit, malformed or unknown error into a warning-level result.
    """
    assert STRICT_ACCURACY.accepts(error) is strict
    assert DISPLAY_ACCURACY.meets_goal(error) is strict
    assert DISPLAY_ACCURACY.accepts(error) is display
    audit: dict[str, Any] = {}
    assert DISPLAY_ACCURACY.observe(audit, "surface", error, face=17) is display
    assert bool(audit.get("accuracy_warnings")) is warning
    if warning:
        finding = audit["accuracy_warnings"][0]
        assert finding == {
            "category": "surface",
            "error_mm": error,
            "goal_mm": 1e-6,
            "warning_below_mm": 0.01,
            "face": 17,
        }


def test_warnings_keep_categories_original_errors_and_actual_maximum() -> None:
    """
    Summarize named completed findings without deleting strict-goal evidence.
    """
    audit: dict[str, Any] = {"failed_points": [{"error_mm": 0.005}]}
    for category, error in (("surface", 0.005), ("seam", 0.002), ("cap_position", 0.004)):
        assert DISPLAY_ACCURACY.observe(audit, category, error)
    summary = warning_summary(audit["accuracy_warnings"])
    assert summary is not None
    assert summary["measurement_count"] == 3
    assert summary["maximum_error_mm"] == 0.005
    assert summary["goal_mm"] == 1e-6
    assert summary["warning_below_mm"] == 0.01
    assert summary["categories"] == ["cap_position", "seam", "surface"]
    assert "Original accuracy findings are retained" in summary["message"]
    assert audit["failed_points"] == [{"error_mm": 0.005}]
    assert warning_summary([]) is None


@pytest.mark.parametrize(
    "goal,limit",
    [
        (0, None),
        (True, None),
        (float("nan"), None),
        (1e-6, 1e-6),
        (1e-6, float("inf")),
        (1e-6, True),
    ],
)
def test_invalid_accuracy_policies_reject(goal: float, limit: float | None) -> None:
    """
    Policy configuration cannot erase the original accuracy target or permit unlimited deviations.
    """
    with pytest.raises(ValueError):
        DimensionalAccuracy(goal, limit)


def test_warning_observation_preserves_the_missed_goal_and_measured_error() -> None:
    """
    Diagnostic archives can show a warning with its original goal rather than a failure or pass.
    """
    observation = RuleObservation(
        "Native dimensional accuracy",
        "warning",
        "Below0.01mm; original accuracy target retained",
        value=0.005,
        limit=1e-6,
    )
    assert observation.status == "warning"
    assert observation.value == 0.005 and observation.limit == 1e-6
