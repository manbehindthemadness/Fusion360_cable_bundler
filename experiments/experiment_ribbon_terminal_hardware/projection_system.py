"""
Prepare the unchanged cap nullspace and normalized inequalities for bounded linear projections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from operator import mul
from typing import Callable, Protocol, Sequence


class CoordinateBounds(Protocol):
    """
    Supply exact bounds for each coordinate of a finite linear projection.
    """

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Return the unchanged closed domain for the indexed coordinate.
        """
        ...


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    """
    Accumulate the same ordered rounded products without a Python generator loop.
    """
    return math.fsum(map(mul, a, b))


@dataclass(frozen=True)
class ProjectionSystem:
    """
    Retain one immutable-input preparation; consumers own their moving working sets.
    """

    base: list[float]
    constraints: list[tuple[list[float], float, float]]
    face_tags: list[tuple[int, str] | None]


def prepare(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> ProjectionSystem | None:
    """
    Preserve cap rank gates, two-pass arithmetic, inequality order and raw/normalized tolerances.

    Require six cap rows and one to thirteen physical inequalities. Return no
    preparation for inconsistent cap equations or a violated constant inequality.
    Coordinate inequalities retain their original identity and order. Every
    preparation checkpoint propagates cancellation and caller resource errors.
    """
    if (
        not 7 <= len(residual) <= 19
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Use six caps and at most thirteen retained physical inequalities")
    basis: list[tuple[list[float], float]] = []
    for source, target in zip(jacobian[:6], residual[:6]):
        checkpoint()
        row = list(source)
        right = -target
        for _ in range(2):
            for unit, beta in basis:
                amount = dot(row, unit)
                row = [a - amount * b for a, b in zip(row, unit)]
                right -= amount * beta
        norm = math.sqrt(dot(row, row))
        if norm <= 1e-10:
            if abs(right) > 1e-8:
                return None
        else:
            basis.append(([v / norm for v in row], right / norm))
    base = [math.fsum(beta * unit[i] for unit, beta in basis) for i in range(len(values))]
    inequalities: list[tuple[list[float], float, tuple[int, str] | None]] = [
        (list(row), -r, None) for row, r in zip(jacobian[6:], residual[6:])
    ]
    for i, value in enumerate(values):
        low, high = model.bounds(i)
        if math.isfinite(low):
            inequalities.append(
                ([-float(j == i) for j in range(len(values))], value - low, (i, "lower"))
            )
        if math.isfinite(high):
            inequalities.append(
                ([float(j == i) for j in range(len(values))], high - value, (i, "upper"))
            )
    constraints: list[tuple[list[float], float, float]] = []
    face_tags: list[tuple[int, str] | None] = []
    for row, right, tag in inequalities:
        checkpoint()
        projected = list(row)
        for _ in range(2):
            for unit, _ in basis:
                amount = dot(projected, unit)
                projected = [a - amount * b for a, b in zip(projected, unit)]
        allowance = right - dot(row, base)
        norm = math.sqrt(dot(projected, projected))
        if norm <= 1e-10:
            if allowance < -1e-14:
                return None
        else:
            constraints.append(
                ([v / norm for v in projected], allowance / norm, min(1e-14, 1e-14 / norm))
            )
            face_tags.append(tag)

    return ProjectionSystem(base, constraints, face_tags)
