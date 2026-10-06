"""
Separate mechanical length goals from experimental geometry rejection gates.
"""

from __future__ import annotations

import math

LENGTH_GOAL_FAILURES = frozenset(
    ("trunk_lane_length_spread", "complete_sampled_lane_length_spread")
)
LENGTH_GOAL = 0.01


def length_goal(spread: float | None) -> dict[str, object]:
    """
    Report a nonblocking one-percent goal, preserving unknown measurements.
    """
    if spread is not None and (not math.isfinite(spread) or spread < 0):
        raise ValueError("Length spread must be finite and nonnegative when measured.")
    return {
        "relative_spread": spread,
        "goal": LENGTH_GOAL,
        "status": "unmeasured"
        if spread is None
        else "met"
        if spread <= LENGTH_GOAL + 1e-9
        else "missed",
        "blocking": False,
        "policy": "warn but proceed; not mechanical certification",
    }


def separate_length_goals(report: dict[str, object], trunk_spread: float) -> None:
    """
    Move only named length-goal findings out of hard failures, retaining all others.

    The legacy preflight remains unchanged. This experimental reporting adapter
    preserves measured values and unknown native properties; it does not assert
    construction success or alter solver decisions.
    """
    failures = report.get("failures")
    complete = report.get("complete_sampled_lane_spread")
    if not isinstance(failures, list) or any(not isinstance(value, str) for value in failures):
        raise TypeError("Preflight failures must be a list of strings.")
    if complete is not None and (
        isinstance(complete, bool) or not isinstance(complete, (int, float))
    ):
        raise TypeError("Complete sampled lane spread must be numeric or unmeasured.")
    warnings = [failure for failure in failures if failure in LENGTH_GOAL_FAILURES]
    failures[:] = [failure for failure in failures if failure not in LENGTH_GOAL_FAILURES]
    report["warnings"] = warnings
    report["mechanical_accuracy"] = {
        "trunk_sampled_length": length_goal(trunk_spread),
        "complete_sampled_length": length_goal(complete),
        "native_complete_length": length_goal(None),
        "scope": "Sampled metrics are mechanical goals, not native material accuracy certificates.",
    }
    report["geometry_assessment"] = {
        "status": "known_rule_rejection" if failures else "no_detected_violation",
        "construction": "not_attempted",
        "scope": "Remaining geometry constraints only; native interpolation still unresolved.",
    }
