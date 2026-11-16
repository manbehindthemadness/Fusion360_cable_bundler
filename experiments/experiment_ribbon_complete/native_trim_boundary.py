"""
Measure native UV boundary correspondence with a physically scaled parameter metric.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, derivative, elevate, multiply

from .native_material_chart import NativeSurfaceSnapshot

UV = tuple[Fraction, Fraction]


def derivative_bounds(
    surface: NativeSurfaceSnapshot, checkpoint: Callable[[], None]
) -> tuple[Fraction, Fraction]:
    """
    Bound both native surface partials in world L1 distance per original parameter unit.

    Require clamped U and quadratic V with the same positive V weights on every
    U row. The U derivative is a positive rational blend of ordinary B-spline
    control differences. The V quotient derivative is enclosed using degree-four
    elevated numerator coefficients divided by matching positive W² coefficients.
    No unit-speed or parameter-to-millimeter equivalence is assumed.
    """
    checkpoint()
    degree = surface.degree_u
    weights = surface.weights[0]
    low, high = surface.knots_u[degree], surface.knots_u[-degree - 1]
    if (
        surface.degree_v != 2
        or len(weights) != 3
        or any(row != weights for row in surface.weights)
        or surface.knots_v != (Fraction(0),) * 3 + (Fraction(1),) * 3
        or surface.knots_u[: degree + 1] != (low,) * (degree + 1)
        or surface.knots_u[-degree - 1 :] != (high,) * (degree + 1)
        or low >= high
    ):
        raise ValueError("Clamped native U and SAME positive quadratic V weights required")
    along = Fraction(0)
    for i, (first, second) in enumerate(zip(surface.rows, surface.rows[1:])):
        checkpoint()
        span = surface.knots_u[i + degree + 1] - surface.knots_u[i + 1]
        if span <= 0:
            raise ValueError("A positive native derivative control support required")
        along = max(
            along,
            max(sum((abs(b - a) for a, b in zip(p, q)), Fraction(0)) for p, q in zip(first, second))
            * degree
            / span,
        )
    denominator = multiply(weights, weights)
    across = Fraction(0)
    for row in surface.rows:
        checkpoint()
        axes = []
        for k in range(3):
            numerator = tuple(p[k] * w for p, w in zip(row, weights))
            axes.append(
                elevate(
                    add(
                        multiply(derivative(numerator), weights),
                        multiply(numerator, derivative(weights)),
                        Fraction(-1),
                    ),
                    4,
                )
            )
        across = max(
            across,
            max(
                sum((abs(axis[j]) for axis in axes), Fraction(0)) / w
                for j, w in enumerate(denominator)
            ),
        )
    return along, across


@dataclass(frozen=True)
class NativeTrimCurve:
    """
    Retain one complete positive-weight Bezier co-edge trace in original native UV coordinates.

    Capture adapters verify the original clamped single-span knots and loop/edge
    ownership. The controls are not snapped or reversed using an inferred convention.
    """

    edge_id: int
    controls: tuple[UV, ...]
    weights: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        """
        Require nonempty bounded traces and exact nonnegative-basis data.
        """
        if (
            type(self.edge_id) is not int
            or self.edge_id < 0
            or len(self.controls) < 2
            or len(self.controls) != len(self.weights)
            or any(len(p) != 2 or any(type(x) is not Fraction for x in p) for p in self.controls)
            or any(type(w) is not Fraction or w <= 0 for w in self.weights)
        ):
            raise ValueError("Complete exact native UV controls and positive weights required")


@dataclass(frozen=True)
class RectangleBoundaryBound:
    """
    Retain parameter-metric boundary discrepancy, not a native material-domain pass.

    Endpoint gaps and boundary collars remain explicit. This receipt does not
    fill the trim interior, assign a world inverse, glue adjacent material maps,
    or replace an original co-edge with an ideal rectangular edge.
    """

    surface: NativeSurfaceSnapshot
    curves: tuple[NativeTrimCurve, ...]
    derivative_upper: tuple[Fraction, Fraction]
    side_indices: tuple[int, ...]
    boundary_upper_mm: Fraction
    endpoint_gap_upper_mm: Fraction
    ordered_sides: bool
    controls_inside_parameter_domain: bool
    status: str


def inspect_rectangle(
    surface: NativeSurfaceSnapshot,
    curves: tuple[NativeTrimCurve, ...],
    checkpoint: Callable[[], None],
) -> RectangleBoundaryBound:
    """
    Bound each co-edge against its nearest original rectangle side in the native derivative metric.

    Positive rational convexity bounds every trace point, including cubic traces.
    Uniform surface partial bounds scale UV differences into millimeters. The
    cyclic side sequence must visit each side once, with split edges kept together.
    This is boundary correspondence only; unresolved endpoint/model consistency
    and whole trimmed-domain coverage must not be silently promoted to acceptance.
    For controls outside the original surface domain this metric is only a
    coordinate discrepancy: derivative bounds do not establish extrapolation or
    a world-space boundary error. Such coordinates remain explicit and untouched.
    """
    checkpoint()
    if not curves or len({c.edge_id for c in curves}) != len(curves):
        raise ValueError("A complete original outer loop with unique native edges required")
    along, across = derivative_bounds(surface, checkpoint)
    low, high = surface.knots_u[surface.degree_u], surface.knots_u[-surface.degree_u - 1]
    sides = []
    maximum = Fraction(0)
    for curve in curves:
        checkpoint()
        candidates: list[Fraction] = []
        for axis, fixed in ((1, Fraction(0)), (0, high), (1, Fraction(1)), (0, low)):
            error = max(
                along * (abs(u - fixed) if axis == 0 else max(low - u, u - high, Fraction(0)))
                + across * (abs(v - fixed) if axis == 1 else max(-v, v - 1, Fraction(0)))
                for u, v in curve.controls
            )
            candidates.append(Fraction(error))
        side = min(range(4), key=lambda i: candidates[i])
        sides.append(side)
        maximum = max(maximum, candidates[side])
    gap = max(
        along * abs(a.controls[-1][0] - b.controls[0][0])
        + across * abs(a.controls[-1][1] - b.controls[0][1])
        for a, b in zip(curves, curves[1:] + curves[:1])
    )
    sequence = [side for i, side in enumerate(sides) if side != sides[i - 1]]
    ordered = len(sequence) == 4 and all(
        (b - a) % 4 == 1 for a, b in zip(sequence, sequence[1:] + sequence[:1])
    )
    ordered = ordered or (
        len(sequence) == 4
        and all((a - b) % 4 == 1 for a, b in zip(sequence, sequence[1:] + sequence[:1]))
    )
    inside = all(low <= u <= high and 0 <= v <= 1 for curve in curves for u, v in curve.controls)
    status = (
        "within_parameter_boundary_accuracy"
        if ordered and max(maximum, gap) <= Fraction(1, 100)
        else "unresolved_parameter_boundary_accuracy"
    )
    checkpoint()
    return RectangleBoundaryBound(
        surface, curves, (along, across), tuple(sides), maximum, gap, ordered, inside, status
    )
