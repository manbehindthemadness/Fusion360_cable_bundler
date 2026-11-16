"""
Compare exact whole-curve composition with independent rational evaluation and reject unsupported domain substitutions.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.native_material_chart import NativeSurfaceSnapshot
from experiments.experiment_ribbon_complete.native_surface_trace import NativeSurfaceTrace
from experiments.experiment_ribbon_complete.native_trim_boundary import NativeTrimCurve
from tests.test_ribbon_complete_native_trim_boundary import surface
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def patch() -> NativeSurfaceSnapshot:
    """
    Retain a nonseparable rational tensor with nonunit native parameter ranges.
    """
    original = surface(2, 3)
    return replace(
        original,
        degree_u=1,
        knots_u=(Fraction(-2),) * 2 + (Fraction(4),) * 2,
        knots_v=(Fraction(5),) * 3 + (Fraction(7),) * 3,
        rows=(original.rows[0], original.rows[-1]),
        weights=((Fraction(1), Fraction(2), Fraction(3)), (Fraction(2), Fraction(3), Fraction(5))),
    )


def test_rational_uv_and_tensor_weights_match_independent_nested_evaluation() -> None:
    """
    Two independent rational denominators and nonunit domains must compose without assuming parameter identity.
    """
    native = patch()
    curve = NativeTrimCurve(
        8,
        (
            (Fraction(-1), Fraction(26, 5)),
            (Fraction(4), Fraction(61, 10)),
            (Fraction(2), Fraction(7)),
        ),
        (Fraction(1), Fraction(3, 2), Fraction(2)),
    )
    trace = NativeSurfaceTrace(native, curve, checkpoint)
    assert trace.surface is native and trace.curve is curve and min(trace.denominator) > 0
    for t in (Fraction(0), Fraction(1, 3), Fraction(1)):
        blend: tuple[Fraction, ...] = (
            (1 - t) * (1 - t) * curve.weights[0],
            2 * t * (1 - t) * curve.weights[1],
            t * t * curve.weights[2],
        )
        uv: tuple[Fraction, ...] = tuple(
            sum((w * p[k] for p, w in zip(curve.controls, blend)), Fraction(0))
            / sum(blend, Fraction(0))
            for k in range(2)
        )
        u, v = (uv[0] + 2) / 6, (uv[1] - 5) / 2
        basis = tuple(
            tuple(a * b * w for b, w in zip(((1 - v) * (1 - v), 2 * v * (1 - v), v * v), weights))
            for a, weights in zip((1 - u, u), native.weights)
        )
        denominator = sum(sum(row) for row in basis)
        expected = tuple(
            sum(p[k] * w for points, row in zip(native.rows, basis) for p, w in zip(points, row))
            / denominator
            for k in range(3)
        )
        assert trace.point(t, checkpoint) == expected
    reverse = NativeSurfaceTrace(
        native,
        replace(
            curve, controls=tuple(reversed(curve.controls)), weights=tuple(reversed(curve.weights))
        ),
        checkpoint,
    )
    assert reverse.point(Fraction(1, 3), checkpoint) == trace.point(Fraction(2, 3), checkpoint)


def test_whole_curve_coefficients_expose_a_bow_that_matching_endpoints_miss() -> None:
    """
    An interior deviation remains present in the composed world curve and affine residual coefficients.
    """
    zero, one = Fraction(0), Fraction(1)
    curve = NativeTrimCurve(3, ((zero, zero), (Fraction(1, 2), one), (one, zero)), (one,) * 3)
    trace = NativeSurfaceTrace(surface(), curve, checkpoint)
    assert trace.point(zero, checkpoint)[1] == trace.point(one, checkpoint)[1] == zero
    assert trace.point(Fraction(1, 2), checkpoint)[1] == Fraction(1, 2)
    numerator = trace.affine_numerator((zero, one, zero), zero)
    assert max(n / d for n, d in zip(numerator, trace.denominator)) >= Fraction(1, 2)


def test_outside_controls_multispan_surfaces_and_stale_evaluation_parameters_are_rejected() -> None:
    """
    Positive composition cannot certify extrapolation or silently reinterpret an unsupported original basis.
    """
    native = patch()
    curve = NativeTrimCurve(
        8, ((Fraction(-2), Fraction(5)), (Fraction(4), Fraction(7))), (Fraction(1),) * 2
    )
    outside = replace(curve, controls=(curve.controls[0], (Fraction(4), Fraction(7001, 1000))))
    with pytest.raises(ValueError, match="natural domains"):
        NativeSurfaceTrace(native, outside, checkpoint)
    multiple = replace(
        native,
        rows=(native.rows[0], native.rows[0], native.rows[1]),
        weights=(native.weights[0], native.weights[0], native.weights[1]),
        knots_u=(Fraction(-2), Fraction(-2), Fraction(0), Fraction(4), Fraction(4)),
    )
    with pytest.raises(ValueError, match="Single-span"):
        NativeSurfaceTrace(multiple, curve, checkpoint)
    trace = NativeSurfaceTrace(native, curve, checkpoint)
    with pytest.raises(ValueError, match="unit trace"):
        trace.point(Fraction(2), checkpoint)


def test_stopped_allocation_prevents_composition() -> None:
    """
    New coefficient work cannot begin after the caller's fixed allocation stops.
    """
    curve = NativeTrimCurve(
        8, ((Fraction(-2), Fraction(5)), (Fraction(4), Fraction(7))), (Fraction(1),) * 2
    )

    def stop() -> None:
        """
        Preserve a stopped allocation before any substitution begins.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeSurfaceTrace(patch(), curve, stop)
