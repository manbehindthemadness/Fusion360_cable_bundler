"""
Compute bounded closure-preserving descent and nonlinear endpoint retraction.
"""

from __future__ import annotations

import math
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import AffineWorkspace, affine_projection

from .model import Model

MAXIMUM_ANGULAR_STEP_RADIANS = 0.2


def projected(
    model: Model,
    values: tuple[float, ...],
    rows: list[list[float]],
    right: list[float],
    reference: list[float],
    *,
    workspace: AffineWorkspace | None = None,
) -> tuple[float, ...] | None:
    """
    Project onto linear closure while freezing outward motion at active bounds.

    An explicit action-owned workspace reuses identical ordered row-prefix bases;
    free-column selection, correction arithmetic and coordinate-bound checks stay unchanged.
    """
    free = list(range(len(values)))
    project_affine = affine_projection if workspace is None else workspace.project
    for _ in range(len(values) + 1):
        delta = project_affine(
            [[row[i] for i in free] for row in rows], right, [reference[i] for i in free]
        )
        if delta is None:
            return None
        blocked = []
        for i, change in zip(free, delta):
            low, high = model.bounds(i)
            if (values[i] <= low + 1e-10 and change < -1e-10) or (
                values[i] >= high - 1e-10 and change > 1e-10
            ):
                blocked.append(i)
        if not blocked:
            output = [0.0] * len(values)
            for i, change in zip(free, delta):
                output[i] = change
            return tuple(output)
        free = [i for i in free if i not in blocked]
    return None


def step_limit(
    model: Model, values: tuple[float, ...], delta: tuple[float, ...], maximum: float = math.inf
) -> float:
    """
    Stop at coordinate bounds or a0.2radian maximum fold-angle change.
    """
    step = maximum
    straights = set(model.straight_indices)
    for i, (value, change) in enumerate(zip(values, delta)):
        low, high = model.bounds(i)
        if change > 1e-12:
            step = min(step, (high - value) / change)
        elif change < -1e-12:
            step = min(step, (low - value) / change)
        if i not in straights and abs(change) > 1e-12:
            step = min(step, MAXIMUM_ANGULAR_STEP_RADIANS / abs(change))
    return max(0.0, step)


def advance(
    model: Model, values: tuple[float, ...], delta: tuple[float, ...], step: float
) -> tuple[float, ...]:
    """
    Apply a bounded parameter step, clipping only floating roundoff at its limits.
    """
    return tuple(
        min(model.bounds(i)[1], max(model.bounds(i)[0], value + step * change))
        for i, (value, change) in enumerate(zip(values, delta))
    )


def retract(
    model: Model, initial: tuple[float, ...], checkpoint: Callable[[], None] | None = None
) -> tuple[float, ...] | None:
    """
    Restore nonlinear cap closure with at most six Newton/four halving steps.

    This corrects the trial plan before acceptance, never the built geometry.
    Failure retains the preceding accepted route; no target movement is allowed.
    """
    values = initial
    for _ in range(6):
        if checkpoint is not None:
            checkpoint()
        residual = model.residual(values)
        error = max(abs(value) for value in residual)
        if error < 1e-10:
            return values
        delta = projected(
            model, values, model.jacobian(values), [-v for v in residual], [0.0] * len(values)
        )
        if delta is None:
            return None
        step = step_limit(model, values, delta, 1.0)
        for _ in range(4):
            trial = advance(model, values, delta, step)
            if max(abs(value) for value in model.residual(trial)) < error:
                values = trial
                break
            step /= 2
        else:
            return None
    return values if max(abs(value) for value in model.residual(values)) < 1e-10 else None
