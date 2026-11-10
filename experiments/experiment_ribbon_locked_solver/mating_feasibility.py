"""
Couple an actual mating-runway crossing with hardware before separate corrections spend the same work.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from experiments.experiment_ribbon_terminal_hardware.deviation_sequence import (
    SequenceStart,
)
from experiments.experiment_ribbon_terminal_hardware.deviation_sequence import (
    recover as recover_sequence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_separation import (
    FlatSeparation,
    ProfileExtent,
    mating_lead_crossing,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_contact import JointMode
from experiments.experiment_ribbon_terminal_hardware.joint_contact import recover as recover_joints
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


@dataclass(frozen=True)
class MatingSupport:
    """
    Retain the original failed first-motion prediction and its actual contact topology.

    This schedules correction only; neither trust clipping nor a failed gap
    prediction establishes clearance or grants more recovery work.
    """

    first_fraction: float | None
    straight_pair: bool

    @property
    def clipped_straights(self) -> bool:
        """
        Identify a confirmed straight crossing whose original correction exceeds one trust step.
        """
        return (
            self.straight_pair and self.first_fraction is not None and 0 < self.first_fraction < 1
        )


def _ordinary_first_gap(
    source: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
) -> tuple[float | None, int, float | None]:
    """
    Predict the existing selected first correction with identical attachment, trust and ordered-cap rules.

    At most two preparatory six-Newton retractions share the caller's CPU/wall
    allowance, as in existing first-gap verification. They are recorded apart
    from committed recovery updates; this prediction grants no contact proof.
    Stop at the first improving retraction, even if its gap remains negative.
    Return its gap, attempted retraction count and original trust fraction so
    the caller can schedule without repeating preparation.
    """
    model = MovableBends(source)
    bound = Separation.from_measurement(model, source, measurement)
    if bound is None:
        return None, 0, None
    expanded = with_attached_straights(bound, source, measurement)
    if expanded.extra_regions:
        trial = plan_step(model, model.initial, expanded, None, checkpoint)
        if trial is not None and trial.fraction == 1.0:
            bound = expanded
    planned = plan_step(model, model.initial, bound, None, checkpoint)
    if planned is None:
        return None, 0, None
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
                return gap * model.scale, number, planned.fraction
    return None, 2, planned.fraction


def supported(
    source: FoldRoute,
    measurement: ContactResult,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> MatingSupport | None:
    """
    Describe a witnessed mating crossing only when its existing first correction fails to open the gap.

    Crossings outside the mating leads and an ordinary first correction that already opens its
    gap retain their established sequence. Preparation shares the caller's
    clocks; no contact certificate, committed update or clearance is granted.
    Separate end straights and actual outward flats of the first/last folds
    describe the same entry/exit material; curved fold interiors stay excluded.
    Retain the already-computed trust fraction and whether both witnessed pieces
    are straight. Full-step and curved contacts need no repeated prediction.
    """
    witness = measurement.witness
    if measurement.status != "penetration" or witness is None:
        return None
    if not mating_lead_crossing(source, witness):
        return None
    if (
        FlatSeparation.create(SignedJoints(source), source, witness, extent=ProfileExtent.COMPLETE)
        is None
    ):
        return None
    gap, retractions, fraction = _ordinary_first_gap(source, measurement, checkpoint)
    opens = gap is not None and gap > 0
    record(
        {
            "stage": "mating_feasibility_prediction",
            "status": "ordinary_gap_opened" if opens else "coupling_required",
            "gap_mm": gap,
            "first_fraction": fraction,
            "preparation_retractions": retractions,
            "preparation_newton_upper_bound": 6 * retractions,
            "committed_updates": 0,
            "contact_certificates": 0,
        }
    )
    return (
        MatingSupport(
            fraction,
            all(isinstance(source.pieces[i].geometry, Straight) for i in witness.pieces),
        )
        if not opens
        else None
    )


def recover(
    baseline: FoldRoute,
    source: FoldRoute,
    measurement: ContactResult,
    terminal: Gate,
    threshold_mm: float,
    work: Work,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    baseline_policy: BaselinePolicy = BaselinePolicy.RESTORE_BLOCKED,
) -> Recovery | None:
    """
    Use the existing coupled engine inside unused original work after caller-owned eligibility.

    The caller measures baseline hardware and first-motion support, charging
    preparation to its original clocks. Return None only without motion or a
    contact certificate. Every returned restoration requires strict
    caps/material/native/self/hardware certification;
    guide preferences cannot veto restored physical feasibility. A caller using
    this for clear-baseline improvement must replace the restoration policy with
    ordinary guide dominance before selection. An explicitly blocked entry uses
    the existing mating correction as the shared sequence's first stage. Only
    its actual closed blocker can yield remaining work to the next stage; the
    inherited length ceiling then becomes a reported goal, as it already can
    after explicit local projection release. That restoration carries a separate
    policy through final selection;
    a clear entry always retains its hard length/guide requirements. No guessed
    frame, radius, candidate bank or renewed work allowance is introduced.
    """
    if baseline_policy not in (BaselinePolicy.GUIDE_IMPROVEMENT, BaselinePolicy.RESTORE_BLOCKED):
        raise ValueError("Enter mating recovery with measured baseline eligibility")
    if measurement.status != "penetration" or measurement.witness is None:
        return None
    if baseline_policy is BaselinePolicy.RESTORE_BLOCKED:
        child = recover_sequence(
            source,
            measurement,
            terminal,
            checkpoint,
            record,
            work=work,
            maximum_length_mm=baseline.material_length_mm,
            minimum_straight_mm=threshold_mm,
            start=SequenceStart.BLOCKED_MATING,
        )
        if child.detail.get("initial_mating_supported") is False:
            return None
    else:
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
        BaselinePolicy.RESTORE_BLOCKED_GOAL
        if baseline_policy is BaselinePolicy.RESTORE_BLOCKED
        and child.detail.get("length_ceiling_released") is True
        else baseline_policy,
    )
