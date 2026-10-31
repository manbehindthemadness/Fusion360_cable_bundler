"""
Certify polynomial curvature on the entire parameter interval using exact arithmetic.

The certificate concerns the ideal curve whose controls are the supplied floats.
It does not certify a native interpolant, material strain, or global contact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from cable_bundler.routing.geometry import Vector3

Polynomial = tuple[Fraction, ...]
Condition = tuple[str, Polynomial, bool]


@dataclass(frozen=True)
class CurvatureCertificate:
    """
    Retain a continuous proof, a violating interval, or an unresolved subdivision.
    """

    status: str
    nodes: int
    interval: tuple[float, float] | None
    condition: str | None


def _product(a: Polynomial, b: Polynomial) -> Polynomial:
    """
    Multiply Bernstein polynomials without changing their represented values.
    """
    m, n = len(a) - 1, len(b) - 1
    return tuple(
        Fraction(
            sum(
                (
                    a[i] * b[k - i] * math.comb(m, i) * math.comb(n, k - i)
                    for i in range(max(0, k - n), min(m, k) + 1)
                ),
                Fraction(0),
            ),
            math.comb(m + n, k),
        )
        for k in range(m + n + 1)
    )


def _elevate(row: Polynomial, degree: int) -> Polynomial:
    """
    Elevate a scalar polynomial exactly to the requested degree.
    """
    while len(row) <= degree:
        n = len(row)
        row = (
            (row[0],)
            + tuple((i * row[i - 1] + (n - i) * row[i]) / n for i in range(1, n))
            + (row[-1],)
        )
    return row


def _subtract(a: Polynomial, b: Polynomial) -> Polynomial:
    """
    Subtract two polynomials after matching their degrees.
    """
    degree = max(len(a), len(b)) - 1
    return tuple(x - y for x, y in zip(_elevate(a, degree), _elevate(b, degree)))


def _split(row: Polynomial) -> tuple[Polynomial, Polynomial]:
    """
    Restrict a polynomial to the two closed half intervals exactly.
    """
    left, right = [row[0]], [row[-1]]
    while len(row) > 1:
        row = tuple((x + y) / 2 for x, y in zip(row, row[1:]))
        left.append(row[0])
        right.append(row[-1])
    return tuple(left), tuple(reversed(right))


def _sum_rows(rows: tuple[Polynomial, ...]) -> Polynomial:
    """
    Add equal-degree exact polynomials without integer-seeded generic summation.
    """
    values: list[Fraction] = [Fraction(0)] * len(rows[0])
    for row in rows:
        for i, value in enumerate(row):
            values[i] += value
    return tuple(values)


def certify_curvature(
    points: tuple[Vector3, ...],
    maximum: Fraction,
    *,
    require_frame: bool = True,
    maximum_nodes: int = 1024,
    maximum_depth: int = 24,
    checkpoint: Callable[[], None] | None = None,
) -> CurvatureCertificate:
    """
    Prove speed>0 and curvature<=maximum, optionally requiring nonzero curvature.

    For G=|r'|² and A=|r' cross r''|² the curvature condition is
    maximum² G³-A>=0. Exact Bernstein convex hull bounds and dyadic subdivision
    cover the entire interval. An unresolved bound never becomes a pass.
    """
    if (
        len(points) < 3
        or any(not math.isfinite(x) for p in points for x in (p.x, p.y, p.z))
        or not isinstance(maximum, Fraction)
        or maximum <= 0
        or isinstance(maximum_nodes, bool)
        or not isinstance(maximum_nodes, int)
        or maximum_nodes < 1
        or isinstance(maximum_depth, bool)
        or not isinstance(maximum_depth, int)
        or maximum_depth < 0
    ):
        raise ValueError(
            "Finite controls, positive rational curvature and finite budgets required."
        )
    coordinates = tuple(
        tuple(Fraction(x) for x in axis) for axis in zip(*((p.x, p.y, p.z) for p in points))
    )
    degree = len(points) - 1
    velocity = tuple(tuple(degree * (b - a) for a, b in zip(row, row[1:])) for row in coordinates)
    acceleration = tuple(
        tuple((degree - 1) * (b - a) for a, b in zip(row, row[1:])) for row in velocity
    )
    cross_rows = tuple(
        _subtract(_product(velocity[i], acceleration[j]), _product(velocity[j], acceleration[i]))
        for i, j in ((1, 2), (2, 0), (0, 1))
    )
    speed_squared = _sum_rows(tuple(_product(row, row) for row in velocity))
    cross_squared = _sum_rows(tuple(_product(row, row) for row in cross_rows))
    speed_sixth = _product(_product(speed_squared, speed_squared), speed_squared)
    bound = _subtract(tuple(maximum**2 * x for x in speed_sixth), cross_squared)
    conditions: tuple[Condition, ...] = (
        ("speed", speed_squared, True),
        ("curvature", bound, False),
    )
    if require_frame:
        conditions += (("frame", cross_squared, True),)
    pending: list[tuple[tuple[Condition, ...], int, Fraction, Fraction]] = [
        (conditions, 0, Fraction(0), Fraction(1))
    ]
    nodes = 0
    while pending:
        if checkpoint is not None:
            checkpoint()
        if nodes >= maximum_nodes:
            rows, _, low, high = pending[-1]
            return CurvatureCertificate("unresolved", nodes, (float(low), float(high)), rows[0][0])
        rows, depth, low, high = pending.pop()
        nodes += 1
        remaining = []
        for name, row, strict in rows:
            if row[0] < 0 or row[-1] < 0 or (strict and (row[0] == 0 or row[-1] == 0)):
                return CurvatureCertificate("violated", nodes, (float(low), float(high)), name)
            if min(row) > 0 or (not strict and min(row) >= 0):
                continue
            remaining.append((name, row, strict))
        if not remaining:
            continue
        if nodes >= maximum_nodes or depth >= maximum_depth:
            return CurvatureCertificate(
                "unresolved", nodes, (float(low), float(high)), remaining[0][0]
            )
        left, right = [], []
        for name, row, strict in remaining:
            a, b = _split(row)
            left.append((name, a, strict))
            right.append((name, b, strict))
        middle = (low + high) / 2
        pending.append((tuple(right), depth + 1, middle, high))
        pending.append((tuple(left), depth + 1, low, middle))
    return CurvatureCertificate("certified", nodes, None, None)
