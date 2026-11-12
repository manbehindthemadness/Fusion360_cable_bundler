"""
Select inactive material guidance without treating current slack as future clearance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence

from experiments.experiment_ribbon_feature_insertion.separation import Side

from .flat_separation import FlatSeparation
from .material_constraint import MaterialConstraint


@dataclass(frozen=True)
class InactiveGuidance:
    """
    Identify one strictly satisfied full bound at the current coordinates only.
    """

    index: int
    gap: float


def least_binding(
    constraints: Sequence[tuple[FlatSeparation | MaterialConstraint, Side]],
    values: tuple[float, ...],
    scale: float,
    checkpoint: Callable[[], None],
) -> InactiveGuidance | None:
    """
    Choose the largest finite slack using the existing material-guide inequality.

    Exact ties retain original order. Each evaluation is charged to the caller's
    clock. This neither removes a constraint nor certifies later motion: callers
    must invalidate equations when replacing guidance and retain full final proofs.
    """
    chosen: InactiveGuidance | None = None
    threshold = 1e-8 / scale
    for index, (bound, side) in enumerate(constraints):
        checkpoint()
        gap = bound.gap(values, side)
        if math.isfinite(gap) and gap > threshold and (chosen is None or gap > chosen.gap):
            chosen = InactiveGuidance(index, gap)
    return chosen
