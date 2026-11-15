"""
Retain complete-member hardware guidance unless another halfspace already proves its required gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .feature_guidance import member_planes
from .feature_plane import FeaturePlane


@dataclass(frozen=True)
class Refresh:
    """
    Keep ordered member coverage and distinguish attempted reselection from changed guidance.
    """

    planes: list[FeaturePlane]
    changed: tuple[int, ...]
    attempts: int


def separated_alternatives(
    planes: list[FeaturePlane],
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    minimum_gap_mm: float,
) -> Refresh:
    """
    Replace stale violated guidance only with an already-separated complete-member bound.

    Each independent member may use the existing fifteen-axis selection once.
    Uncertain or still-intruding choices retain their original plane; an already
    satisfied plane is untouched. Preserve the exact box, model, ordered member
    identity and required positive gap. These bounds guide the next correction,
    never certify the entire route or waive final hardware/contact measurements.
    Caller checkpoints bound all work and propagate cancellation without a result.
    The own-terminal straight retains its explicit zero mating-boundary goal;
    it never acquires permission to penetrate or a hardware certificate.
    """
    if not math.isfinite(minimum_gap_mm) or minimum_gap_mm <= 0:
        raise ValueError("Use the existing positive hardware gap")
    if any(plane.members != (plane.reference,) for plane in planes):
        raise ValueError("Refresh only independent complete-member planes")
    result = list(planes)
    changed: list[int] = []
    attempts = 0
    for index, plane in enumerate(planes):
        checkpoint()
        minimum = (0.0 if plane.mating_straight else minimum_gap_mm) / plane.model.scale
        if plane.gap(values) >= minimum:
            continue
        attempts += 1
        chosen = member_planes([plane], plane.model, values)
        checkpoint()
        alternative = chosen[0]
        if alternative.gap(values) >= minimum:
            result[index] = alternative
            changed.append(index)
    return Refresh(result, tuple(changed), attempts)
