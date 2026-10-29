"""
Solve small feasible linearized shooting steps without extra transport probes.

This bounded active-set quadratic subproblem is not a nonlinear feasibility or
global routing certificate. The caller must check actual candidate geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# noinspection PyProtectedMember
from .target_shooting import _solve


@dataclass(frozen=True)
class StepResult:
    """
    Retain a feasible subproblem prefix and explicit bounded termination status.
    """

    values: tuple[float, ...]
    iterations: int
    active: tuple[int, ...]
    status: str


def _independent(row: tuple[float, ...], active: list[tuple[float, ...]]) -> bool:
    """
    Reject dependent working-set rows before forming a singular KKT system.
    """
    basis: list[list[float]] = []
    for source in (*active, row):
        residual = list(source)
        for direction in basis:
            projection = sum(a * b for a, b in zip(residual, direction))
            residual = [a - projection * b for a, b in zip(residual, direction)]
        length = math.sqrt(sum(v * v for v in residual))
        if length <= 1e-8:
            return False
        basis.append([v / length for v in residual])
    return True


def constrained_step(
    columns: list[tuple[float, ...]],
    errors: tuple[float, ...],
    damping: float,
    slack_columns: list[tuple[float, ...]],
    slacks: tuple[float, ...],
    coordinates: tuple[float, ...],
    lower: tuple[float, ...],
    upper: tuple[float, ...],
) -> StepResult:
    """
    Minimize a damped residual quadratic with linearized nonnegative slacks.

    Start from zero displacement and perform at most32active-set iterations in
    at most12coordinates/1024input inequalities. Bounds enter as inequalities.
    Numerical/dependent-set termination returns the last feasible prefix with
    explicit status;it never drops a constraint or claims nonlinear feasibility.
    Invalid/nonfinite/infeasible input raises ValueError. No inputs are mutated.
    """
    n = len(columns)
    if (
        not 1 <= n <= 12
        or len(slacks) > 1024
        or len(slack_columns) != n
        or any(len(c) != len(errors) for c in columns)
        or any(len(c) != len(slacks) for c in slack_columns)
        or any(len(row) != n for row in (coordinates, lower, upper))
        or not math.isfinite(damping)
        or damping <= 0
    ):
        raise ValueError("Malformed bounded quadratic subproblem.")
    values = (*errors, *slacks, *coordinates, *lower, *upper)
    if not all(math.isfinite(v) for v in values) or any(c < 0 for c in slacks):
        raise ValueError("Quadratic subproblem requires a finite feasible origin.")
    if any(not a <= x <= b for x, a, b in zip(coordinates, lower, upper)):
        raise ValueError("Quadratic subproblem origin violates coordinate bounds.")
    if not all(math.isfinite(v) for column in (*columns, *slack_columns) for v in column):
        raise ValueError("Quadratic subproblem derivatives must be finite.")
    hessian = [
        [
            sum(a * b for a, b in zip(c, d)) + (damping if i == j else 0)
            for j, d in enumerate(columns)
        ]
        for i, c in enumerate(columns)
    ]
    gradient = [sum(a * b for a, b in zip(c, errors)) for c in columns]
    rows = [tuple(c[j] for c in slack_columns) for j in range(len(slacks))]
    margins = list(slacks)
    for i, (x, lo, hi) in enumerate(zip(coordinates, lower, upper)):
        direction = tuple(float(i == j) for j in range(n))
        rows.extend((direction, tuple(-v for v in direction)))
        margins.extend((x - lo, hi - x))
    for i, row in enumerate(rows):
        scale = math.sqrt(sum(v * v for v in row))
        if scale > 1e-14:
            rows[i] = tuple(v / scale for v in row)
            margins[i] /= scale
    delta = [0.0] * n
    active: list[int] = []
    status = "iteration limit"
    iterations = 0
    for _ in range(32):
        iterations += 1
        working = [rows[i] for i in active]
        matrix = [row + [-a[i] for a in working] for i, row in enumerate(hessian)]
        matrix.extend([list(a) + [0.0] * len(active) for a in working])
        right = [
            -g - sum(a * b for a, b in zip(row, delta)) for g, row in zip(gradient, hessian)
        ] + [0.0] * len(active)
        try:
            solution = _solve(matrix, right)
        except ValueError:
            # Fail soft only to a retained feasible prefix;caller records this status.
            status = "numerical KKT stop"
            break
        direction, multipliers = solution[:n], solution[n:]
        if max(abs(v) for v in direction) <= 1e-9:
            if not multipliers or min(multipliers) >= -1e-9:
                status = "stationary linearized subproblem"
                break
            active.pop(min(range(len(active)), key=lambda j: multipliers[j]))
            continue
        fraction, blocker = 1.0, None
        for i, (row, margin) in enumerate(zip(rows, margins)):
            slope = sum(a * b for a, b in zip(row, direction))
            if i not in active and slope < -1e-12:
                available = margin + sum(a * b for a, b in zip(row, delta))
                allowed = max(0.0, available) / -slope
                if allowed < fraction:
                    fraction, blocker = allowed, i
        proposed = [a + fraction * b for a, b in zip(delta, direction)]
        if any(
            c + sum(a * b for a, b in zip(row, proposed)) < -1e-8 for row, c in zip(rows, margins)
        ):
            status = "linearized feasibility loss"
            break
        delta = proposed
        if blocker is not None:
            if not _independent(rows[blocker], working):
                status = "dependent working-set stop"
                break
            active.append(blocker)
    return StepResult(tuple(delta), iterations, tuple(active), status)
