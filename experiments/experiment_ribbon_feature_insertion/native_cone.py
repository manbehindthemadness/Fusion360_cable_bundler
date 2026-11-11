"""
Project one original three-ray support onto native-sized positive straight coordinates.
"""

from __future__ import annotations

import math
from typing import Callable

from .linear_fit import least_squares


def project(
    rows: list[list[float]],
    right: list[float],
    size: int,
    minimum: float,
    maximum_sum: float | None,
    checkpoint: Callable[[], None],
) -> list[float] | None:
    """
    Minimize endpoint error over one support, including its original straight-budget face.

    Enumerate at most eight lower faces, each with at most one active sum face.
    These are algebraic coordinates of the same support, not new fold/angle or
    physical candidates. Pin selected coordinates exactly; free coordinates must
    meet the same lower floor. Zero support is owned by the caller. An ordinary
    unconstrained optimum already inside this domain returns without extra faces.
    """
    if not 0 <= size <= 3 or not math.isfinite(minimum) or minimum <= 0:
        raise ValueError("Use at most three native-sized straight coordinates")
    if maximum_sum is not None and (not math.isfinite(maximum_sum) or maximum_sum < 0):
        raise ValueError("Use a finite nonnegative straight-coordinate budget")
    if maximum_sum is not None and size * minimum > maximum_sum:
        return None
    best: list[float] | None = None
    score: tuple[float, float] | None = None
    for mask in range(1 << size):
        checkpoint()
        pinned = [i for i in range(size) if mask & (1 << i)]
        candidate = least_squares(
            [[float(i == j) for j in range(size)] for i in pinned],
            [minimum] * len(pinned),
            rows,
            right,
            size,
            maximum_sum=maximum_sum,
        )
        if candidate is None:
            continue
        for i in pinned:
            candidate[i] = minimum
        if min(candidate, default=minimum) < minimum or (
            maximum_sum is not None and math.fsum(candidate) > maximum_sum + 1e-8
        ):
            continue
        current = (
            math.fsum(
                (math.fsum(a * b for a, b in zip(row, candidate)) - target) ** 2
                for row, target in zip(rows, right)
            ),
            math.fsum(candidate),
        )
        if score is None or current < score:
            best, score = candidate, current
        if mask == 0:
            return candidate
    return best
