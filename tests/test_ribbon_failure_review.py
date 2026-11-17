"""
Verify endpoint comparisons and final-rejection precedence in read-only campaign reports.
"""

from __future__ import annotations

from typing import Any

import pytest

from artifacts.verification.resume3368.review import grouped, reason, relative_roll


@pytest.mark.parametrize(
    ("end", "end_width", "expected"),
    [
        ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 90.0),
        ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), 0.0),
        ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), None),
    ],
)
def test_relative_roll_transport_and_opposite_ambiguity(
    end: tuple[float, float, float], end_width: tuple[float, float, float], expected: float | None
) -> None:
    """
    Distinguish roll from tangent rotation without choosing an arbitrary half-turn axis.
    """
    actual = relative_roll((0.0, 0.0, 1.0), end, (1.0, 0.0, 0.0), end_width)
    assert actual is None if expected is None else actual == pytest.approx(expected)


def test_report_keeps_passing_and_ambiguous_denominators() -> None:
    """
    A group containing only failures must not absorb unrelated or ambiguous cases.
    """
    result = grouped(
        [
            {"roll": 45.0, "category": "prepared_with_longitudinal_bound"},
            {"roll": 45.0, "category": "trunk_unresolved"},
            {"roll": None, "category": "prepared_with_longitudinal_bound"},
        ],
        "roll",
        (45, 90),
    )
    assert result["0..45"] == {"total": 2, "prepared": 1, "failures": 1, "failure_percent": 50.0}
    assert result["ambiguous"]["total"] == 1
    assert result["ambiguous"]["failures"] == 0


@pytest.mark.parametrize(
    ("row", "detail", "events", "expected"),
    [
        (
            {"category": "case_exhaustion", "error": "10s scheduling limit"},
            {"rejection_reason": "accepted"},
            [],
            "case_time_limit",
        ),
        (
            {
                "category": "case_exhaustion",
                "error": "Shared trunk metric span allocation exhausted",
            },
            {},
            [],
            "metric_span_limit",
        ),
        (
            {"category": "trunk_unresolved"},
            {"rejection_reason": "work_exhausted"},
            [{"stage": "native_readiness", "status": "proposal_declined"}],
            "work_exhausted",
        ),
        (
            {"category": "trunk_unresolved"},
            {"construction": {"recovery": None}},
            [{"stage": "native_readiness", "status": "proposal_declined"}, {"wall": 1}],
            "native_support_degeneracy",
        ),
    ],
)
def test_final_reason_overrides_earlier_events(
    row: dict[str, Any], detail: dict[str, Any], events: list[dict[str, Any]], expected: str
) -> None:
    """
    Earlier accepted recovery and missing stage fields must not mislabel final failures.
    """
    assert reason(row, detail, events) == expected
