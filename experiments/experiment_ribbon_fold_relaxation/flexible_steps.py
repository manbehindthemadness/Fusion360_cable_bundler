"""
Share bounded flexible-material steps and exact ordered-cap retraction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .closure_policy import ClosurePolicy, ordered_caps_closed
from .flexible import FlexibleModel as Model
from .steps import advance, projected


@dataclass(frozen=True)
class StepLimits:
    """
    Distinguish routing trust steps from the established small aesthetic steps.
    """

    linear_fraction: float = 0.05
    angle_radians: float = 0.2


DEFAULT_STEPS = StepLimits()


def step_limit(
    model: Model,
    values: tuple[float, ...],
    delta: tuple[float, ...],
    maximum: float = math.inf,
    *,
    limits: StepLimits = DEFAULT_STEPS,
) -> float:
    """
    Bound coordinate changes with explicit layout-relative linear and angular trust limits.
    """
    step = maximum
    for i, (value, change) in enumerate(zip(values, delta)):
        low, high = model.bounds(i)
        if change > 1e-12:
            step = min(step, (high - value) / change)
        elif change < -1e-12:
            step = min(step, (low - value) / change)
        if abs(change) > 1e-12:
            step = min(
                step,
                (limits.linear_fraction if i % 4 in (0, 3) else limits.angle_radians) / abs(change),
            )
    return max(0.0, step)


def retract(
    model: Model,
    initial: tuple[float, ...],
    maximum_length: float,
    checkpoint: Callable[[], None],
    *,
    closure_policy: ClosurePolicy = ClosurePolicy.NORMALIZED,
) -> tuple[float, ...] | None:
    """
    Restore ordered caps and any exceeded length budget before candidate acceptance.

    Six Newton corrections with four correction halvings, using the same bounded
    coordinates. Targets never move. Complete cap vectors remain an independent
    acceptance gate because the local rotation residual also vanishes at a half-turn.
    Predicted zero runway slots stay exactly on their active bound during Newton
    correction; the correction cannot create new microscopic straight features.
    Certified smoothing requests the same actual ordered1e-10cap criterion used
    by mating proofs, rather than accepting length-normalized error alone. The
    exploratory default and six-correction/four-halving allowance stay unchanged.
    """
    if not isinstance(closure_policy, ClosurePolicy):
        raise ValueError("Supply an explicit flexible closure policy")
    fixed_runway = tuple(i for i in model.straight_indices if initial[i] <= 1e-12)
    values = tuple(0.0 if i in fixed_runway else v for i, v in enumerate(initial))
    for _ in range(6):
        checkpoint()
        residual = model.residual(values)
        excess = max(0.0, model.length(values) - maximum_length)
        error = max(excess, *(abs(v) for v in residual))
        if error < 1e-10 and (
            closure_policy is ClosurePolicy.NORMALIZED or ordered_caps_closed(model, values)
        ):
            return values
        rows = model.jacobian(values)
        right = [-v for v in residual]
        if excess:
            rows.append(model.length_gradient(values))
            right.append(-excess)
        for index in fixed_runway:
            row = [0.0] * len(values)
            row[index] = 1.0
            rows.append(row)
            right.append(0.0)
        delta = projected(model, values, rows, right, [0.0] * len(values))
        if delta is None:
            return None
        step = step_limit(model, values, delta, 1.0)
        for _ in range(4):
            trial = advance(model, values, delta, step)
            trial = tuple(0.0 if i in fixed_runway else v for i, v in enumerate(trial))
            trial_error = max(
                max(0.0, model.length(trial) - maximum_length),
                *(abs(v) for v in model.residual(trial)),
            )
            if trial_error < error:
                values = trial
                break
            step /= 2
        else:
            return None
    return (
        values
        if max(
            max(0.0, model.length(values) - maximum_length),
            *(abs(v) for v in model.residual(values)),
        )
        < 1e-10
        and (closure_policy is ClosurePolicy.NORMALIZED or ordered_caps_closed(model, values))
        else None
    )
