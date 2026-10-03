"""
Check the host-independent arithmetic used by the Fusion bank experiment.
"""

from __future__ import annotations

import pytest

from experiments.experiment_banked_profile_extremes import (
    SHAPES,
    cases,
    normal_extremes_mm,
    twist_cases,
)


def test_circle_extremes_are_bank_invariant() -> None:
    """
    A circular profile has the same reach in both normal directions.
    """
    circle = SHAPES[0]
    for angle in (0.0, 30.0, 90.0, 150.0):
        assert normal_extremes_mm(circle, angle) == (2.0, 2.0)


def test_rectangle_extremes_follow_bank_angle() -> None:
    """
    Width enters the bend plane under a quarter-turn of bank.
    """
    rectangle = SHAPES[1]
    assert normal_extremes_mm(rectangle, 0.0) == (0.25, 0.25)
    assert normal_extremes_mm(rectangle, 90.0) == pytest.approx((4.0, 4.0))
    assert normal_extremes_mm(rectangle, 30.0) == pytest.approx(
        (2.2165063509461094, 2.2165063509461094)
    )


def test_asymmetric_triangle_reaches_differ_and_exchange_under_reversal() -> None:
    """
    Signed support is necessary where the profile has no central symmetry.
    """
    triangle = SHAPES[2]
    left, right = normal_extremes_mm(triangle, 30.0)
    reversed_left, reversed_right = normal_extremes_mm(triangle, 210.0)
    assert (left, right) == pytest.approx((1.7834936490538902, 2.2165063509461094))
    assert (reversed_left, reversed_right) == pytest.approx((right, left))


def test_preregistered_fixed_and_twisted_cases() -> None:
    """
    Keep the Fusion comparison grid deterministic and separately labeled.
    """
    fixed = cases()
    twisted = twist_cases()
    assert len(fixed) == 36
    assert len(twisted) == 18
    assert len({row["name"] for row in (*fixed, *twisted)}) == 54
    triangle = next(row for row in fixed if row["name"] == "bank_h5_triangle_8x1_a30")
    assert triangle["left_reach_mm"] < triangle["right_reach_mm"]
    assert triangle["local_fold_load"] > 1.0
    twist = next(row for row in twisted if row["name"] == "twist_h5_triangle_8x1_a180")
    assert twist["distance_local_fold_load"] > 1.0
