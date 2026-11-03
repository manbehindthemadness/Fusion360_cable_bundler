"""
Expose movable existing bends and straight slots while keeping original radii fixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Callable

from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece


@dataclass(frozen=True)
class MovableBends(FlexibleModel):
    """
    Remove radius coordinates from the shared material model without fixing internal frames.
    """

    @cached_property
    def full(self) -> FlexibleModel:
        """
        Reuse the established bank-dependent flat leads and complete material map.
        """
        return FlexibleModel(self.original)

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Retain straights, signed angles and banks, excluding radius growth.
        """
        return tuple(i for i in range(len(self.full.initial)) if i % 4 != 3)

    @cached_property
    def initial(self) -> tuple[float, ...]:
        """
        Start at the original accepted route without perturbation or guessed bends.
        """
        return tuple(self.full.initial[i] for i in self.indices)

    @cached_property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Include absent zero-length slots so material can redistribute between bends.
        """
        return tuple(i for i, full_index in enumerate(self.indices) if full_index % 4 == 0)

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep existing angle/bank regularity and nonnegative straight bounds.
        """
        return self.full.bounds(self.indices[index])

    def expanded(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reinsert the immutable initial radius coordinates for the shared model.
        """
        result = list(self.full.initial)
        for index, value in zip(self.indices, values):
            result[index] = value
        return tuple(result)

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Place the original ordered folds using their current angles, banks and runways.
        """
        return self.full.pieces(self.expanded(values))

    def length_gradient(self, values: tuple[float, ...]) -> list[float]:
        """
        Differentiate full material length, including curved paths and required flat leads.
        """
        gradient = self.full.length_gradient(self.expanded(values))
        return [gradient[i] for i in self.indices]


def retract_active(
    model: MovableBends, initial: tuple[float, ...], checkpoint: Callable[[], None]
) -> tuple[float, ...] | None:
    """
    Restore external caps with six Newton steps and four scalar halvings per step.

    Preserve the descent step's exact zero-runway active set. The local rotation
    residual is not a final frame certificate; acceptance checks actual cap poses.
    """
    fixed = tuple(i for i in model.straight_indices if initial[i] == 0.0)
    values = initial
    for _ in range(6):
        checkpoint()
        residual = model.residual(values)
        error = max(abs(v) for v in residual)
        if error < 1e-10:
            return values
        rows = model.jacobian(values)
        right = [-v for v in residual]
        for index in fixed:
            rows.append([float(i == index) for i in range(len(values))])
            right.append(0.0)
        delta = projected(model, values, rows, right, [0.0] * len(values))
        if delta is None:
            return None
        step = step_limit(model, values, delta, 1.0)
        for _ in range(4):
            trial = advance(model, values, delta, step)
            trial = tuple(0.0 if i in fixed else v for i, v in enumerate(trial))
            if max(abs(v) for v in model.residual(trial)) < error:
                values = trial
                break
            step /= 2
        else:
            return None
    return values if max(abs(v) for v in model.residual(values)) < 1e-10 else None
