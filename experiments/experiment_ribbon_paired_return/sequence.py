"""
Prototype witnessed paired-branch changes under one shared root, motion and proof ledger.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.separation import regions
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import FeatureEvidence
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work

from .allocation import MaterialEvidence, allocate
from .continuation import correct_remaining, correct_started
from .discovery import Discovery
from .factors import alternate, bracket
from .ledger import Exhausted, Ledger


@dataclass(frozen=True)
class Result:
    """
    Distinguish accepted geometry from a rejected candidate and its own measured evidence.
    """

    accepted: FoldRoute | None
    last_candidate: FoldRoute
    evidence: ContactResult | Report
    evidence_route: FoldRoute
    detail: dict[str, Any]


def recover(
    source: FoldRoute,
    evidence: ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_roots: int,
    minimum_straight_mm: float,
    hardware_evidence: Report | None = None,
    on_event_refinement: Callable[[JointHandoff], None] | None = None,
) -> Result:
    """
    Follow actual new crossings without trying alternative root combinations or flipping back.

    The caller supplies only its remaining original allocation and the same gate
    shared for the complete sequence. An optional coexisting hardware blocker
    retains its current measured source pose before the first allocation.
    No budget, tolerance, target, event or certificate transfers from older runs.
    Every action starts charged, reserves both possible orientation roots before
    derivation, and performs at most one fixed-factor allocation. A newly measured
    hardware feature may use the current action's unspent Newton steps, without
    another allocation or root derivation. All earlier evidence remains retained.
    Unsupported or ambiguous
    evidence stops. Only a fresh full contact and refined hardware certificate
    can return accepted geometry. External failures propagate without fail-soft retry.
    """
    if evidence.status != "penetration" or evidence.witness is None or evidence.limit is not None:
        raise ValueError("Enter with an actual strict material crossing")
    if (
        type(minimum_straight_mm) not in (int, float)
        or not math.isfinite(minimum_straight_mm)
        or minimum_straight_mm <= 0
    ):
        raise ValueError("Use the unchanged positive native threshold")
    ledger = Ledger(work, maximum_roots, checkpoint)
    ledger.checkpoint()
    if cap_error(source) > 1e-7 or material_error(source) > 1e-10:
        raise ValueError("Enter with closed, unchanged material geometry")
    current = source
    actual: ContactResult | Report = evidence
    evidence_route = source
    material: list[MaterialEvidence] = []
    features: dict[tuple[object, ...], FeatureEvidence] = {}
    if hardware_evidence is not None:
        witness = hardware_evidence.witness
        if (
            hardware_evidence.status != "blocked"
            or witness is None
            or not 0 <= witness.piece < len(source.pieces)
        ):
            raise ValueError("Retain an actual coexisting hardware blocker on the source")
        key = (witness.terminal, regions(source)[witness.piece])
        features[key] = FeatureEvidence(source, hardware_evidence)
    changed: set[int] = set()
    owned: list[tuple[int, int]] = []
    accepted = None
    stop = "unresolved"
    contact_checks = 0
    contact_seconds = 0.0
    interrupted_pairs = 0
    carry_hardware = False
    discovery = Discovery(terminal, features, ledger, record)
    try:
        while True:
            ledger.checkpoint()
            if (
                on_event_refinement is not None
                and owned
                and ledger.updates < work.updates
                and ledger.roots < maximum_roots
                and isinstance(actual, ContactResult)
                and actual.witness is not None
                and actual.status == "penetration"
                and actual.limit is None
                and evidence_route is current
            ):
                next_pair = bracket(current, actual.witness)
                duplicate = any(
                    item.route is current and item.witness == actual.witness for item in material
                )
                if not duplicate and (next_pair is None or changed.intersection(next_pair.folds)):
                    if not ordered_mating_caps(current.pieces, current.targets):
                        stop = "open_refinement_handoff"
                        break
                    state = JointHandoff(current, actual)
                    record(
                        {
                            "stage": "paired_return",
                            "status": "closed_refinement_handoff",
                            "owned_pairs": tuple(owned),
                            "evidence": asdict(actual),
                        }
                    )
                    ledger.checkpoint()
                    on_event_refinement(state)
                    stop = "event_refinement_handoff"
                    break
            continuing = carry_hardware
            carry_hardware = False
            if not continuing:
                ledger.start_action()
            working = current
            candidate = None
            if continuing:
                record(
                    {
                        "stage": "paired_return",
                        "status": "continue_hardware_action",
                        "action": ledger.updates,
                        "remaining_action_newton": 6 - ledger.action_newton,
                        "evidence": asdict(actual),
                    }
                )
                candidate = correct_remaining(
                    current,
                    current,
                    tuple(owned),
                    tuple(material),
                    tuple(features.values()),
                    terminal.hardware,
                    minimum_straight_mm,
                    ledger,
                    record,
                    discovery=discovery,
                )
                if candidate is None:
                    stop = "hardware_continuation_unresolved"
                    break
            elif isinstance(actual, ContactResult):
                if actual.witness is None or actual.status != "penetration":
                    stop = "unsupported_material_evidence"
                    break
                ledger.charge_pairs(1)
                pair = bracket(current, actual.witness)
                if pair is None or changed.intersection(pair.folds):
                    duplicate = any(
                        item.route is current and item.witness == actual.witness
                        for item in material
                    )
                    if not owned or duplicate:
                        stop = "unsupported_or_repeated_pair"
                        break
                    material.append(MaterialEvidence(current, actual.witness))
                    record(
                        {
                            "stage": "paired_return",
                            "status": "continue_current_topology",
                            "owned_pairs": tuple(owned),
                            "new_witness": asdict(actual.witness),
                        }
                    )
                    candidate = correct_started(
                        current,
                        current,
                        tuple(owned),
                        tuple(material),
                        tuple(features.values()),
                        terminal.hardware,
                        minimum_straight_mm,
                        ledger,
                        record,
                        discovery=discovery,
                    )
                    if candidate is None:
                        stop = "material_continuation_unresolved"
                        break
                else:
                    material.append(MaterialEvidence(current, pair.witness))
                    working = alternate(current, pair, ledger)
                    if working is None:
                        stop = "unsupported_alternate"
                        break
                    changed.update(pair.folds)
                    owned.append(pair.folds)
                    record(
                        {
                            "stage": "paired_return",
                            "status": "refactored",
                            "folds": pair.folds,
                            "roots_debited": ledger.roots,
                            "roots_derived": ledger.derived_roots,
                        }
                    )
            elif actual.status != "blocked" or actual.witness is None:
                stop = "unsupported_hardware_evidence"
                break
            if candidate is None:
                candidate = allocate(
                    working,
                    current,
                    tuple(material),
                    tuple(features.values()),
                    terminal.hardware,
                    minimum_straight_mm,
                    ledger,
                )
            if candidate is None:
                candidate = correct_started(
                    working,
                    current,
                    tuple(owned),
                    tuple(material),
                    tuple(features.values()),
                    terminal.hardware,
                    minimum_straight_mm,
                    ledger,
                    record,
                    discovery=discovery,
                )
                if candidate is None:
                    stop = "allocation_unresolved"
                    break
            current = candidate
            discovery.latest = None
            discovery.last_proof = None
            record({"stage": "paired_return", "status": "candidate", "route": snapshot(current)})
            if (
                cap_error(current) > 1e-7
                or material_error(current) > 1e-10
                or any(
                    type(piece.geometry) is Straight
                    and piece.geometry.material_length_mm <= minimum_straight_mm
                    for piece in current.pieces
                )
            ):
                stop = "cap_material_or_native_failed"
                break
            hardware = terminal.certify(current, "paired_return_final")
            ledger.checkpoint()
            if hardware.status != "clear":
                actual = hardware
                evidence_route = current
                if hardware.status != "blocked" or hardware.witness is None:
                    stop = "hardware_unresolved"
                    break
                key = (hardware.witness.terminal, regions(current)[hardware.witness.piece])
                if key not in features and len(features) >= 3:
                    stop = "feature_capacity"
                    break
                carry_hardware = (
                    key not in features
                    and bool(owned)
                    and 0 < ledger.action_newton < 6
                    and ledger.newton_steps < work.newton_steps
                )
                features[key] = FeatureEvidence(current, hardware)
                continue
            allowance = work.pairs - ledger.pairs
            contact_checks += 1
            started = perf_counter()
            try:
                contact = inspect_contact(
                    current,
                    maximum_pairs=allowance,
                    checkpoint=ledger.checkpoint,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                )
            except Exhausted:
                ledger.charge_pairs(allowance)
                interrupted_pairs = allowance
                raise
            finally:
                contact_seconds += perf_counter() - started
            ledger.charge_pairs(contact.pairs_checked)
            actual = contact
            evidence_route = current
            record({"stage": "paired_return", "status": "contact", "report": asdict(contact)})
            ledger.checkpoint()
            if contact.status == "separated" and contact.limit is None:
                accepted, stop = current, "accepted"
                break
            if contact.status != "penetration" or contact.limit is not None:
                stop = "contact_unresolved"
                break
    except Exhausted as error:
        stop = str(error)
    if discovery.last_proof is not None:
        evidence_route, actual = discovery.last_proof
    elif discovery.latest is not None:
        actual = discovery.latest.report
        evidence_route = discovery.latest.route
    detail = {
        "status": "accepted" if accepted is not None else "unresolved",
        "stop_reason": stop,
        "updates": ledger.updates,
        "roots_debited": ledger.roots,
        "roots_derived": ledger.derived_roots,
        "pairs": ledger.pairs,
        "cpu_seconds": ledger.cpu_seconds,
        "seconds": ledger.wall_seconds,
        "newton_steps": ledger.newton_steps,
        "refactored_folds_attempted": sorted(changed),
        "owned_pairs": owned,
        "material_constraints": len(material),
        "hardware_features": len(features),
        "contact_checks": contact_checks,
        "contact_seconds": contact_seconds,
        "interrupted_pairs_charged_as_upper_bound": interrupted_pairs,
    }
    record({"stage": "paired_return", **detail})
    return Result(accepted, current, actual, evidence_route, detail)
