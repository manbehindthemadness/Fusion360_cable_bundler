"""
Express clearance-driven feature redistribution through existing interior straight travel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from experiments.experiment_ribbon_fold_relaxation.flexible_steps import DEFAULT_STEPS

from .feature_plane import FeaturePlane, SignedJoints
from .model import Terminal


@dataclass(frozen=True)
class Redistribution:
    """
    Prefer a bounded transfer of existing travel and turn between neighbouring features.

    This is a projection reference, not a proposed route or a clearance proof.
    Cap/feature equations, coordinate bounds and final certificates remain mandatory.
    """

    reference: tuple[float, ...]
    donor_slot: int
    receiving_slots: tuple[int, ...]
    terminal_folds: tuple[int, ...]


def redistribution(
    model: SignedJoints, values: tuple[float, ...], planes: Sequence[FeaturePlane]
) -> Redistribution | None:
    """
    Use an occupied interior straight to separate a measured blocked terminal turn from its neighbour.

    Only own-terminal fold constraints establish eligibility. Existing terminal
    mating straights are never donors. Transfer straight length neutrally in the
    reference and preserve the neighbouring pair's signed angle sum; the full
    nonlinear cap equations still govern the actual motion. This is no requirement
    for equal spacing, spare material, additional folds or a larger length allowance.
    """
    count = len(model.folds)
    if len(values) != len(model.initial) or any(not math.isfinite(v) for v in values):
        raise ValueError("Use complete finite coordinates from the current material model")
    if count < 3:
        return None
    indices = {full: index for index, full in enumerate(model.indices)}
    selected: dict[int, tuple[int, int]] = {}
    for plane in planes:
        if plane.model is not model:
            raise ValueError("Workspace constraints must belong to the same material model")
        region = plane.reference
        if region.straight:
            continue
        if plane.box.terminal is Terminal.START and region.fold == 0:
            selected[0] = (1, 1)
        elif plane.box.terminal is Terminal.END and region.fold == count - 1:
            selected[count - 1] = (count - 2, count - 1)
    receivers = tuple(sorted({slot for _, slot in selected.values()}))
    donors = tuple(slot for slot in range(1, count) if slot not in receivers)
    if not selected or not donors:
        return None
    donor = max(donors, key=lambda slot: values[indices[4 * slot]])
    transfer = min(DEFAULT_STEPS.linear_fraction, values[indices[4 * donor]] / 2)
    if transfer <= 1e-12:
        return None
    reference = [0.0] * len(values)
    reference[indices[4 * donor]] = -transfer
    for slot in receivers:
        reference[indices[4 * slot]] = transfer / len(receivers)
    for terminal, (neighbour, _) in selected.items():
        index = indices[4 * terminal + 1]
        angle = values[index]
        motion = -math.copysign(min(DEFAULT_STEPS.angle_radians, abs(angle)), angle)
        reference[index] += motion
        reference[indices[4 * neighbour + 1]] -= motion
    return Redistribution(tuple(reference), donor, receivers, tuple(sorted(selected)))
