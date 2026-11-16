"""
Challenge whole-tensor parameter metrics with nonuniform rational weights, multiple spans and independent world units.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_surface_metric import rational_partial_bounds
from tests.test_ribbon_complete_native_trim_boundary import surface
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_affine_scaling_and_translation_do_not_assume_native_units_are_millimeters() -> None:
    """
    Independent physical U/V speeds are exact and remain unchanged under a large world translation.
    """
    original = surface(2, 7)
    expected = Fraction(2), Fraction(7)
    assert rational_partial_bounds(original, checkpoint) == expected
    shifted = replace(
        original,
        rows=tuple(tuple(tuple(x + 10**9 for x in p) for p in row) for row in original.rows),
    )
    assert rational_partial_bounds(shifted, checkpoint) == expected


def test_nonuniform_weights_on_both_axes_bound_independent_quotient_derivatives() -> None:
    """
    A rational bilinear patch has nonconstant derivatives even though all its controls form a rectangle.
    """
    original = surface()
    zero, one = Fraction(0), Fraction(1)
    patch = replace(
        original,
        degree_u=1,
        degree_v=1,
        knots_u=(zero, zero, one, one),
        knots_v=(zero, zero, one, one),
        rows=(((zero, zero, zero), (zero, one, zero)), ((one, zero, zero), (one, one, zero))),
        weights=((one, Fraction(2)), (Fraction(3), Fraction(5))),
    )
    along, across = rational_partial_bounds(patch, checkpoint)
    for u in (zero, Fraction(1, 3), one):
        for v in (zero, Fraction(2, 3), one):
            # Independent closed form: N=(3u+2uv,2v+3uv), W=1+2u+v+uv.
            w = 1 + 2 * u + v + u * v
            x, y = 3 * u + 2 * u * v, 2 * v + 3 * u * v
            du = abs(((3 + 2 * v) * w - x * (2 + v)) / w**2) + abs((3 * v * w - y * (2 + v)) / w**2)
            dv = abs((2 * u * w - x * (1 + u)) / w**2) + abs(((2 + 3 * u) * w - y * (1 + u)) / w**2)
            assert du <= along and dv <= across


def test_multiple_original_knot_spans_keep_their_physical_parameter_scale() -> None:
    """
    A continuous piecewise linear native U coordinate uses each original span rather than a unit-span guess.
    """
    original = surface()
    zero, one = Fraction(0), Fraction(1)
    patch = replace(
        original,
        degree_u=1,
        knots_u=(zero, zero, Fraction(1, 4), one, one),
        rows=(original.rows[0], original.rows[3], original.rows[-1]),
        weights=(original.weights[0],) * 3,
    )
    assert rational_partial_bounds(patch, checkpoint) == (Fraction(12, 5), one)
    discontinuous = replace(
        patch,
        knots_u=(zero, zero, Fraction(1, 4), Fraction(1, 4), one, one),
        rows=(patch.rows[0], patch.rows[1], patch.rows[1], patch.rows[2]),
        weights=(patch.weights[0],) * 4,
    )
    with pytest.raises(ValueError, match="Continuous positive"):
        rational_partial_bounds(discontinuous, checkpoint)


def test_parameter_extrapolation_and_stopped_allocations_cannot_gain_metric_bounds() -> None:
    """
    Nonclamped domains and a stopped caller are refused before a physical distance claim can be made.
    """
    original = surface()
    nonclamped = replace(original, knots_u=(Fraction(-1),) + original.knots_u[1:])
    with pytest.raises(ValueError, match="clamped"):
        rational_partial_bounds(nonclamped, checkpoint)

    def stop() -> None:
        """
        Refuse metric work once the shared allocation is exhausted.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        rational_partial_bounds(original, stop)
