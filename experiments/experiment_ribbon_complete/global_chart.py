"""
Certify global injectivity of the actual branch ambient chart on one convex source envelope.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from artifacts.verification.resume3204.polynomial import add, elevate

from .branch_reference import validate_spans
from .ruled_support import square_root_upper
from .spatial_frame import FrameSpan, differentiated

Triple = tuple[Fraction, Fraction, Fraction]
Matrix = tuple[Triple, Triple, Triple]


def cross(a: Triple, b: Triple) -> Triple:
    """
    Form an exact root-basis cofactor without normalizing its physical axes.
    """
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def inverse(a: Triple, b: Triple, c: Triple) -> Matrix | None:
    """
    Invert a three-column basis exactly, retaining singularity as unresolved evidence.
    """
    first, second, third = cross(b, c), cross(c, a), cross(a, b)
    determinant = sum((x * y for x, y in zip(a, first)), Fraction(0))
    if determinant == Fraction(0):
        return None
    return (
        (first[0] / determinant, first[1] / determinant, first[2] / determinant),
        (second[0] / determinant, second[1] / determinant, second[2] / determinant),
        (third[0] / determinant, third[1] / determinant, third[2] / determinant),
    )


@dataclass(frozen=True)
class GlobalChart:
    """
    Retain a sufficient injectivity/conditioning proof, not a material-transport or contact claim.
    """

    status: str
    inverse_root_basis: Matrix | None
    minimum_monotonicity: Fraction | None
    condition_upper: Fraction | None
    coefficient_matrices: int
    q_bounds_mm: tuple[Fraction, Fraction]
    b_bounds_mm: tuple[Fraction, Fraction]


def certify(
    frames: tuple[FrameSpan, ...],
    q_bounds: tuple[Fraction, Fraction],
    b_bounds: tuple[Fraction, Fraction],
    checkpoint: Callable[[], None],
) -> GlobalChart:
    """
    Prove B^-1*F strongly monotone over the entire convex u/q/b box.

    F=C(u)+qW(u)+bN(u). B is the exact root Jacobian at q=b=0,
    fixed once. Domain coordinates use numerical mm and u times a fixed1mm unit;
    this is a proof convention, not a physical accuracy gate or fitted parameter.
    The symmetric part is affine in q/b and polynomial in each original span.
    Strict diagonal dominance of every corner Bernstein coefficient matrix gives
    one positive lower bound throughout the box. Integrating along a straight
    source segment proves injectivity; mere positive local Jacobians do not.
    Exact source closure transfers the argument across piecewise-polynomial spans.

    A Frobenius bound on actual J and B^-1 gives a conservative condition bound,
    retaining the existing1024numerical-conditioning ceiling. A failed sufficient
    bound is unresolved, never evidence of infeasibility. No subdivision, solver
    work reserve, geometry change or normalization is introduced.
    """
    checkpoint()
    validate_spans(frames, checkpoint)
    if not q_bounds[0] < q_bounds[1] or not b_bounds[0] < b_bounds[1]:
        raise ValueError("One increasing common physical q/b envelope is required")
    root = frames[0]
    center, width, thickness = root.fields()
    h = root.high - root.low
    dc = differentiated(center)
    inv = inverse(
        (dc[0][0] / h, dc[1][0] / h, dc[2][0] / h),
        (width[0][0], width[1][0], width[2][0]),
        (thickness[0][0], thickness[1][0], thickness[2][0]),
    )
    if inv is None:
        return GlobalChart("unresolved", None, None, None, 0, q_bounds, b_bounds)
    minimum: Fraction | None = None
    norm_squared = Fraction(0)
    count = 0
    for frame in frames:
        checkpoint()
        center, width, thickness = frame.fields()
        h = frame.high - frame.low
        dc, dw, dn = (
            tuple(tuple(x / h for x in field) for field in differentiated(values))
            for values in (center, width, thickness)
        )
        for q, b in product(q_bounds, b_bounds):
            checkpoint()
            along = tuple(add(add(dc[k], dw[k], q), dn[k], b) for k in range(3))
            columns = (along, width, thickness)
            degree = max(len(field) - 1 for column in columns for field in column)
            columns = tuple(tuple(elevate(field, degree) for field in column) for column in columns)
            for index in range(degree + 1):
                checkpoint()
                actual = tuple(tuple(columns[j][i][index] for j in range(3)) for i in range(3))
                transformed = tuple(
                    tuple(
                        sum((inv[i][k] * actual[k][j] for k in range(3)), Fraction(0))
                        for j in range(3)
                    )
                    for i in range(3)
                )
                symmetric = tuple(
                    tuple((transformed[i][j] + transformed[j][i]) / Fraction(2) for j in range(3))
                    for i in range(3)
                )
                lower = min(
                    symmetric[i][i]
                    - sum((abs(symmetric[i][j]) for j in range(3) if i != j), Fraction(0))
                    for i in range(3)
                )
                minimum = lower if minimum is None else min(minimum, lower)
                norm_squared = max(
                    norm_squared, sum((x * x for row in actual for x in row), Fraction(0))
                )
                count += 1
    condition = None
    if minimum is not None and minimum > Fraction(0):
        inverse_squared = sum((x * x for row in inv for x in row), Fraction(0))
        condition = square_root_upper(norm_squared) * square_root_upper(inverse_squared) / minimum
    return GlobalChart(
        "certified" if condition is not None and condition <= 1024 else "unresolved",
        inv,
        minimum,
        condition,
        count,
        q_bounds,
        b_bounds,
    )
