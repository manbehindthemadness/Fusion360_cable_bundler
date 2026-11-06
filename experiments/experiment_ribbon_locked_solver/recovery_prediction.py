"""
Verify a promised full first correction before replacing a legacy recovery choice.
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends, retract_active
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation, TopologyChanged
from experiments.experiment_ribbon_feature_insertion.separation_step import InitialStep, plan_step
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact import ContactResult

from .recovery_evidence import EvidencePolicy, adjacent_straight_contact


class PredictionPolicy(Enum):
    """
    Preserve historical linear selection or verify an inconsistent one-step prediction.
    """

    LINEAR = "linear"
    VERIFIED_SHEETS = "verified_sheets"


def first_gap(planned: InitialStep, checkpoint: Callable[[], None]) -> float | None:
    """
    Measure the first cap-retracted gap using recovery's original two-halving rule.

    Only a full predicted correction is eligible. No contact certificate or
    committed recovery update occurs here. The caller charges every retraction
    and measurement to its existing selection/recovery time allowance. Missing
    support or changed topology returns no prediction; hard caller errors propagate.
    """
    if planned.step.fraction != 1.0:
        return None
    model = MovableBends(planned.source)
    bound = Separation.from_measurement(model, planned.source, planned.measurement)
    if bound is None:
        return None
    bound = replace(bound, plane=planned.plane)
    try:
        for fraction in (1.0, 0.5):
            checkpoint()
            values = retract_active(
                model, advance(model, model.initial, planned.step.delta, fraction), checkpoint
            )
            if values is not None:
                gap = bound.gap(values, planned.step.side)
                if gap > planned.step.gap:
                    return gap * model.scale
    except TopologyChanged:
        return None
    return None


def verified_sheets(
    candidates: tuple[tuple[Branch, ContactResult], ...],
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[Branch, ContactResult, InitialStep, float] | None:
    """
    Choose only an existing sheet correction whose full first motion opens its measured gap.

    Consult this bounded evidence preparation only after a legacy one-step
    prediction fails. No new roots, angles or contact certificates are generated.
    A positive gap is a motion prediction, not whole-route clearance.
    """
    prepared: list[tuple[Branch, ContactResult, InitialStep, float]] = []
    for branch, measurement in candidates:
        checkpoint()
        stronger, plane = adjacent_straight_contact(
            branch.route, measurement, checkpoint, record, policy=EvidencePolicy.CONFIRMED_SHEETS
        )
        if plane is None:
            continue
        model = MovableBends(branch.route)
        try:
            bound = Separation.from_measurement(model, branch.route, stronger)
            if bound is None:
                continue
            bound = replace(bound, plane=plane)
            planned = plan_step(model, model.initial, bound, None, checkpoint)
        except TopologyChanged:
            continue
        if planned is None or planned.fraction != 1.0:
            record(
                {
                    "stage": "recovery_sheet_prediction",
                    "roots": branch.roots,
                    "status": "not_a_full_step",
                    "fraction": planned.fraction if planned else None,
                }
            )
            continue
        initial = InitialStep(branch.route, stronger, planned, plane)
        gap = first_gap(initial, checkpoint)
        record(
            {
                "stage": "recovery_sheet_prediction",
                "roots": branch.roots,
                "status": "verified_first_gap" if gap is not None and gap > 0 else "no_first_gap",
                "actual_gap_mm": gap,
                "fraction": planned.fraction,
            }
        )
        if gap is not None and gap > 0:
            prepared.append((branch, stronger, initial, gap))
    return min(prepared, key=lambda item: item[0].priority) if prepared else None
