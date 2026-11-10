"""
Allow bounded partial restoration of nonlinear reflected caps without relaxing final physical checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .active_projection import CoordinateBounds, active_step


@dataclass(frozen=True)
class _RestorationBounds:
    """
    Add one unit slack coordinate while retaining every original joint bound exactly.
    """

    source: CoordinateBounds
    size: int

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Bound only the added restoration fraction between zero and one.
        """
        return (0.0, 1.0) if index == self.size else self.source.bounds(index)


def restoration_step(
    model: CoordinateBounds,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> tuple[float, ...] | None:
    """
    Compute one partial cap/clearance correction using the original sixteen-step projector.

    A full Newton correction can leave the coordinate domain even when the
    nonlinear problem is feasible. Add one shared slack s in [0,1]: cap rows
    become J*d-r*s=-r. Already satisfied inequalities remain strict; violated
    inequalities may retain only s times their current violation. The same
    least-norm objective penalizes joint motion and slack, selecting partial
    progress without a second projection, extra Jacobian or candidate search.
    The caller still requires actual nonlinear descent and unchanged final
    cap, material, length and complete physical certificates. Zero progress or
    exhausted algebra returns None; caller cancellation is never caught.
    """
    if (
        not 7 <= len(residual) <= 19
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Use six caps and at most thirteen retained physical inequalities")
    augmented = [
        list(row) + [-term if index < 6 else -max(0.0, term)]
        for index, (row, term) in enumerate(zip(jacobian, residual))
    ]
    solution = active_step(
        _RestorationBounds(model, len(values)),
        values + (0.0,),
        augmented,
        residual,
        checkpoint,
    )
    if solution is None or solution[-1] >= 1.0:
        return None
    delta = solution[:-1]
    predicted = tuple(
        term + math.fsum(a * b for a, b in zip(row, delta)) for row, term in zip(jacobian, residual)
    )
    before = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(residual))
    after = max(abs(term) if i < 6 else max(0.0, term) for i, term in enumerate(predicted))
    return delta if after < before else None
