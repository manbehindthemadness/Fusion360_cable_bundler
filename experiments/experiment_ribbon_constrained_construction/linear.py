"""
Minimize straight material length over a small supplied closure-and-clearance polyhedron.

This is a numerical construction kernel, not a collision detector or full routing
solver. Halfspaces must describe an explicitly supplied separation arrangement.
All coordinates are nonnegative normalized lengths and all cost coefficients are
positive. A completed enumeration minimizes over checked vertices of that linear
problem only; numerical rank/residual gates do not certify global ribbon feasibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

# These dimensionless arithmetic gates resolve basis rank and residuals; they are
# not substitutes for the physical 0.01 mm acceptance policy.
RANK_EPSILON = 1e-10
RESIDUAL_EPSILON = 1e-8


@dataclass(frozen=True)
class Row:
    """
    Store one finite normalized affine row with an evidence-oriented name.

    Equality rows mean coefficients*x=right; clearance rows mean >=right.
    """

    name: str
    coefficients: tuple[float, ...]
    right: float

    def __post_init__(self) -> None:
        """
        Reject malformed row identity and numbers before numerical work.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Rows require a nonempty name")
        if not self.coefficients or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in (*self.coefficients, self.right)
        ):
            raise ValueError("Rows require finite numeric coefficients and right side")


@dataclass(frozen=True)
class Problem:
    """
    Combine hard closure and clearance before selecting any length allocation.

    Positive cost and nonnegative coordinates give bounded cost sublevel sets.
    Fold material is constant for fixed angles/radii and need not enter the cost.
    """

    cost: tuple[float, ...]
    equalities: tuple[Row, ...]
    clearance: tuple[Row, ...]

    def __post_init__(self) -> None:
        """
        Enforce the supported dimension and reject incompatible constraint data.
        """
        if not 1 <= len(self.cost) <= 7 or any(
            type(c) not in (int, float) or not math.isfinite(c) or c <= 0 for c in self.cost
        ):
            raise ValueError("Use one to seven finite positive length costs")
        if any(
            len(row.coefficients) != len(self.cost) for row in (*self.equalities, *self.clearance)
        ):
            raise ValueError("All rows must match the coordinate dimension")


@dataclass(frozen=True)
class Result:
    """
    Keep completion, the best checked allocation and finite work accounting separate.

    A work-limited best point may satisfy supplied rows but has no completed
    minimization claim. No checked vertex is not a proof of physical infeasibility.
    """

    status: str
    values: tuple[float, ...] | None
    cost: float | None
    vertices_checked: int
    total_active_sets: int


def _basis(rows: tuple[Row, ...]) -> tuple[Row, ...]:
    """
    Select independent equality normals with two-pass orthogonalization.

    The original full equality set is checked on every returned point, including
    dependent rows. Ambiguous small directions stay subject to that residual gate.
    """
    selected = []
    normals: list[list[float]] = []
    for row in rows:
        vector = list(row.coefficients)
        for _ in range(2):
            for prior in normals:
                factor = math.fsum(a * b for a, b in zip(vector, prior))
                vector = [a - factor * b for a, b in zip(vector, prior)]
        norm = math.sqrt(math.fsum(v * v for v in vector))
        if norm > RANK_EPSILON:
            normals.append([v / norm for v in vector])
            selected.append(row)
    return tuple(selected)


def minimize(
    problem: Problem, checkpoint: Callable[[], None], *, maximum_vertices: int = 4096
) -> Result:
    """
    Enumerate algebraic active intersections without guessing route coordinates.

    Clearance boundaries participate in the vertex system, unlike filtering only
    vertices of the closure/nonnegativity polyhedron. Work exhaustion retains the
    best checked point with an explicit incomplete status. Caller cancellation,
    wall, memory and source failures propagate; CPU targets belong to the caller.
    """
    if type(maximum_vertices) is not int or maximum_vertices <= 0:
        raise ValueError("Use a positive finite active-set allowance")
    size = len(problem.cost)
    equalities = _basis(problem.equalities)
    boundaries = problem.clearance + tuple(
        Row(f"nonnegative {i}", tuple(float(i == j) for j in range(size)), 0.0) for i in range(size)
    )
    needed = size - len(equalities)
    total = math.comb(len(boundaries), needed) if needed <= len(boundaries) else 0
    best = None
    best_cost = None
    checked = 0
    for active in combinations(boundaries, needed):
        checkpoint()
        if checked == maximum_vertices:
            return Result("work_limit", best, best_cost, checked, total)
        checked += 1
        rows = equalities + active
        if len(_basis(rows)) != size:
            continue
        point = affine_projection(
            [list(r.coefficients) for r in rows], [r.right for r in rows], [0.0] * size
        )
        if point is None or min(point) < -RESIDUAL_EPSILON:
            continue
        values = tuple(max(0.0, value) for value in point)

        def residual(row: Row, coordinates: tuple[float, ...] = values) -> float:
            """
            Measure each original equation and inequality after nonnegative roundoff removal.
            """
            return math.fsum(a * b for a, b in zip(row.coefficients, coordinates)) - row.right

        if any(abs(residual(row)) > RESIDUAL_EPSILON for row in problem.equalities) or any(
            residual(row) < -RESIDUAL_EPSILON for row in problem.clearance
        ):
            continue
        cost = math.fsum(a * b for a, b in zip(problem.cost, values))
        if best_cost is None or cost < best_cost:
            best, best_cost = values, cost
    return Result(
        "complete" if best is not None else "no_checked_vertex", best, best_cost, checked, total
    )
