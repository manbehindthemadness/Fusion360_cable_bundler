"""
Check fixed-motion travel bounds with at most 63 algebraic bases in three dimensions.

This is a small linear allocation problem, not a geometric candidate search.
No shape is constructed during basis checks. Floating-point exhaustion remains
unresolved unless a separating chord projection establishes a restricted-family
incompatibility with an explicit numerical margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .coupled_motion import ZERO


class AllocationStatus(Enum):
    """
    Distinguish an allocation, a numerical separating witness and unresolved exhaustion.
    """

    FEASIBLE = "feasible"
    SEPARATED = "separated by chord projection"
    UNRESOLVED = "no feasible algebraic basis found"


@dataclass(frozen=True)
class TravelAllocation:
    """
    Retain the sole allocation outcome and its bounded-work or separating evidence.
    """

    status: AllocationStatus
    lengths: tuple[float, ...] | None
    checked_bases: int
    separation_margin_mm: float | None = None
    minimum_column_projection: float | None = None


def _coefficients(columns: tuple[Vector3, ...], target: Vector3) -> tuple[float, ...] | None:
    """
    Solve one independent support of size at most three, rejecting deficient rank.
    """
    if len(columns) == 1:
        squared = dot(columns[0], columns[0])
        return (dot(columns[0], target) / squared,) if squared > 1e-24 else None
    if len(columns) == 2:
        a, b = columns
        aa, ab, bb = dot(a, a), dot(a, b), dot(b, b)
        determinant = aa * bb - ab * ab
        if determinant <= 1e-12 * aa * bb:
            return None
        return (
            (dot(a, target) * bb - dot(b, target) * ab) / determinant,
            (dot(b, target) * aa - dot(a, target) * ab) / determinant,
        )
    a, b, c = columns
    determinant = dot(a, cross(b, c))
    if abs(determinant) <= 1e-12 * magnitude(a) * magnitude(b) * magnitude(c):
        return None
    return (
        dot(target, cross(b, c)) / determinant,
        dot(a, cross(target, c)) / determinant,
        dot(a, cross(b, target)) / determinant,
    )


def allocate(
    columns: tuple[Vector3, ...], lower_bounds: tuple[float, ...], chord: Vector3
) -> TravelAllocation:
    """
    Find minimum total travel satisfying fixed position and nonnegative extra travel.

    Subtract required travel, then inspect supports of sizes 1..3 in fixed order.
    A feasible three-dimensional nonnegative combination has such a support;
    finite-precision rank skips are why exhaustion alone is not an infeasibility
    certificate. No negative coefficient is clipped and no bounds are relaxed.
    Position closure uses the established absolute 1e-8 mm numerical threshold.
    """
    if not 1 <= len(columns) <= 7 or len(columns) != len(lower_bounds):
        raise ValueError("Allocation requires one to seven paired columns and lower bounds.")
    if any(not math.isfinite(v) for p in (*columns, chord) for v in (p.x, p.y, p.z)):
        raise ValueError("Allocation vectors must be finite.")
    if any(not math.isfinite(value) or value < 0 for value in lower_bounds):
        raise ValueError("Travel lower bounds must be finite and nonnegative.")
    if magnitude(chord) <= 1e-8:
        raise ValueError("Allocation requires nonzero endpoint displacement.")
    residual = chord
    for column, lower in zip(columns, lower_bounds):
        residual = residual.translated(column, -lower)
    if magnitude(residual) <= 1e-8:
        return TravelAllocation(AllocationStatus.FEASIBLE, lower_bounds, 0)
    direction = unit(chord)
    minimum_projection = min(dot(column, direction) for column in columns)
    margin = -dot(residual, direction)
    if minimum_projection >= 0 and margin > 1e-8:
        return TravelAllocation(AllocationStatus.SEPARATED, None, 0, margin, minimum_projection)
    best, best_length, checked = None, math.inf, 0
    for size in range(1, min(3, len(columns)) + 1):
        for indices in combinations(range(len(columns)), size):
            checked += 1
            support = tuple(columns[index] for index in indices)
            values = _coefficients(support, residual)
            if values is None or min(values) < 0:
                continue
            endpoint = ZERO
            for column, value in zip(support, values):
                endpoint = endpoint.translated(column, value)
            if magnitude(difference(endpoint, residual)) > 1e-8:
                continue
            lengths = list(lower_bounds)
            for index, value in zip(indices, values):
                lengths[index] += value
            total = sum(lengths)
            if total < best_length:
                best, best_length = tuple(lengths), total
    return TravelAllocation(
        AllocationStatus.FEASIBLE if best is not None else AllocationStatus.UNRESOLVED,
        best,
        checked,
    )
