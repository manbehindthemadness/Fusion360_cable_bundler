"""
Polish one selected fixed-fold allocation against its actual ordered mating frames.
"""

from __future__ import annotations

import math
from typing import Callable

from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.straight_closure import correction
from experiments.experiment_ribbon_joint_route.allocation import Model


def polish(
    model: Model,
    values: tuple[float, ...],
    minimum_straight_mm: float,
    checkpoint: Callable[[], None],
    *,
    maximum_straight_mm: float | None = None,
) -> tuple[float, ...] | None:
    """
    Spend one affine correction on existing positive slots, with no root or active-set search.

    Only an already route-closed fixed-radius allocation is eligible. Derivatives
    are the actual straight directions, not differences of world-coordinate
    endpoints. Exact zero slots stay zero; no positive slot can disappear or
    become sub-native. Fold geometry and targets are unchanged. The same caller
    checkpoint bounds every stage. Failure returns None without altering the
    original allocation; success requires the recomposed actual strict mating
    predicate, never just a normalized affine residual. This supplies no contact
    or hardware certificate and grants no additional nonlinear correction.
    """
    checkpoint()
    if len(values) != model.size or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Use complete finite nonnegative allocation coordinates")
    if any(values[1::2]):
        raise ValueError("Mating polish requires fixed fold radii")
    if not math.isfinite(minimum_straight_mm) or minimum_straight_mm < 0:
        raise ValueError("Use a finite nonnegative native straight floor")
    if maximum_straight_mm is not None and (
        not math.isfinite(maximum_straight_mm) or maximum_straight_mm < 0
    ):
        raise ValueError("Use a finite nonnegative straight budget")
    diameter = model.source.targets.diameter_mm

    def admissible(coordinates: tuple[float, ...]) -> bool:
        """
        Preserve the original occupied slots, strict native floor and inherited sum gate.
        """
        return all(
            math.isfinite(v)
            and (v == 0 if old == 0 else v > 1e-10 and v * diameter > minimum_straight_mm)
            for old, v in zip(values[::2], coordinates[::2])
        ) and (
            maximum_straight_mm is None
            or math.fsum(coordinates[::2]) * diameter <= maximum_straight_mm + 1e-8 * diameter
        )

    if not admissible(values):
        return None
    pieces = model.pieces(values)
    targets = model.source.targets
    if ordered_mating_caps(pieces, targets):
        return values
    delta = correction(pieces, targets, tuple(v * diameter for v in values[::2]), checkpoint)
    if delta is None:
        return None
    result = list(values)
    for i, change in enumerate(delta):
        result[2 * i] += change / diameter
    proposed = tuple(result)
    checkpoint()
    if not admissible(proposed):
        return None
    closed = ordered_mating_caps(model.pieces(proposed), targets)
    checkpoint()
    return proposed if closed else None
