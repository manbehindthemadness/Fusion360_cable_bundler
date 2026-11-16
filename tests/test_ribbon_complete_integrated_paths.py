"""
Check integrated absolute bounds against independent speed inequalities and cancellation.
"""

from __future__ import annotations

import math
from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.material_paths import (
    enclose,
    square_root_lower,
    witness,
)
from experiments.experiment_ribbon_complete.spatial_frame import FrameSpan
from tests.test_ribbon_complete_lengths import checkpoint
from tests.test_ribbon_complete_material_paths import frame, patches


def taper(length: float, delta: float) -> FrameSpan:
    """
    Supply a straight center and endpoint-flat transverse motion with independent closed-form speed.
    """
    return replace(
        frame(),
        center=(Vector3(0, 0, 0), Vector3(length, 0, 0)),
        width=(Vector3(0, 1, 0),) * 3 + (Vector3(0, 1 + delta, 0),) * 3,
    )


@pytest.mark.parametrize("length,delta", ((0.75, 0.2), (3.0, -0.4), (0.5, 1.0)))
def test_quintic_transverse_motion_encloses_independent_speed_integral(
    length: float, delta: float
) -> None:
    """
    For Y=q*delta*beta, integrate beta-prime squared by the factorial beta integral.

    With constant center speed L, the excess is Y-prime squared divided by
    sqrt(L squared+Y-prime squared)+L. Independent global slope bounds therefore
    bracket its entire integral. No sampled quadrature or implementation residual
    coefficients serve as the reference answer.
    """
    geometry = patches(taper(length, delta))
    patch = max(geometry, key=lambda p: abs(p.section.rows[0][-1][0] / p.section.rows[0][-1][2]))
    source = patch.section.rows[0][-1]
    q = source[0] / source[2]
    displacement = q * (Fraction(1 + delta) - 1)
    beta_integral = Fraction(30**2 * math.factorial(4) ** 2, math.factorial(9))
    square_integral = displacement**2 * beta_integral
    speed = Fraction(length)
    upper = square_integral / (2 * speed)
    slope = Fraction(15, 8) * abs(displacement)
    root_lower = square_root_lower(speed**2 + slope**2)
    root_upper = root_lower + Fraction(1, 1 << 40)
    lower = square_integral / (root_upper + speed)
    result = enclose(patch, checkpoint, edge_coordinate=Fraction(1))
    assert result.discrepancy_upper_mm is not None
    assert lower <= result.discrepancy_upper_mm <= upper
    if length == 0.75:
        assert result.discrepancy_upper_mm <= Fraction(1, 100)
    if length == 0.5:
        assert lower > Fraction(1, 100)
        assert result.discrepancy_upper_mm > Fraction(1, 100)


def test_signed_returning_motion_cannot_cancel_under_coefficient_integration() -> None:
    """
    Equal endpoint offsets hide a quarter-millimeter local length mismatch, which must remain bounded.
    """
    returning = replace(frame(), width=(Vector3(0, 1, 0), Vector3(1, 1, 0), Vector3(0, 1, 0)))
    patch = max(
        patches(returning), key=lambda p: abs(p.section.rows[0][-1][0] / p.section.rows[0][-1][2])
    )
    bound = enclose(patch, checkpoint, edge_coordinate=Fraction(1))
    local = witness(patch, Fraction(0), Fraction(1, 2), Fraction(1), checkpoint)
    assert local.violation and local.excess_lower_mm > Fraction(1, 100)
    assert bound.discrepancy_upper_mm is not None
    assert bound.discrepancy_upper_mm >= local.excess_lower_mm


def test_uniform_rectangle_bound_covers_fixed_transverse_traces() -> None:
    """
    The whole-edge bound covers each exact transverse restriction without selecting a favorable trace.
    """
    patch = patches(taper(2, 0.3))[0]
    whole = enclose(patch, checkpoint)
    assert whole.discrepancy_upper_mm is not None
    for v in (Fraction(0), Fraction(1, 3), Fraction(1, 2), Fraction(1)):
        trace = enclose(patch, checkpoint, edge_coordinate=v)
        assert trace.discrepancy_upper_mm is not None
        assert trace.discrepancy_upper_mm <= whole.discrepancy_upper_mm
