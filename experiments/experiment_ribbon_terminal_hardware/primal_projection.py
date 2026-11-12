"""
Retain checked feasible linear incumbents while optimizing within sixteen primal working-set updates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from .projection_system import CoordinateBounds, ProjectionSystem, dot, prepare


class Stop(Enum):
    """
    Separate numerical stationarity from incomplete optimization and absent feasible input.
    """

    STATIONARY = "stationary"
    UPDATE_LIMIT = "update_limit"
    DEPENDENT_ACTIVE = "dependent_active"
    FEASIBILITY_DECLINE = "feasibility_decline"
    INVALID_ANCHOR = "invalid_anchor"
    INCONSISTENT_SYSTEM = "inconsistent_system"


@dataclass(frozen=True)
class Result:
    """
    Offer at most one checked linear incumbent; no result certifies nonlinear material geometry.

    A nonstationary result is incomplete optimization, even when its step is
    feasible. Only stationarity may identify active coordinate faces. Caller
    cancellation and resource exceptions propagate instead of returning a prefix.
    """

    step: tuple[float, ...] | None
    stop: Stop
    updates: int = 0
    lower: frozenset[int] = frozenset()
    upper: frozenset[int] = frozenset()


@dataclass(frozen=True)
class _Tangent:
    """
    Keep a two-pass active-row basis and triangular factors without squaring its conditioning.
    """

    units: list[list[float]]
    factors: list[list[float]]

    def direction(self, motion: list[float]) -> tuple[list[float], list[float]]:
        """
        Project toward minimum norm in the active tangent and recover signed row multipliers.
        """
        right = [-dot(unit, motion) for unit in self.units]
        multipliers = [0.0] * len(self.units)
        for j in reversed(range(len(self.units))):
            multipliers[j] = (
                right[j]
                - math.fsum(
                    self.factors[k][j] * multipliers[k] for k in range(j + 1, len(self.units))
                )
            ) / self.factors[j][j]
        direction = [
            -motion[i] - math.fsum(v * unit[i] for v, unit in zip(right, self.units))
            for i in range(len(motion))
        ]
        return direction, multipliers


def _remainder(row: Sequence[float], units: list[list[float]]) -> tuple[list[float], list[float]]:
    """
    Remove known row directions twice, preserving deterministic accumulated coefficients.
    """
    remainder = list(row)
    factors = [0.0] * len(units)
    for _ in range(2):
        for j, unit in enumerate(units):
            amount = dot(remainder, unit)
            factors[j] += amount
            remainder = [a - amount * b for a, b in zip(remainder, unit)]
    return remainder, factors


def _tangent(
    system: ProjectionSystem, active: list[int], checkpoint: Callable[[], None]
) -> _Tangent | None:
    """
    Decline dependent active rows under the existing1e-10rank criterion.
    """
    units: list[list[float]] = []
    triangular: list[list[float]] = []
    for index in active:
        checkpoint()
        row, factors = _remainder(system.constraints[index][0], units)
        norm = math.hypot(*row)
        if not math.isfinite(norm) or norm <= 1e-10:
            return None
        triangular.append(factors + [norm])
        units.append([x / norm for x in row])
    return _Tangent(units, triangular)


def _checked(
    system: ProjectionSystem,
    motion: list[float],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
) -> tuple[float, ...] | None:
    """
    Check every normalized inequality, raw physical row and original cap equation before retention.

    Use the original normalized/raw inequality gates and cap consistency gate.
    Coordinate faces are included in the normalized system. The caller must
    still enforce its original geometry bounds and predicted/nonlinear descent.
    """
    point = tuple(a + b for a, b in zip(system.base, motion))
    if any(not math.isfinite(x) for x in point):
        return None
    if any(dot(row, motion) - right > tolerance for row, right, tolerance in system.constraints):
        return None
    if any(abs(r + dot(row, point)) > 1e-8 for row, r in zip(jacobian[:6], residual[:6])):
        return None
    if any(r + dot(row, point) > 1e-14 for row, r in zip(jacobian[6:], residual[6:])):
        return None
    return point


def _advance(
    system: ProjectionSystem,
    motion: list[float],
    direction: list[float],
    active: list[int],
    tangent: _Tangent,
    checkpoint: Callable[[], None],
) -> tuple[list[float], int | None]:
    """
    Stop the one tangent ray at its first independent blocking face; keep all rows in later checks.

    A finite slope no larger than the original1e-14gate cannot block this
    ray. A positive slope whose candidate fraction cannot improve the current
    first blocker also needs no two-pass independence calculation. Checkpoints,
    positive-slope arithmetic, row order and final feasibility stay unchanged.
    A speculative dot-product overflow or invalid sum is deferred until after
    the original dependence test: dependent rows previously skipped those products.
    """
    fraction = 1.0
    blocker = None
    for index, (row, right, _) in enumerate(system.constraints):
        checkpoint()
        if index in active:
            continue
        slope_error: OverflowError | ValueError | None = None
        try:
            slope = dot(row, direction)
        except (OverflowError, ValueError) as error:
            slope, slope_error = math.nan, error
        if math.isfinite(slope) and slope <= 1e-14:
            continue
        step_error: OverflowError | ValueError | None = None
        step = 0.0
        if slope_error is None and slope > 1e-14:
            try:
                step = max(0.0, (right - dot(row, motion)) / slope)
            except (OverflowError, ValueError) as error:
                step_error = error
            if step_error is None and step >= fraction:
                continue
        independent, _ = _remainder(row, tangent.units)
        if math.hypot(*independent) <= 1e-10:
            continue
        if slope_error is not None:
            raise slope_error
        if slope > 1e-14:
            if step_error is not None:
                raise step_error
            if step < fraction:
                fraction, blocker = step, index
    return [v + fraction * d for v, d in zip(motion, direction)], blocker


def project(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    anchor: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> Result:
    """
    Optimize from a supplied feasible anchor, retaining the last checked incumbent within16updates.

    Validate the anchor against the complete shared system, never inferring
    feasibility from a caller label. A failed new iterate cannot displace its
    checked predecessor. Incomplete optimization may offer that predecessor to
    stricter caller gates, but supplies no active-face identity or optimality.
    Singular/inconsistent input and an invalid anchor never invent a step.
    Every preparation, update and constraint traversal propagates checkpoints;
    exceptions do not return retained geometry or start a second optimization.
    """
    if len(anchor) != len(values) or any(not math.isfinite(x) for x in anchor):
        raise ValueError("Supply a complete finite linear anchor")
    if any(not math.isfinite(x) for x in values + residual) or any(
        not math.isfinite(x) for row in jacobian for x in row
    ):
        raise ValueError("Supply finite linear equations and current coordinates")
    system = prepare(model, values, jacobian, residual, checkpoint)
    if system is None:
        return Result(None, Stop.INCONSISTENT_SYSTEM)
    motion = [a - b for a, b in zip(anchor, system.base)]
    incumbent = _checked(system, motion, jacobian, residual)
    if incumbent is None:
        return Result(None, Stop.INVALID_ANCHOR)
    active: list[int] = []
    for update in range(1, 17):
        checkpoint()
        tangent = _tangent(system, active, checkpoint)
        if tangent is None:
            return Result(incumbent, Stop.DEPENDENT_ACTIVE, update)
        direction, multipliers = tangent.direction(motion)
        if any(not math.isfinite(x) for x in direction + multipliers):
            return Result(incumbent, Stop.FEASIBILITY_DECLINE, update)
        if math.hypot(*direction) <= 1e-12:
            if multipliers and min(multipliers) < -1e-12:
                active.pop(min(range(len(multipliers)), key=lambda i: multipliers[i]))
                continue
            lower: set[int] = set()
            upper: set[int] = set()
            for index in active:
                tag = system.face_tags[index]
                if tag is not None:
                    (lower if tag[1] == "lower" else upper).add(tag[0])
            return Result(incumbent, Stop.STATIONARY, update, frozenset(lower), frozenset(upper))
        proposed, blocker = _advance(system, motion, direction, active, tangent, checkpoint)
        checked = _checked(system, proposed, jacobian, residual)
        if checked is None:
            return Result(incumbent, Stop.FEASIBILITY_DECLINE, update)
        motion, incumbent = proposed, checked
        if blocker is not None:
            active.append(blocker)
    checkpoint()
    return Result(incumbent, Stop.UPDATE_LIMIT, 16)
