"""
Distinguish algebraic rejection causes without changing the allocation calculation.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_bend_reduction.closure import AffineWorkspace
from experiments.experiment_ribbon_feature_insertion.linear_fit import least_squares


@pytest.mark.parametrize("cached", (False, True))
@pytest.mark.parametrize(
    "hard,right,objective,wanted,budget,expected_reason",
    (
        ([[1.0], [1.0]], [1.0, 2.0], [[1.0]], [0.0], None, "hard_equalities_unresolved"),
        (
            [[1.0, 1.0]],
            [20.0],
            [],
            [],
            10.0,
            "straight_budget_hard_equalities_unresolved",
        ),
        (
            [[1.0, 0.0, 0.0]],
            [2.0],
            [[0.0, 1.0, 1.0], [0.0, 0.0, 1e-6]],
            [3.0, 1.0],
            None,
            "guide_objective_unresolved",
        ),
        ([[1.0, 1.0]], [2.0], [[1.0, 0.0]], [0.5], None, None),
        ([[1.0, -1.0]], [0.0], [[0.0, 1e-3]], [1.0], 10.0, None),
    ),
)
def test_failure_observation_preserves_results_and_identifies_the_rejected_stage(
    cached: bool,
    hard: list[list[float]],
    right: list[float],
    objective: list[list[float]],
    wanted: list[float],
    budget: float | None,
    expected_reason: str | None,
) -> None:
    """
    Preserve successful and unresolved results with and without exact affine workspace reuse.
    """
    size = len(hard[0])
    expected = least_squares(hard, right, objective, wanted, size, maximum_sum=budget)
    failures: list[str] = []
    actual = least_squares(
        hard,
        right,
        objective,
        wanted,
        size,
        maximum_sum=budget,
        workspace=AffineWorkspace() if cached else None,
        rejected=failures.append,
    )
    assert actual == expected
    assert failures == ([] if expected_reason is None else [expected_reason])
    assert (actual is None) == (expected_reason is not None)
