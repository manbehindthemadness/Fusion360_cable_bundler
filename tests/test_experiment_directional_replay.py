"""
Check directional support arithmetic without treating it as geometry validation.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.directional_replay import (
    _frames,
    _vector,
    bending_ratios,
    measure_frames,
)
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


def _frame(x: float = 0, roll: float = 0) -> RibbonFrame:
    """
    Supply an orthonormal straight scaffold with explicit roll.
    """
    return RibbonFrame(
        Vector3(x, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, math.cos(roll), math.sin(roll)),
        Vector3(0, -math.sin(roll), math.cos(roll)),
    )


def test_directional_support_distinguishes_width_and_thickness_bending() -> None:
    """
    Thin-axis bending gains margin; hard-axis bending still consumes width.
    """
    hard = bending_ratios(Vector3(0, 0.1, 0), _frame(), 15, 0.75)
    easy = bending_ratios(Vector3(0, 0, 0.1), _frame(), 15, 0.75)
    assert hard[0] == easy[0] == pytest.approx(math.hypot(15, 0.75) * 0.1)
    assert hard[1] == pytest.approx(1.5)
    assert easy[1] == easy[2] == pytest.approx(0.075)


def test_mixed_bending_consumes_one_combined_allowance() -> None:
    """
    Do not independently grant each axis a full macaroni allowance.
    """
    circular, directional, _ideal = bending_ratios(Vector3(0, 0.03, 0.6), _frame(), 15, 0.75)
    assert directional == pytest.approx(0.9)
    assert circular > directional


def test_diagonal_rectangle_support_can_equal_circular_bound() -> None:
    """
    The directional calculation does not universally improve the enclosing circle.
    """
    circular, directional, _ideal = bending_ratios(Vector3(0, 15, 0.75), _frame(), 15, 0.75)
    assert circular == pytest.approx(directional)


def test_straight_twist_is_invisible_to_bending_but_visible_to_bank_rate() -> None:
    """
    Expose why the directional bending rule cannot substitute for twist checks.
    """
    result = measure_frames(tuple(_frame(i, i * 0.1) for i in range(3)), 15, 0.75)
    assert result["maximum_directional_proxy"] == 0
    assert result["maximum_circular_proxy"] == 0
    assert result["maximum_projected_bank_rate_radians_per_mm"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    "value", (None, {}, {"x": True, "y": 0, "z": 0}, {"x": float("nan"), "y": 0, "z": 0})
)
def test_malformed_vectors_are_not_valid_geometry(value: object) -> None:
    """
    Distinguish invalid archived data from a successful diagnostic.
    """
    with pytest.raises(ValueError):
        _vector(value)


def test_missing_frames_and_invalid_dimensions_are_rejected() -> None:
    """
    Reject absent samples and nonphysical envelope inputs without fallback.
    """
    with pytest.raises(ValueError):
        _frames(None)
    with pytest.raises(ValueError):
        bending_ratios(Vector3(0, 0, 0), _frame(), -1, 0.75)
