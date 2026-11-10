"""
Continue one rejected material chain through actual blockers without renewing work.
"""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from math import ceil
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.separation import regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .check import Report
from .feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
    MaterialGuidance,
    ReturnLength,
)
from .gate import Gate
from .joint_contact import JointMode
from .joint_contact import recover as recover_joints
from .joint_handoff import JointHandoff
from .material_return import select_fold
from .recovery_limits import Work, validate


class SequenceStart(Enum):
    """
    Select ordinary evidence-driven entry or the existing blocked mating correction as the first stage.
    """

    EVIDENCE = "evidence"
    BLOCKED_MATING = "blocked_mating"


def recover(
    source: FoldRoute,
    contact: ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    start: SequenceStart = SequenceStart.EVIDENCE,
) -> Result:
    """
    Share the original allowance across coupled separation, distinct witnessed returns and straight correction.

    Only closed, actually measured blockers can hand off between stages. A
    material crossing selects the existing dominant turn once per fold, without
    trying another fold after failure. Hardware-only blockers start with fixed
    bends; initial straight-projection failure can expand joint mobility once
    before any motion, sharing the same original work.
    Earlier actual connector features remain guidance at the same fixed targets.
    One later crossing selecting an already reflected fold can continue with
    the current bend signs under the remaining allowance; it never flips back.
    All changed geometry needs full new contact and refined hardware proof.
    Each supported stage charges at least one logical update; ordinary unsupported
    preparation is also charged. Its actual ceil(Newton/6), pairs and total clocks can only reduce
    subsequent work. Invalid-source length is reported as a quality goal.
    An explicit blocked-mating entry retains its original first correction and
    performs no extra initial hardware measurement. Only a subsequent witnessed
    handoff or the existing explicit release turns that entry's length ceiling
    into a quality goal. Unsupported initial mating preparation can decline
    without motion or certificates, preserving its caller's original fallback.
    """
    if not isinstance(start, SequenceStart):
        raise ValueError("Choose an explicit recovery-sequence entry policy")
    if start is SequenceStart.BLOCKED_MATING and (
        contact.status != "penetration" or contact.witness is None
    ):
        raise ValueError("Blocked mating entry requires an actual material crossing")
    validate(
        remaining_pairs=work.pairs,
        maximum_cpu_seconds=work.cpu_seconds,
        maximum_seconds=work.wall_seconds,
        maximum_updates=work.updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    candidate = source
    evidence: ContactResult | Report = contact
    features: dict[tuple[object, ...], FeatureEvidence] = {}
    reflected: set[int] = set()
    material_continuation = False
    counters: dict[str, Any] = {
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
    }
    stages = 0
    accepted: Result | None = None
    stop = "work_exhausted"
    detail: dict[str, Any] = {}
    if start is SequenceStart.BLOCKED_MATING:
        detail.update(initial_stage=start.value, length_ceiling_released=False)

    def remaining() -> Work | None:
        """
        Include every preceding stage, report, witness preparation and unsuccessful correction.
        """
        checkpoint()
        return work.remaining(
            updates=counters["iterations"],
            pairs=counters["contact_pairs"],
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )

    def retain(route: FoldRoute, report: Report) -> bool:
        """
        Remember at most three actual connector features by stable material slot and terminal.
        """
        if report.status != "blocked" or report.witness is None:
            return True
        witness = report.witness
        if type(witness.piece) is not int or not 0 <= witness.piece < len(route.pieces):
            raise ValueError("Hardware witness must identify existing material")
        key = (witness.terminal, regions(route)[witness.piece])
        if key not in features and len(features) >= 3:
            return False
        features[key] = FeatureEvidence(route, report)
        return True

    def require_contract(route: FoldRoute) -> None:
        """
        Verify ordered caps and material independently of a child or existing clearance receipt.
        """
        if (
            route.targets != source.targets
            or cap_error(route) > 1e-7
            or material_error(route) > 1e-10
        ):
            raise ArithmeticError("Recovery sequence lost ordered caps or material geometry")

    while True:
        if remaining() is None:
            stop = "work_exhausted"
            break
        first_mating = start is SequenceStart.BLOCKED_MATING and stages == 0
        if not first_mating:
            measured = terminal.measure(candidate, "spatial_sequence_source")
            if not retain(candidate, measured):
                stop = "feature_capacity"
                break
        if (
            isinstance(evidence, ContactResult)
            and evidence.status == "separated"
            and terminal.certify(candidate, "spatial_sequence_existing").status == "clear"
        ):
            require_contract(candidate)
            accepted = Result(candidate, evidence, {})
            stop = "accepted"
            break
        mode: ContactGuidance | MaterialGuidance | JointMode
        if first_mating:
            mode = JointMode.BLOCKED_MATING
        elif isinstance(evidence, Report):
            if not retain(candidate, evidence):
                stop = "feature_capacity"
                break
            mode = ContactGuidance(tuple(features.values()), ContactMotion.ADAPTIVE_HARDWARE)
        elif evidence.status == "penetration" and evidence.witness is not None:
            selected = select_fold(candidate, evidence.witness)
            if selected is None or (selected in reflected and material_continuation):
                stop = "unsupported_or_repeated_return"
                break
            if selected in reflected:
                material_continuation = True
                mode = ContactGuidance(tuple(features.values()), ContactMotion.BEND_JOINTS)
            else:
                reflected.add(selected)
                mode = MaterialGuidance(
                    selected, tuple(features.values()), ReturnLength.RESTORATION_GOAL
                )
        else:
            mode = ContactGuidance(
                tuple(features.values()),
                ContactMotion.ADAPTIVE_HARDWARE
                if evidence.status == "separated"
                else ContactMotion.BEND_JOINTS,
            )
        left = remaining()
        if left is None:
            break
        if start is SequenceStart.BLOCKED_MATING and not first_mating:
            detail["length_ceiling_released"] = True
        yielded: list[JointHandoff] = []
        stages += 1
        stage_evidence: Report | Penetration | ContactResult = evidence
        if isinstance(mode, MaterialGuidance) or mode is JointMode.BLOCKED_MATING:
            assert isinstance(evidence, ContactResult) and evidence.witness is not None
            stage_evidence = evidence.witness
        result = recover_joints(
            candidate,
            stage_evidence,
            terminal,
            checkpoint,
            record,
            maximum_length_mm=maximum_length_mm,
            minimum_straight_mm=minimum_straight_mm,
            remaining_pairs=left.pairs,
            maximum_cpu_seconds=left.cpu_seconds,
            maximum_seconds=left.wall_seconds,
            maximum_updates=left.updates,
            mode=mode,
            on_blocked=yielded.append,
        )
        if result is None:
            if first_mating:
                detail["initial_mating_supported"] = False
                stop = "unsupported_initial_mating"
            else:
                counters["iterations"] += 1
                stop = "unsupported_guidance"
            break
        if first_mating:
            detail["initial_mating_supported"] = True
            detail["length_ceiling_released"] = result.detail.get("length_ceiling_released") is True
        spent = result.detail
        if any(
            type(spent[key]) is not int or spent[key] < 0
            for key in ("iterations", "newton_steps", "contacts", "contact_pairs")
        ):
            raise ArithmeticError("Joint stages must report nonnegative integer work")
        charged = max(1, spent["iterations"], ceil(spent["newton_steps"] / 6))
        if charged > left.updates or spent["contact_pairs"] > left.pairs:
            raise ArithmeticError("Joint stage exceeded its remaining allocation")
        counters["iterations"] += charged
        for key in ("newton_steps", "contacts", "contact_pairs", "contact_seconds"):
            counters[key] += spent[key]
        stop = spent["stop_reason"]
        if result.contact is not None and result.contact.status == "separated":
            require_contract(result.route)
            if terminal.certify(result.route, "spatial_sequence_final").status == "clear":
                accepted, stop = result, "accepted"
            else:
                stop = "final_hardware_not_clear"
            break
        if not yielded:
            break
        if len(yielded) != 1:
            raise ArithmeticError("A joint stage yielded more than one candidate")
        state = yielded[0]
        if state.route.targets != source.targets:
            raise ArithmeticError("Recovery handoff changed fixed targets")
        candidate, evidence = state.route, state.evidence
        record(
            {
                "stage": "spatial_sequence",
                "status": "handoff",
                "number": stages,
                "route": snapshot(candidate),
                "evidence": asdict(evidence),
                "spent": dict(counters),
            }
        )
    detail.update(
        counters,
        status="separated" if accepted is not None else "unresolved",
        method="evidence_driven_deviation_sequence",
        stop_reason=stop,
        stages=stages,
        reflected_folds=sorted(reflected),
        material_continuation=material_continuation,
        retained_hardware_features=len(features),
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
        length_goal_mm=maximum_length_mm,
        length_mm=(accepted.route if accepted is not None else candidate).material_length_mm,
    )
    detail["length_goal_excess_mm"] = max(0.0, detail["length_mm"] - maximum_length_mm)
    record({"stage": "spatial_sequence", "status": detail["status"], "detail": detail})
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    if detail["cpu_seconds"] >= work.cpu_seconds or detail["elapsed_seconds"] >= work.wall_seconds:
        accepted = None
        detail.update(status="unresolved", stop_reason="phase_budget")
        record({"stage": "spatial_sequence", "status": "unresolved", "detail": detail})
    return Result(
        accepted.route if accepted is not None else source,
        accepted.contact if accepted is not None else None,
        detail,
    )
