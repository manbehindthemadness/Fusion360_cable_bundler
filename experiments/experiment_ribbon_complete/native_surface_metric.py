"""
Bound physical distances over complete rational native tensor domains without uniform parameterization assumptions.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from .native_material_chart import NativeSurfaceSnapshot


def rational_partial_bounds(
    surface: NativeSurfaceSnapshot, checkpoint: Callable[[], None]
) -> tuple[Fraction, Fraction]:
    """
    Bound world L1 derivatives per native U/V unit on a complete clamped positive-weight tensor rectangle.

    Homogeneous numerator and denominator derivatives use exact B-spline control
    differences, including original knot spans. Positive partition of unity
    bounds N, W, N' and W', hence |(N'W-NW')/W²|. A common world translation is
    removed before bounding N; it changes neither the surface derivatives nor
    the original data. Bounds apply across continuous interior knots, including
    corners with one-sided derivatives, and integrate to a global distance bound.
    They do not establish trim membership, invertibility or material accuracy.

    Raise ValueError for nonclamped, empty or discontinuous knot domains. The
    snapshot already requires finite exact controls and positive tensor weights.
    """
    checkpoint()
    center = surface.rows[0][0]
    homogeneous = tuple(
        tuple(tuple((x - c) * w for x, c in zip(point, center)) for point, w in zip(row, weights))
        for row, weights in zip(surface.rows, surface.weights)
    )
    minimum_weight = min(w for row in surface.weights for w in row)
    maximum_weight = max(w for row in surface.weights for w in row)
    numerator = max(sum(map(abs, point)) for row in homogeneous for point in row)
    result = []
    for degree, knots, values, weights in (
        (surface.degree_u, surface.knots_u, homogeneous, surface.weights),
        (
            surface.degree_v,
            surface.knots_v,
            tuple(zip(*homogeneous)),
            tuple(zip(*surface.weights)),
        ),
    ):
        checkpoint()
        low, high = knots[degree], knots[-degree - 1]
        if (
            len(values) <= degree
            or low >= high
            or knots[: degree + 1] != (low,) * (degree + 1)
            or knots[-degree - 1 :] != (high,) * (degree + 1)
        ):
            raise ValueError("Complete continuous clamped native knot domains required")
        numerator_derivative = Fraction(0)
        weight_derivative = Fraction(0)
        for i, (first, second) in enumerate(zip(values, values[1:])):
            checkpoint()
            span = knots[i + degree + 1] - knots[i + 1]
            if span <= 0:
                raise ValueError("Continuous positive native derivative supports required")
            scale = degree / span
            numerator_derivative = max(
                numerator_derivative,
                max(sum(abs(b - a) for a, b in zip(p, q)) for p, q in zip(first, second)) * scale,
            )
            weight_derivative = max(
                weight_derivative,
                max(abs(b - a) for a, b in zip(weights[i], weights[i + 1])) * scale,
            )
        result.append(
            (numerator_derivative * maximum_weight + numerator * weight_derivative)
            / minimum_weight**2
        )
    checkpoint()
    return result[0], result[1]
