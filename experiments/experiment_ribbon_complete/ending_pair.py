"""
Enclose paired material speeds on the original rational midplane ending traces.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import Polynomial, multiply

from .curve_lengths import distance
from .material_paths import square_root_lower
from .spatial_frame import differentiated, split_at
from .spatial_transition import SpatialPatch, compose


def absolute_integral(values: Polynomial) -> Fraction:
    """
    Enclose the integral of an absolute Bernstein polynomial without signed cancellation.
    """
    return sum((abs(value) for value in values), Fraction(0)) / len(values)


@dataclass(frozen=True)
class TraceDerivative:
    """
    Retain original rational derivative controls, convex-hull positions and axis-motion error.
    """

    numerator: Polynomial
    weights: Polynomial
    positions: Polynomial
    remainder: Fraction


def derivative_data(
    patch: SpatialPatch, coordinate: Fraction, checkpoint: Callable[[], None]
) -> TraceDerivative | None:
    """
    Extract q'=D/w² and the actual width-motion remainder with positive source weights.

    The rational convex hull bounds |q|. Integrating absolute derivative coefficients
    bounds total variation even without assuming monotonic motion. No width axis is
    normalized, and its original derivative contribution is retained.
    """
    checkpoint()
    original = compose(patch.section, patch.frame, checkpoint)
    if original.rows != patch.rows or original.section_rows != patch.section_rows:
        raise ValueError("Ending material certificate cannot transfer to changed geometry")
    samples = tuple(
        tuple(split_at(tuple(p[k] for p in row), coordinate)[0][-1] for k in range(3))
        for row in patch.section_rows
    )
    if any(value[1] or value[2] <= 0 for value in samples):
        return None
    numerator = tuple(value[0] for value in samples)
    weights = tuple(value[2] for value in samples)
    degree = len(weights) - 1
    dq = tuple(degree * (b - a) for a, b in zip(numerator, numerator[1:]))
    dw = tuple(degree * (b - a) for a, b in zip(weights, weights[1:]))
    derivative = tuple(a - b for a, b in zip(multiply(dq, weights), multiply(numerator, dw)))
    width = patch.frame.fields()[1]
    errors = tuple(tuple(value - axis[0] for value in axis) for axis in width)
    error_max = tuple(max(abs(value) for value in axis) for axis in errors)
    motion_max = tuple(
        max((abs((len(axis) - 1) * (b - a)) for a, b in zip(axis, axis[1:])), default=Fraction(0))
        for axis in errors
    )
    zero = (Fraction(0),) * 3
    remainder = (
        distance(zero, motion_max)[1] * max(abs(n / w) for n, w in zip(numerator, weights))
        + distance(zero, error_max)[1] * absolute_integral(derivative) / min(weights) ** 2
    )
    return TraceDerivative(
        derivative, weights, tuple(n / w for n, w in zip(numerator, weights)), remainder
    )


def frame_metrics(patch: SpatialPatch) -> tuple[Fraction, Fraction, Fraction]:
    """
    Enclose original center speed squared and its cross term with the frozen width axis.
    """
    center, width, _ = patch.frame.fields()
    velocity = differentiated(center)
    squared = [Fraction(0)] * (2 * len(velocity[0]) - 1)
    cross = [Fraction(0)] * len(velocity[0])
    for axis in range(3):
        for i, value in enumerate(multiply(velocity[axis], velocity[axis])):
            squared[i] += value
        for i, value in enumerate(velocity[axis]):
            cross[i] += value * width[axis][0]
    return (
        min(squared),
        max(abs(value) for value in cross),
        sum((axis[0] ** 2 for axis in width), Fraction(0)),
    )


def bound(
    first: SpatialPatch,
    first_coordinate: Fraction,
    second: SpatialPatch,
    second_coordinate: Fraction,
    checkpoint: Callable[[], None],
) -> Fraction | None:
    """
    Bound integral |speed(left)-speed(right)| directly, never canceling signed increments.

    With frozen W0, squared speeds differ by 2(C'·W0)(q1'-q2') plus
    |W0|²(q1'²-q2'²). Exact common-denominator polynomials retain pointwise
    cancellation before absolute integration. Identical weights are canceled
    algebraically first. Positive speed lower bounds justify division by the
    sum of speeds. Actual W-W0 motion contributes both additive remainders.
    Unsupported charts or nonpositive lower bounds return no certificate.
    """
    checkpoint()
    a = derivative_data(first, first_coordinate, checkpoint)
    b = derivative_data(second, second_coordinate, checkpoint)
    if first.frame != second.frame:
        return None
    if a is None or b is None:
        return None
    da, wa, ra = a.numerator, a.weights, a.remainder
    db, wb, rb = b.numerator, b.weights, b.remainder
    if wa == wb:
        difference = tuple(x - y for x, y in zip(da, db))
        square_difference = tuple(x - y for x, y in zip(multiply(da, da), multiply(db, db)))
        derivative_integral = absolute_integral(difference) / min(wa) ** 2
        square_integral = absolute_integral(square_difference) / min(wa) ** 4
    else:
        aw = multiply(da, multiply(wb, wb))
        bw = multiply(db, multiply(wa, wa))
        if len(aw) != len(bw):
            return None
        difference = tuple(x - y for x, y in zip(aw, bw))
        square_difference = multiply(difference, tuple(x + y for x, y in zip(aw, bw)))
        denominator = min(wa) ** 2 * min(wb) ** 2
        derivative_integral = absolute_integral(difference) / denominator
        square_integral = absolute_integral(square_difference) / denominator**2
    reference_squared, cross_max, width_squared = frame_metrics(first)
    low_a = reference_squared - 2 * cross_max * max(abs(v) for v in da) / min(wa) ** 2
    low_b = reference_squared - 2 * cross_max * max(abs(v) for v in db) / min(wb) ** 2
    if min(low_a, low_b) <= 0:
        return None
    denominator = square_root_lower(low_a) + square_root_lower(low_b)
    if denominator <= 0:
        return None
    checkpoint()
    return (
        (2 * cross_max * derivative_integral + width_squared * square_integral) / denominator
        + ra
        + rb
    )
