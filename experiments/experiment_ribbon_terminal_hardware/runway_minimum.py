"""
Minimize a runway objective on a cap nullspace using bounded primal face pivots.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection


@dataclass(frozen=True)
class LinearMinimum:
    """
    Retain one stationary feasible point and its independent active faces.
    """

    point: tuple[float, ...]
    active: frozenset[int]


def minimize(
    objective: list[float],
    rows: list[list[float]],
    bounds: list[float],
    feasible: list[float],
    checkpoint: Callable[[], None],
) -> LinearMinimum | None:
    """
    Follow at most sixteen improving face pivots from the supplied feasible point.

    Rows describe closed halfspaces in cap-nullspace coordinates. Project the
    negative linear objective onto each active face, advance to its first
    blocking halfspace and retain independent active normals. At stationarity,
    nonpositive normal coefficients certify a minimum; a positive coefficient
    releases that face. Rank loss, an unbounded direction, arithmetic inconsistency
    or the pivot limit declines optimization. There is no feasibility search,
    route evaluation or renewed caller allowance. The caller must recheck the
    original unnormalized rows after reconstructing exact zero runways.
    """
    if len(rows) != len(bounds) or any(len(row) != len(objective) for row in rows):
        raise ValueError("Match each finite nullspace row with its bound and objective size")
    if len(feasible) != len(objective):
        raise ValueError("Match the initial feasible point to the objective size")
    if not all(math.isfinite(x) for row in [objective, feasible, bounds, *rows] for x in row):
        return None
    normalized: list[tuple[list[float], float]] = []
    for row, bound in zip(rows, bounds):
        checkpoint()
        norm = math.sqrt(math.fsum(x * x for x in row))
        normalized.append(([x / norm for x in row], bound / norm) if norm > 1e-10 else (row, bound))
    point = list(feasible)
    if any(
        bound - math.fsum(a * b for a, b in zip(row, point)) < -1e-10 for row, bound in normalized
    ):
        return None
    active: list[int] = []
    tolerance = 1e-12 * max(1.0, math.sqrt(math.fsum(x * x for x in objective)))
    for _ in range(16):
        checkpoint()
        normals = [normalized[i][0] for i in active]
        direction = affine_projection(normals, [0.0] * len(active), [-x for x in objective])
        if direction is None:
            return None
        if math.sqrt(math.fsum(x * x for x in direction)) <= tolerance:
            coefficients = affine_projection(
                [list(column) for column in zip(*normals)] if normals else [[] for _ in objective],
                objective,
                [0.0] * len(active),
            )
            if coefficients is None:
                return None
            leaving = max(enumerate(coefficients), key=lambda item: item[1], default=None)
            if leaving is None or leaving[1] <= tolerance:
                return LinearMinimum(tuple(point), frozenset(active))
            active.pop(leaving[0])
            continue
        blockers: list[tuple[float, int]] = []
        for i, (row, bound) in enumerate(normalized):
            checkpoint()
            if i in active:
                continue
            slope = math.fsum(a * b for a, b in zip(row, direction))
            slack = bound - math.fsum(a * b for a, b in zip(row, point))
            if slack < -1e-10:
                return None
            if slope > tolerance:
                blockers.append((max(0.0, slack) / slope, i))
        if not blockers:
            return None
        fraction, entering = min(blockers)
        if not math.isfinite(fraction):
            return None
        point = [a + fraction * b for a, b in zip(point, direction)]
        active.append(entering)
    return None
