"""
Invert fixed exact material frames without orthogonality or floating-rounding assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

Point = tuple[Fraction, ...]


@dataclass(frozen=True)
class FrameInverse:
    """
    Retain exact inverse rows, determinant and infinity-norm bounds for one fixed frame.
    """

    columns: tuple[Point, ...]
    determinant: Fraction
    rows: tuple[Point, ...] | None
    norm: Fraction
    inverse_norm: Fraction | None


def invert(columns: tuple[Point, ...]) -> FrameInverse:
    """
    Validate and invert a three-dimensional rational frame, retaining singularity explicitly.
    """
    if len(columns) != 3 or any(
        len(p) != 3 or any(type(x) is not Fraction for x in p) for p in columns
    ):
        raise ValueError("Three complete exact material-frame columns required")

    def cross(a: Point, b: Point) -> Point:
        """
        Form one exact cofactor row without magnitude cancellation losses.
        """
        return tuple(
            a[(k + 1) % 3] * b[(k + 2) % 3] - a[(k + 2) % 3] * b[(k + 1) % 3] for k in range(3)
        )

    first, second, third = columns
    cofactors = (cross(second, third), cross(third, first), cross(first, second))
    determinant = sum((a * b for a, b in zip(first, cofactors[0])), Fraction(0))
    norm = max(sum((abs(column[k]) for column in columns), Fraction(0)) for k in range(3))
    if determinant == Fraction(0):
        return FrameInverse(columns, determinant, None, norm, None)
    rows = tuple(tuple(x / determinant for x in row) for row in cofactors)
    inverse_norm = max(sum(map(abs, row), Fraction(0)) for row in rows)
    return FrameInverse(columns, determinant, rows, norm, inverse_norm)
