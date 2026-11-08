"""
Keep absent native runway slots out of a sub-native linear correction before exact cap reclosure.
"""

from __future__ import annotations

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_relaxation.steps import projected


def native_slot_step(
    model: MovableBends,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    equation: tuple[float, ...],
    delta: tuple[float, ...],
    minimum_straight_mm: float,
) -> tuple[float, ...] | None:
    """
    Reproject one correction with exact-zero slots fixed when their motion cannot make a native piece.

    Restrict only currently absent runways whose proposed change is below the
    existing native minimum. Positive slots and larger zero-slot growth stay free.
    Reuse the same Jacobian and cap/gap equations; no additional nonlinear motion
    or acceptance tolerance is granted. Return None if the restricted projection
    is infeasible. Caller still recloses and certifies the actual final geometry.
    """
    fixed = {
        i
        for i in model.straight_indices
        if values[i] == 0 and abs(delta[i]) * model.scale <= minimum_straight_mm
    }
    if not fixed:
        return delta
    rows = [[0.0 if i in fixed else value for i, value in enumerate(row)] for row in jacobian]
    return projected(model, values, rows, [-value for value in equation], [0.0] * len(values))
