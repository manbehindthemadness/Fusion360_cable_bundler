"""
Couple an actual mating-runway crossing with hardware before separate corrections spend the same work.
"""

from __future__ import annotations

from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import (
    ClosurePolicy,
    MovableBends,
    retract_active,
)
from experiments.experiment_ribbon_feature_insertion.attached_regions import with_attached_straights
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    BaselinePolicy,
    Recovery,
)
from experiments.experiment_ribbon_feature_insertion.separation import Separation
from experiments.experiment_ribbon_feature_insertion.separation_step import plan_step
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    ProfileExtent,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_contact import JointMode
from experiments.experiment_ribbon_terminal_hardware.joint_contact import recover as recover_joints
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


def _ordinary_first_gap(
    source: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
) -> tuple[float | None, int]:
    """
    Predict the existing selected first correction with identical attachment, trust and ordered-cap rules.

    At most two preparatory six-Newton retractions share the caller's CPU/wall
    allowance, as in existing first-gap verification. They are recorded apart
    from committed recovery updates; this prediction grants no contact proof.
    Stop at the first improving retraction, even if its gap remains negative.
    """
    model = MovableBends(source)
    bound = Separation.from_measurement(model, source, measurement)
    if bound is None:
        return None, 0
    expanded = with_attached_straights(bound, source, measurement)
    if expanded.extra_regions:
        trial = plan_step(model, model.initial, expanded, None, checkpoint)
        if trial is not None and trial.fraction == 1.0:
            bound = expanded
    planned = plan_step(model, model.initial, bound, None, checkpoint)
    if planned is None:
        return None, 0
    for number, fraction in enumerate((planned.fraction, planned.fraction / 2), 1):
        checkpoint()
        values = retract_active(
            model,
            advance(model, model.initial, planned.delta, fraction),
            checkpoint,
            closure_policy=ClosurePolicy.ORDERED_CAPS,
        )
        if values is not None:
            gap = bound.gap(values, planned.side)
            if gap > planned.gap:
                return gap * model.scale, number
    return None, 2


def supported(
    source: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> bool:
    """
    Require an actual witnessed crossing involving the original first or last straight and flat support.

    Internal crossings and an ordinary first correction that already opens its
    gap retain their established sequence. Preparation shares the caller's
    clocks; no contact certificate, committed update or clearance is granted.
    """
    witness = measurement.witness
    if measurement.status != "penetration" or witness is None:
        return False
    if not any(
        i in (0, len(source.pieces) - 1) and isinstance(source.pieces[i].geometry, Straight)
        for i in witness.pieces
    ):
        return False
    if (
        FlatSeparation.create(SignedJoints(source), source, witness, extent=ProfileExtent.COMPLETE)
        is None
    ):
        return False
    gap, retractions = _ordinary_first_gap(source, measurement, checkpoint)
    opens = gap is not None and gap > 0
    record(
        {
            "stage": "mating_feasibility_prediction",
            "status": "ordinary_gap_opened" if opens else "coupling_required",
            "gap_mm": gap,
            "preparation_retractions": retractions,
            "preparation_newton_upper_bound": 6 * retractions,
            "committed_updates": 0,
            "contact_certificates": 0,
        }
    )
    return not opens


def recover(
    baseline: FoldRoute,
    source: FoldRoute,
    measurement: ContactResult,
    terminal: Gate,
    threshold_mm: float,
    work: Work,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Recovery | None:
    """
    Use the existing coupled engine inside unused original work after actual blocked-baseline eligibility.

    The caller owns the measured blocked-baseline proof and charges eligibility
    preparation to its original clocks. Return None only without motion or a
    contact certificate. A returned restoration preserves the baseline length
    ceiling and requires strict caps/material/native/self/hardware certification;
    guide preferences cannot veto restored physical feasibility. No guessed
    frame, radius, candidate bank or renewed work allowance is introduced.
    """
    if measurement.status != "penetration" or measurement.witness is None:
        return None
    child = recover_joints(
        source,
        measurement.witness,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=baseline.material_length_mm,
        minimum_straight_mm=threshold_mm,
        remaining_pairs=work.pairs,
        maximum_cpu_seconds=work.cpu_seconds,
        maximum_seconds=work.wall_seconds,
        maximum_updates=work.updates,
        mode=JointMode.MATING_CEILING,
    )
    if child is None:
        return None
    return Recovery(
        child.route if child.contact is not None else None,
        child.contact,
        child.detail["contact_pairs"],
        child.detail["contacts"],
        child.detail["contact_seconds"],
        child.detail,
        BaselinePolicy.RESTORE_BLOCKED,
    )
