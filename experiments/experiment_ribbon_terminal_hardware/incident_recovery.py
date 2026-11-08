"""
Prioritize a proven incident fold intrusion over unresolved contact within one existing recovery.
"""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from time import perf_counter, process_time
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    Penetration,
    ProjectionReuse,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .check import Report
from .flat_separation import paired_return_fold
from .gate import Gate
from .incident_model import IncidentJoints
from .joint_contact import recover as recover_contact
from .recovery_limits import Work, validate
from .return_contact import recover as recover_return_contact
from .reversal import close_update
from .reversal_model import incident_fold


class ContactCompletion(Enum):
    """
    Retain historical stopping or use unused work on a terminal return's measured flat crossing.
    """

    STOP = "stop"
    REMAINING_JOINT = "remaining_joint"


class _Exhausted(RuntimeError):
    """
    Stop optional incident correction while preserving caller source/cancellation/resource errors.
    """


def recover(
    source: FoldRoute,
    evidence: Report,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
) -> Recovery | None:
    """
    Reclose one measured free incident reversal, then correct its actual connector and flat contacts.

    All phases share four updates/24Newton steps, at most0.35CPU/two wall seconds
    and the supplied original pair pool. No other fold, sign family, radius or
    endpoint candidate is tried. The caller selects this strategy only for proven
    hardware intrusion beside unresolved depth contact; known penetration retains
    its established contact-first strategy. Failure retains no accepted geometry.
    """
    if evidence.status != "blocked" or evidence.witness is None:
        return None
    selected = incident_fold(source, evidence.witness)
    if selected is None:
        return None
    return _recover_selected(
        source,
        selected,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        completion=ContactCompletion.STOP,
    )


def recover_return(
    source: FoldRoute,
    witness: Penetration,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
) -> Recovery | None:
    """
    Reverse only a nonadjacent fold proven to cross an original terminal straight.

    Material incidence selects one existing fold; no alternative sign or event
    is tried. Unsupported pairs return None without correction. A supported
    attempt may finish actual flat contacts with its unused original work.
    """
    first, second = witness.pieces
    if not 0 <= first < second < len(source.pieces):
        raise ValueError("A return witness must identify two ordered existing pieces")
    start_straight = first == 0 and isinstance(source.pieces[first].geometry, Straight)
    end_straight = second == len(source.pieces) - 1 and isinstance(
        source.pieces[second].geometry, Straight
    )
    other = second if start_straight else first
    if (
        not (start_straight or end_straight)
        or second - first <= 1
        or not isinstance(source.pieces[other].geometry, CylindricalFold)
    ):
        return None
    selected = sum(isinstance(piece.geometry, CylindricalFold) for piece in source.pieces[:other])
    return _recover_selected(
        source,
        selected,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        completion=ContactCompletion.REMAINING_JOINT,
    )


def recover_paired_return(
    source: FoldRoute,
    witness: Penetration,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int,
) -> Recovery | None:
    """
    Reflect only the entry fold of a measured adjacent-fold return using the caller's remaining work.
    """
    selected = paired_return_fold(source, witness)
    if selected is None:
        return None
    record(
        {
            "stage": "paired_fold_return",
            "status": "selected",
            "pieces": witness.pieces,
            "selected_fold": selected,
            "first_phase": "before",
            "second_phase": "after",
        }
    )
    return _recover_selected(
        source,
        selected,
        terminal,
        checkpoint,
        record,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        completion=ContactCompletion.REMAINING_JOINT,
    )


def _recover_selected(
    source: FoldRoute,
    selected: int,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    completion: ContactCompletion,
    maximum_updates: int = 4,
) -> Recovery:
    """
    Share one selected reflection, strict certificates and the supplied original update allocation.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    work = Work(maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds)
    cpu, wall = process_time(), perf_counter()
    model = IncidentJoints(source, selected)
    values = model.initial
    detail: dict[str, Any] = {
        "status": "unresolved",
        "method": "incident_reversal_flat_contact",
        "selected_fold": selected,
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
    }
    candidate = source
    accepted: FoldRoute | None = None
    contact: ContactResult | None = None
    stop = "unattempted"
    active_pairs: int | None = None
    contact_started = 0.0

    def bounded() -> None:
        """
        Charge all reflected closure, evidence, preparation and certificates to this single allocation.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    def emit(status: str, **data: Any) -> None:
        """
        Retain every attempted incident correction and its actual unfinished geometry.
        """
        record({"stage": "incident_flat_recovery", "status": status, **data})

    try:
        for _ in range(maximum_updates):
            bounded()
            detail["iterations"] += 1
            values, count, reason = close_update(model, values, bounded)
            detail["newton_steps"] += count
            proposed = model.route(values)
            assert proposed is not None
            candidate = proposed
            emit(
                "reclosure",
                selected_fold=selected,
                values=values,
                reason=reason,
                route=snapshot(candidate),
            )
            if max(map(abs, model.residual(values))) < 1e-13:
                break
            if reason is not None:
                stop = reason
                break
        else:
            stop = "incident_closure_limit"
        if max(map(abs, model.residual(values))) < 1e-13:
            if (
                cap_error(candidate) > 1e-7
                or material_error(candidate) > 1e-10
                or not model.preserves(candidate)
            ):
                raise ArithmeticError(
                    "Incident reflection changed ordered caps, material or fold identity"
                )
            if candidate.material_length_mm >= maximum_length_mm - 1e-7:
                stop = "not_shorter_than_parent"
            else:
                report = terminal.measure(candidate, "incident_reclosed_candidate")
                if report.status == "blocked" and report.witness is not None:
                    left = work.remaining(
                        updates=detail["iterations"],
                        pairs=0,
                        cpu_seconds=process_time() - cpu,
                        wall_seconds=perf_counter() - wall,
                    )
                    if left is None:
                        stop = "no_remaining_incident_work"
                    else:
                        recovered = recover_contact(
                            candidate,
                            report,
                            terminal,
                            checkpoint,
                            record,
                            maximum_length_mm=maximum_length_mm - 1e-7,
                            minimum_straight_mm=minimum_straight_mm,
                            remaining_pairs=left.pairs,
                            maximum_cpu_seconds=left.cpu_seconds,
                            maximum_seconds=left.wall_seconds,
                            maximum_updates=left.updates,
                        )
                        if recovered is not None:
                            for field in (
                                "iterations",
                                "newton_steps",
                                "contacts",
                                "contact_pairs",
                                "contact_seconds",
                            ):
                                detail[field] += recovered.detail[field]
                            detail["joint_contact"] = recovered.detail
                            stop = recovered.detail.get("stop_reason", "joint_contact_unresolved")
                            if (
                                recovered.contact is not None
                                and recovered.contact.status == "separated"
                            ):
                                accepted, contact = recovered.route, recovered.contact
                        else:
                            stop = "unsupported_joint_contact"
                elif report.status == "clear" and not any(
                    isinstance(p.geometry, Straight)
                    and p.geometry.material_length_mm <= minimum_straight_mm
                    for p in candidate.pieces
                ):
                    allowed = min(1024, remaining_pairs)
                    active_pairs = allowed
                    detail["contacts"] += 1
                    contact_started = perf_counter()
                    measured_contact = inspect_contact(
                        candidate,
                        maximum_pairs=allowed,
                        cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                        checkpoint=bounded,
                        projection_reuse=ProjectionReuse.CELLS,
                    )
                    detail["contact_seconds"] += perf_counter() - contact_started
                    contact = measured_contact
                    detail["contact_pairs"] += measured_contact.pairs_checked
                    active_pairs = None
                    if measured_contact.status == "separated":
                        accepted = candidate
                    else:
                        stop = "incident_contact_unresolved"
                        if completion is ContactCompletion.REMAINING_JOINT:
                            emit(
                                "contact",
                                contact=asdict(measured_contact),
                                route=snapshot(candidate),
                            )
                            left = work.remaining(
                                updates=detail["iterations"],
                                pairs=detail["contact_pairs"],
                                cpu_seconds=process_time() - cpu,
                                wall_seconds=perf_counter() - wall,
                            )
                            if left is not None:
                                continued = recover_return_contact(
                                    candidate,
                                    measured_contact,
                                    terminal,
                                    checkpoint,
                                    record,
                                    maximum_length_mm=maximum_length_mm,
                                    minimum_straight_mm=minimum_straight_mm,
                                    remaining_pairs=left.pairs,
                                    maximum_cpu_seconds=left.cpu_seconds,
                                    maximum_seconds=left.wall_seconds,
                                    maximum_updates=left.updates,
                                )
                                for key, value in (
                                    ("iterations", continued.detail["iterations"]),
                                    ("newton_steps", continued.detail["newton_steps"]),
                                    ("contacts", continued.contacts),
                                    ("contact_pairs", continued.pairs),
                                    ("contact_seconds", continued.contact_seconds),
                                ):
                                    detail[key] += value
                                detail["self_contact_continuation"] = continued.detail
                                if (
                                    continued.route is not None
                                    and model.preserves(continued.route)
                                    and terminal.permits(
                                        continued.route, "self_incident_contact_final"
                                    )
                                ):
                                    accepted, contact = continued.route, continued.contact
                else:
                    stop = "incident_hardware_unresolved"
        if accepted is not None:
            bounded()
            if (
                not model.preserves(accepted)
                or accepted.material_length_mm >= maximum_length_mm - 1e-7
            ):
                raise ArithmeticError(
                    "Incident contact repair lost its ordered folds or strict parent shortening"
                )
            detail["status"], stop = "separated", "accepted"
        detail.update(
            stop_reason=stop,
            length_mm=accepted.material_length_mm
            if accepted is not None
            else source.material_length_mm,
            cpu_seconds=process_time() - cpu,
            elapsed_seconds=perf_counter() - wall,
        )
        emit(
            detail["status"],
            detail=detail,
            candidate=snapshot(accepted if accepted is not None else candidate),
        )
        bounded()
    except _Exhausted:
        accepted = None
        contact = None
        detail["status"], detail["stop_reason"] = "unresolved", "phase_budget"
        detail.update(
            newton_steps_recorded_lower_bound=True,
            newton_steps_upper_bound=6 * maximum_updates,
            iterations_upper_bound=maximum_updates,
            length_mm=source.material_length_mm,
        )
        if active_pairs is not None:
            detail["contact_pairs"] += active_pairs
            detail["contact_seconds"] += perf_counter() - contact_started
            detail["interrupted_pairs_charged_as_upper_bound"] = active_pairs
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    return Recovery(
        accepted,
        contact if accepted is not None else None,
        detail["contact_pairs"],
        detail["contacts"],
        detail["contact_seconds"],
        detail,
    )
