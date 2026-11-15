"""
Refresh a complete hardware member's separating axis between accepted correction poses.
"""

from __future__ import annotations

from typing import Callable

from experiments.experiment_ribbon_paired_return.allocation import HardwareRow
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import member_planes


def reorient(
    row: HardwareRow,
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> HardwareRow:
    """
    Select a better separating bound only for an already-satisfied individual member.

    Preserve the exact member, fixed hardware box, model and minimum gap. Own
    mating straights, grouped bounds and currently violated guidance retain their
    existing axis. The caller fixes the returned equation throughout the next
    Newton derivative/projection/trial sequence. This supplies no clearance
    certificate and allocates no projection, root, action or geometry trial.
    Source-mating protections and material rows are outside this typed operation.
    Cancellation and malformed selection propagate without a partial result.
    """
    checkpoint()
    plane = row.plane
    if plane.members != (plane.reference,) or plane.mating_straight or row(values) > 0:
        return row
    selected = member_planes([plane], plane.model, values)
    checkpoint()
    if len(selected) != 1:
        raise ArithmeticError("Hardware axis selection must retain one complete member")
    candidate = selected[0]
    if (
        candidate.model is not plane.model
        or candidate.box != plane.box
        or candidate.reference != plane.reference
        or candidate.members != plane.members
        or candidate.minimum_gap_mm != plane.minimum_gap_mm
    ):
        raise ArithmeticError("Hardware axis selection changed its physical member or gap")
    if (candidate.family, candidate.side) == (plane.family, plane.side):
        return row
    return HardwareRow(candidate) if candidate.gap(values) > plane.gap(values) else row
