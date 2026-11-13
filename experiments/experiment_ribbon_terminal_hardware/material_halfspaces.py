"""
Refresh stale material guidance only after the same complete flat phases already separate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Union

from experiments.experiment_ribbon_feature_insertion.separation import Side

from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint

Constraint = Union[FlatSeparation, MaterialConstraint]


@dataclass(frozen=True)
class Refresh:
    """
    Preserve every ordered constraint while reporting completed direction reselections.
    """

    constraints: list[tuple[Constraint, Side]]
    changed: tuple[int, ...]
    attempts: int


def separated_alternatives(
    constraints: list[tuple[Constraint, Side]],
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    minimum_gap_mm: float,
) -> Refresh:
    """
    Replace only violated flat guidance with a currently separated same-coverage bound.

    Satisfied axes and whole-piece curved guidance stay unchanged. Uncertain or
    overlapping alternatives retain the original constraint and side. All work
    uses caller checkpoints; this grants neither another optimizer nor physical
    acceptance. A changed axis requires fresh raw-equation evaluation by callers.
    """
    if not math.isfinite(minimum_gap_mm) or minimum_gap_mm <= 0:
        raise ValueError("Use the existing positive material gap")
    result = list(constraints)
    changed: list[int] = []
    attempts = 0
    for index, (constraint, side) in enumerate(constraints):
        checkpoint()
        flat = constraint.bound if isinstance(constraint, MaterialConstraint) else constraint
        if not isinstance(flat, FlatSeparation):
            continue
        if flat.gap(values, side) * flat.model.scale >= minimum_gap_mm:
            continue
        attempts += 1
        alternative = flat.separated_alternative(values, checkpoint, minimum_gap_mm=minimum_gap_mm)
        if alternative is None:
            continue
        result[index] = (
            MaterialConstraint(alternative)
            if isinstance(constraint, MaterialConstraint)
            else alternative,
            Side.BEFORE,
        )
        changed.append(index)
    return Refresh(result, tuple(changed), attempts)
