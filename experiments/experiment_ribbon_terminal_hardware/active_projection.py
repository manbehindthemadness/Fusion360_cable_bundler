"""
Bound a dual active-set least-norm joint projection by sixteen algebraic working-set steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal, Protocol, Sequence


@dataclass
class UnfinishedProjection:
    """
    Retain a declined working-set vector and its reason without granting linear feasibility.
    """

    step: tuple[float, ...] | None = None
    stop_reason: Literal["working_set_limit", "raw_inequality"] | None = None


class CoordinateBounds(Protocol):
    """
    Supply exact bounds for each coordinate of a finite linear projection.
    """

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Return the unchanged closed domain for the indexed coordinate.
        """
        ...


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    """
    Accumulate a deterministic small dense inner product.
    """
    return math.fsum(x * y for x, y in zip(a, b))


def _solve(rows: list[list[float]], right: list[float]) -> list[float] | None:
    """
    Solve one independent working-set Gram system, declining singular arithmetic.
    """
    n = len(right)
    matrix = [list(row) + [value] for row, value in zip(rows, right)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(matrix[i][k]))
        if abs(matrix[pivot][k]) <= 1e-12:
            return None
        matrix[k], matrix[pivot] = matrix[pivot], matrix[k]
        scale = matrix[k][k]
        matrix[k] = [v / scale for v in matrix[k]]
        for i in range(n):
            if i != k:
                factor = matrix[i][k]
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[k])]
    return [row[-1] for row in matrix]


def _checked_step(
    base: list[float],
    motion: list[float],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    *,
    unfinished: UnfinishedProjection | None = None,
) -> tuple[float, ...] | None:
    """
    Apply the original unnormalized inequality gate to an already completed working set.
    """
    result = tuple(a + b for a, b in zip(base, motion))
    if any(r + _dot(row, result) > 1e-14 for row, r in zip(jacobian[6:], residual[6:])):
        if unfinished is not None:
            unfinished.step = result
            unfinished.stop_reason = "raw_inequality"
        return None
    return result


def active_step(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    unfinished: UnfinishedProjection | None = None,
) -> tuple[float, ...] | None:
    """
    Keep six cap equalities and every supplied inequality using at most sixteen dual updates.

    A final feasibility check also examines the completed sixteenth update.
    This grants no seventeenth working-set update or relaxed acceptance gate.
    An optional receipt retains only an already computed vector at exhaustion
    or completed working-set raw-inequality rejection, with distinct reasons.
    It stays empty on early inconsistency, singular arithmetic or cancellation;
    a receipt is never a certified return value and is cleared before each call.
    Normalize each inequality with a stopping tolerance no larger than either
    the original normalized 1e-14 gate or raw 1e-14 gate divided by its projected norm.
    Pending selection and final feasibility use that same per-row tolerance;
    the original raw return gate remains independent and unchanged.
    """
    if unfinished is not None:
        unfinished.step = None
        unfinished.stop_reason = None
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
                amount = _dot(row, unit)
                row = [a - amount * b for a, b in zip(row, unit)]
                right -= amount * beta
        norm = math.sqrt(_dot(row, row))
        if norm <= 1e-10:
            if abs(right) > 1e-8:
                return None
        else:
            basis.append(([v / norm for v in row], right / norm))
    base = [math.fsum(beta * unit[i] for unit, beta in basis) for i in range(len(values))]
    inequalities = [(list(row), -r) for row, r in zip(jacobian[6:], residual[6:])]
    for i, value in enumerate(values):
        low, high = model.bounds(i)
        if math.isfinite(low):
            inequalities.append(([-float(j == i) for j in range(len(values))], value - low))
        if math.isfinite(high):
            inequalities.append(([float(j == i) for j in range(len(values))], high - value))
    constraints: list[tuple[list[float], float, float]] = []
    for row, right in inequalities:
        checkpoint()
        projected = list(row)
        for _ in range(2):
            for unit, _ in basis:
                amount = _dot(projected, unit)
                projected = [a - amount * b for a, b in zip(projected, unit)]
        allowance = right - _dot(row, base)
        norm = math.sqrt(_dot(projected, projected))
        if norm <= 1e-10:
            if allowance < -1e-14:
                return None
        else:
            constraints.append(
                ([v / norm for v in projected], allowance / norm, min(1e-14, 1e-14 / norm))
            )
    motion = [0.0] * len(values)
    active: list[int] = []
    multipliers: list[float] = []
    pending: int | None = None
    pending_multiplier = 0.0
    for _ in range(16):
        checkpoint()
        if pending is None:
            violations = [
                _dot(row, motion) - right - tolerance for row, right, tolerance in constraints
            ]
            pending = (
                max(range(len(violations)), key=lambda i: violations[i]) if violations else None
            )
            if pending is None or violations[pending] <= 0.0:
                return _checked_step(base, motion, jacobian, residual, unfinished=unfinished)
            pending_multiplier = 0.0
        assert pending is not None
        normal, right, _tolerance = constraints[pending]
        normals = [constraints[i][0] for i in active]
        if normals:
            coefficients = _solve(
                [[_dot(a, b) for b in normals] for a in normals], [_dot(a, normal) for a in normals]
            )
            if coefficients is None:
                return None
        else:
            coefficients = []
        direction = [
            normal[i] - math.fsum(c * row[i] for c, row in zip(coefficients, normals))
            for i in range(len(values))
        ]
        norm2 = _dot(direction, direction)
        primal = (_dot(normal, motion) - right) / norm2 if norm2 > 1e-20 else math.inf
        candidates = [
            (lam / c, i) for i, (lam, c) in enumerate(zip(multipliers, coefficients)) if c > 1e-12
        ]
        dual, leaving = min(candidates, default=(math.inf, -1))
        step = min(primal, dual)
        if not math.isfinite(step) or step < -1e-12:
            return None
        step = max(0.0, step)
        motion = [v - step * d for v, d in zip(motion, direction)]
        multipliers = [max(0.0, lam - step * c) for lam, c in zip(multipliers, coefficients)]
        pending_multiplier += step
        if dual < primal:
            active.pop(leaving)
            multipliers.pop(leaving)
        else:
            active.append(pending)
            multipliers.append(pending_multiplier)
            pending = None
    checkpoint()
    if pending is None and all(
        _dot(row, motion) - right <= tolerance for row, right, tolerance in constraints
    ):
        return _checked_step(base, motion, jacobian, residual, unfinished=unfinished)
    if unfinished is not None:
        unfinished.step = tuple(a + b for a, b in zip(base, motion))
        unfinished.stop_reason = "working_set_limit"
    return None
