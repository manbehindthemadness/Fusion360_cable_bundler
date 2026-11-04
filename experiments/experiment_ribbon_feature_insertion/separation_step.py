"""
Plan one bounded contact-separating joint motion without constructing trial geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_relaxation.steps import projected, step_limit

from .separation import Separation, Side


@dataclass(frozen=True)
class SeparationStep:
    """
    Retain the same minimum-norm correction and permitted fraction used by recovery.
    """

    side: Side
    gap: float
    delta: tuple[float, ...]
    fraction: float


def plan_step(
    model: MovableBends,
    values: tuple[float, ...],
    bound: Separation,
    side: Side | None,
    checkpoint: Callable[[], None],
) -> SeparationStep | None:
    """
    Preserve cap closure and compare the original two signed separation directions.

    Choose the original minimum normalized joint motion, with stable side ties.
    Its fraction is bounded by existing coordinates and the0.2radian trust step.
    This linear prediction neither executes a correction nor certifies contact.
    """
    residual, rows = model.residual(values), model.jacobian(values)
    options: list[tuple[float, Side, float, tuple[float, ...]]] = []
    for direction in (s for s in Side if side is None or s is side):
        checkpoint()
        gap = bound.gap(values, direction)
        gradient = bound.gradient(values, direction, checkpoint)
        delta = projected(
            model,
            values,
            rows + [gradient],
            [-v for v in residual] + [1e-8 / model.scale - gap],
            [0.0] * len(values),
        )
        if delta is not None:
            options.append((math.fsum(d * d for d in delta), direction, gap, delta))
    if not options:
        return None
    _, chosen, gap, delta = min(options, key=lambda item: (item[0], item[1].value))
    return SeparationStep(chosen, gap, delta, step_limit(model, values, delta, 1.0))
