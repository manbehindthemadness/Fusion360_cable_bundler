"""
Verify analytic taper planning against independent exact polynomial integration and jets.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.taper_schedule import (
    BlendInterval,
    TaperRequirement,
    plan,
)


def check() -> None:
    """
    Permit bounded host-independent mathematical contract tests.
    """


def power(controls: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    """
    Expand Bernstein controls into monomials independently of the planner.
    """
    degree = len(controls) - 1
    return tuple(
        sum(
            (
                controls[i] * math.comb(degree, i) * math.comb(degree - i, k - i) * (-1) ** (k - i)
                for i in range(k + 1)
            ),
            Fraction(0),
        )
        for k in range(degree + 1)
    )


def velocity_energy(interval: BlendInterval) -> Fraction:
    """
    Integrate squared global velocity using monomial products and exact antiderivatives.
    """
    coefficients = power(interval.controls)
    derivative = tuple(i * coefficients[i] for i in range(1, len(coefficients)))
    return sum(
        (a * b / (i + j + 1) for i, a in enumerate(derivative) for j, b in enumerate(derivative)),
        Fraction(0),
    ) / (interval.high - interval.low)


def endpoint_jets(interval: BlendInterval, end: bool) -> tuple[Fraction, Fraction, Fraction]:
    """
    Evaluate position and two global derivatives from independent monomial expansion.
    """
    coefficients = power(interval.controls)
    parameter = Fraction(int(end))
    width = interval.high - interval.low
    values = tuple(
        sum(
            (
                math.prod(range(i - derivative + 1, i + 1)) * value * parameter ** (i - derivative)
                for i, value in enumerate(coefficients)
                if i >= derivative
            ),
            Fraction(0),
        )
        / width**derivative
        for derivative in range(3)
    )
    return values[0], values[1], values[2]


def maximum_acceleration(interval: BlendInterval) -> Fraction:
    """
    Find exact extrema of each returned quadratic acceleration in the monomial basis.
    """
    coefficients = power(interval.controls)
    second = tuple(i * (i - 1) * coefficients[i] for i in range(2, len(coefficients)))
    if not second:
        return Fraction(0)
    a = second[2] if len(second) > 2 else Fraction(0)
    b = second[1] if len(second) > 1 else Fraction(0)
    locations = [Fraction(0), Fraction(1)]
    if a and 0 < -b / (2 * a) < 1:
        locations.append(-b / (2 * a))
    return (
        max(
            abs(sum((value * u**i for i, value in enumerate(second)), Fraction(0)))
            for u in locations
        )
        / (interval.high - interval.low) ** 2
    )


@pytest.mark.parametrize(
    "requirements",
    (
        (TaperRequirement(Fraction(3, 4), Fraction(3, 40), Fraction(2)),) * 2,
        (
            TaperRequirement(Fraction(2), Fraction(1, 10), Fraction(1)),
            TaperRequirement(Fraction(1), Fraction(1, 20), Fraction(1)),
        ),
        (TaperRequirement(Fraction(1), Fraction(0), Fraction(0)),),
    ),
)
def test_exact_blend_has_monotone_c2_jets_and_independently_integrated_shared_bound(
    requirements: tuple[TaperRequirement, ...],
) -> None:
    """
    Both ends share one budget; returned exact pieces join without endpoint or derivative gaps.
    """
    result = plan(requirements, Fraction(1, 100), check)
    assert result.status == "certified" and result.alpha is not None
    assert result.intervals[0].low == Fraction(0) and result.intervals[-1].high == Fraction(1)
    assert endpoint_jets(result.intervals[0], False) == (Fraction(0),) * 3
    assert endpoint_jets(result.intervals[-1], True) == (Fraction(1), Fraction(0), Fraction(0))
    for first, following in zip(result.intervals, result.intervals[1:]):
        assert first.high == following.low
        assert endpoint_jets(first, True) == endpoint_jets(following, False)
    assert all(
        piece.low < piece.high and all(a <= b for a, b in zip(piece.controls, piece.controls[1:]))
        for piece in result.intervals
    )
    energy = sum((velocity_energy(piece) for piece in result.intervals), Fraction(0))
    independent_bound = (
        sum(
            (value.displacement_mm**2 / (2 * value.length_mm) for value in requirements),
            Fraction(0),
        )
        * energy
    )
    assert result.discrepancy_upper_mm == independent_bound <= result.allowance_mm
    assert all(
        bound <= requirement.curvature_limit_per_mm
        for bound, requirement in zip(result.curvature_upper_per_mm, requirements)
    )
    acceleration = max(maximum_acceleration(piece) for piece in result.intervals)
    assert result.curvature_upper_per_mm == tuple(
        value.displacement_mm * acceleration / value.length_mm**2 for value in requirements
    )


def test_same_serial_chain_cannot_receive_an_allowance_per_ending() -> None:
    """
    Two individually admissible contributions can exhaust one aggregate sufficient certificate.
    """
    requirement = TaperRequirement(Fraction(1), Fraction(3, 25), Fraction(100))
    assert plan((requirement,), Fraction(1, 100), check).status == "certified"
    combined = plan((requirement, requirement), Fraction(1, 100), check)
    assert combined.status == "unresolved" and combined.intervals == ()
    assert "sufficient bound" in combined.reason


def test_curvature_conflict_is_unresolved_without_relaxing_radius_or_moving_targets() -> None:
    """
    Material allowance alone cannot license a cap ramp with excessive curvature.
    """
    requirement = TaperRequirement(Fraction(3, 4), Fraction(3, 40), Fraction(1, 10))
    result = plan((requirement,) * 2, Fraction(1, 100), check)
    assert result.status == "unresolved" and result.alpha is None and result.intervals == ()
    assert result.curvature_upper_per_mm[0] > requirement.curvature_limit_per_mm
    assert result.requirements == (requirement,) * 2


def test_dimensional_scaling_preserves_the_same_analytic_schedule() -> None:
    """
    Scaling all lengths/allowance and inverse curvature gives identical dimensionless controls.
    """
    first = TaperRequirement(Fraction(1, 4), Fraction(1, 40), Fraction(6))
    original = plan((first,) * 2, Fraction(1, 300), check)
    scaled = TaperRequirement(
        first.length_mm * 2, first.displacement_mm * 2, first.curvature_limit_per_mm / 2
    )
    larger = plan((scaled,) * 2, Fraction(1, 150), check)
    assert original.status == larger.status == "certified"
    assert original.alpha == larger.alpha and original.intervals == larger.intervals
    assert original.discrepancy_upper_mm is not None
    assert larger.discrepancy_upper_mm == 2 * original.discrepancy_upper_mm


def test_half_width_ramps_omit_zero_length_plateau() -> None:
    """
    A loose budget returns two smooth ramps, never an empty third interval.
    """
    result = plan(
        (TaperRequirement(Fraction(10), Fraction(1, 100), Fraction(1)),), Fraction(1, 100), check
    )
    assert result.status == "certified" and result.alpha == Fraction(1, 2)
    assert len(result.intervals) == 2


@pytest.mark.parametrize(
    "ratio",
    (
        Fraction(1) + Fraction(1, 10**20),
        Fraction(1001, 1000),
        Fraction(11, 10),
        Fraction(52, 35),
        Fraction(2),
    ),
)
def test_budget_root_never_overspends_under_fixed_rounding(ratio: Fraction) -> None:
    """
    Near-degenerate analytic roots remain unresolved rather than borrowing numerical slack.
    """
    requirement = TaperRequirement(Fraction(1), Fraction(1, 100), Fraction(10**30))
    allowance = Fraction(1, 20000) * ratio
    result = plan((requirement,), allowance, check)
    if result.status == "certified":
        independent_energy = sum(
            (velocity_energy(piece) for piece in result.intervals), Fraction(0)
        )
        assert Fraction(1, 20000) * independent_energy <= allowance
    else:
        assert ratio < Fraction(1001, 1000)
        assert result.intervals == () and result.alpha is None


def test_caller_stop_propagates_without_a_second_attempt() -> None:
    """
    The planner uses the same caller guard without catching cancellation or renewing work.
    """

    def stopped() -> None:
        """
        Represent an already exhausted caller allocation.
        """
        raise TimeoutError("latched")

    with pytest.raises(TimeoutError, match="latched"):
        plan((TaperRequirement(Fraction(1), Fraction(0), Fraction(0)),), Fraction(1, 100), stopped)


@pytest.mark.parametrize("allowance", (Fraction(0), Fraction(-1), Fraction(1), 0.01))
def test_invalid_or_expanded_allowance_is_not_silently_accepted(allowance: Fraction) -> None:
    """
    Exact explicit residual allowance cannot enlarge the user's whole-path dimensional rule.
    """
    with pytest.raises(ValueError, match="allowance"):
        plan((TaperRequirement(Fraction(1), Fraction(0), Fraction(0)),), allowance, check)
