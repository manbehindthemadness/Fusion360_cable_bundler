"""
Spend one existing allocation on local topology changes and verified module removal.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import (
    ContactResult,
    ProbeOrder,
    ProjectionReuse,
    inspect_contact,
)
from experiments.experiment_ribbon_fold_route.contact_affine_witness import AffineWitnesses
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .adaptive_event_construction import Roots, construct
from .adaptive_event_continuation import recover as continue_fixed
from .adaptive_event_plan import plan
from .adaptive_event_schedule import (
    Action,
    Correction,
    choose,
    contains_contact,
    preparation_declined,
)
from .adaptive_event_window import Edit, EventId, Window, events, reidentify, reopen, select
from .check import Report
from .gate import Gate
from .hardware_contact_discovery import HardwareContacts
from .joint_handoff import JointHandoff
from .paired_event_handoff import recover as recover_pair
from .recovery_limits import Work, validate


class _Exhausted(RuntimeError):
    """
    End this original allocation without swallowing caller source/cancellation failures.
    """


def recover(
    source: FoldRoute,
    evidence: Report | ContactResult,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    work: Work,
    maximum_length_mm: float,
    minimum_straight_mm: float,
) -> Result | None:
    """
    Refine only strict geometric blockers and recertify every changed complete route.

    At most eight fitted local roots and the caller's remaining logical updates
    cover all windows and optional undo checks. There is no parent event-count
    ceiling. Windows keep both actual boundary poses; outer objects and their
    lineage survive unchanged. Old ordinal constraints or certificates are never
    transferred. Strict hardware blockers are checked before self-contact and can
    guide another update without spending a contact proof on known rejected
    geometry. Unresolved evidence cannot trigger insertion. An intact inserted
    module with a current strict blocker prefers one fixed-topology sequence
    before another rewrite; root exhaustion also permits that entry. Only an
    explicit unchanged hardware-preparation decline without a motion trial can
    leave event refinement eligible. The correction entry cannot renew itself.
    A failed phase returns the original source without renewing its allocation.
    One fixed entry may yield a new closed strict departure crossing before
    another reversal. Residual parent roots and updates can then refine that
    current material; spent correction cannot restart and old lineage is retired.
    Removal prefers simpler certified geometry; missing pruning work is explicit,
    and no global minimality is claimed. All original physical checks remain.
    A strict hardware blocker may receive one32comparison negative material
    screen before correction. Its current occupied member and neighbours order
    proposals only. A verified competing crossing can use existing local event
    refinement while caps are still closed if no intact inserted module contains
    both colliding members. Contained crossings retain fixed correction rather
    than repeatedly rebuilding the same module; a miss retains hardware correction.
    Negative work shares the original pair/CPU pools and supplies no clearance.
    The same bounded discovery precedes the first hardware-driven rewrite. A
    strict competing crossing starts correction with both current blockers;
    a miss or uncertainty preserves the ordinary refinement schedule.
    The initial fixed trial receives at most one logical update and six Newton steps.
    Only if that fixed trial fails, a supported exact paired return may use at
    most two remaining original updates, twelve Newton steps and two roots before
    extra events. This preserves simpler successful correction. Its root reclosure
    and hardware correction use their already charged actions; failure keeps
    every charge and the original incumbent for residual event refinement.
    Until full acceptance the original closed source remains the incumbent.
    Failure retains every charge and leaves only residual topology work; ordinary
    correction becomes eligible again only after new local geometry is constructed.
    After a rewrite, a supported strict two-fold material return may use one
    paired-branch sequence before another rewrite. Owned-module fixed correction
    retains priority over changing its root family. Paired recovery retains
    coexisting hardware and shares only the parent's genuine remaining roots,
    actions, Newton steps, comparisons, clocks and hardware gate. Every failed
    child charge survives, and failure retains the closed incumbent.
    """
    validate(
        remaining_pairs=work.pairs,
        maximum_cpu_seconds=work.cpu_seconds,
        maximum_seconds=work.wall_seconds,
        maximum_updates=work.updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
        maximum_newton_steps=work.newton_steps,
    )
    if evidence.witness is None or evidence.status != (
        "blocked" if isinstance(evidence, Report) else "penetration"
    ):
        return None
    cpu, wall = process_time(), perf_counter()
    roots = Roots(newton_limit=work.newton_steps)
    correction = Correction.READY
    pending: Action | None = None
    initial_hardware: Report | None = None
    current_hardware = evidence if isinstance(evidence, Report) else None
    paired_spent = False
    current = source
    evidence_source = source
    lineage: tuple[EventId, ...] = tuple((0, i) for i in range(len(source.pieces)))
    edits: list[Edit] = []
    iterations = pairs = contacts = 0
    contact_seconds = 0.0
    accepted: ContactResult | None = None
    stop = "work_exhausted"
    pruning_attempted = pruning_removed = pruning_unavailable = 0
    hardware_contacts = HardwareContacts()
    detail: dict[str, Any] = {
        "purpose": "adaptive_local_events",
        "initial_event_count": events(source),
        "reopened_windows": 0,
        "contact_checks_deferred": 0,
        "preparation_only_resumes": 0,
        "closed_material_resumes": 0,
    }

    def bounded() -> None:
        """
        Charge preparation, all local roots and every global proof to the original clocks.
        """
        checkpoint()
        if process_time() - cpu >= work.cpu_seconds or perf_counter() - wall >= work.wall_seconds:
            raise _Exhausted()

    def remaining() -> Work | None:
        """
        Deduct all prior geometry, proof and reporting work from the same original allocation.
        """
        checkpoint()
        return work.remaining(
            updates=iterations,
            pairs=pairs,
            newton_steps=roots.newton_steps,
            cpu_seconds=process_time() - cpu,
            wall_seconds=perf_counter() - wall,
        )

    def discover_material(route: FoldRoute, report: Report) -> ContactResult | None:
        """
        Charge initial and later negative discovery to the same original comparison and time pools.
        """
        nonlocal pairs, contact_seconds
        allowance = work.pairs - pairs
        if allowance <= 0:
            return None
        started = perf_counter()
        try:
            negative = hardware_contacts.inspect(route, report, allowance, bounded)
        except _Exhausted:
            charged = min(32, allowance)
            pairs += charged
            detail["interrupted_hardware_discovery_pairs"] = charged
            raise
        finally:
            contact_seconds += perf_counter() - started
        if negative is not None:
            pairs += negative.pairs_checked
        return negative

    def certify(route: FoldRoute) -> tuple[ContactResult | None, Report | None]:
        """
        Check hardware first, retaining actual evidence without renewing either proof pool.
        """
        nonlocal pairs, contacts, contact_seconds
        bounded()
        if (
            route.targets != source.targets
            or cap_error(route) > 1e-7
            or material_error(route) > 1e-10
        ):
            return None, None
        allowance = work.pairs - pairs
        if allowance <= 0:
            return None, None
        terminal_proof = terminal.certify(route, "adaptive_events_before_contact")
        if terminal_proof.status == "blocked" and terminal_proof.witness is not None:
            detail["contact_checks_deferred"] += 1
            negative = None
            if accepted is None and roots.attempted < 8 and iterations < work.updates:
                negative = discover_material(route, terminal_proof)
            record(
                {
                    "stage": "adaptive_proof",
                    "status": "contact_deferred",
                    "hardware": asdict(terminal_proof),
                    "contact": None,
                    "negative_discovery": None if negative is None else asdict(negative),
                    "contact_scope": "full_certificate_unattempted_for_strict_hardware_blocker",
                }
            )
            bounded()
            return negative, terminal_proof
        bounded()
        contacts += 1
        started = perf_counter()
        probe = FlatProbe()
        affine_context = AffineWitnesses()
        try:
            proof = inspect_contact(
                route,
                maximum_pairs=allowance,
                checkpoint=bounded,
                cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                projection_reuse=ProjectionReuse.CELLS,
                witness_probe=probe,
                probe_order=ProbeOrder.ORIGINAL_PAIRS,
                affine_witnesses=affine_context,
            )
        except _Exhausted:
            pairs += allowance
            detail["interrupted_pairs_charged_as_upper_bound"] = allowance
            raise
        finally:
            contact_seconds += perf_counter() - started
            detail.setdefault("flat_probe_preparations", []).append(probe.shape_preparations())
            detail.setdefault("affine_witnesses", []).append(affine_context.statistics())
        if type(proof.pairs_checked) is not int or not 0 <= proof.pairs_checked <= allowance:
            raise ArithmeticError("Adaptive proof exceeded its remaining pair allocation")
        if proof.status == "separated" and proof.limit is not None:
            raise ArithmeticError("Incomplete material proof cannot certify adaptive geometry")
        pairs += proof.pairs_checked
        record(
            {
                "stage": "adaptive_proof",
                "status": "contact_measured",
                "hardware": asdict(terminal_proof),
                "contact": asdict(proof),
            }
        )
        bounded()
        return proof, terminal_proof

    def select_workspace(route: FoldRoute, members: tuple[int, ...]) -> Window:
        """
        Retain complete surviving work areas before deriving their new local reference.
        """
        bounded()
        selected = select(route, members)
        if correction is Correction.SPENT:
            record(
                {
                    "stage": "adaptive_workspace",
                    "status": "subdivide_after_closed_material_handoff"
                    if detail["closed_material_resumes"]
                    else "subdivide_after_preparation_decline",
                    "window": [selected.begin, selected.end],
                    "parent_event_count": events(route),
                }
            )
            bounded()
            return selected
        expanded = reopen(selected, lineage, tuple(edits))
        if (expanded.begin, expanded.end) != (selected.begin, selected.end):
            detail["reopened_windows"] += 1
            record(
                {
                    "stage": "adaptive_workspace",
                    "status": "reopened",
                    "selected": [selected.begin, selected.end],
                    "window": [expanded.begin, expanded.end],
                    "parent_event_count": events(expanded.route),
                }
            )
        bounded()
        return expanded

    try:
        bounded()
        if cap_error(source) > 1e-7 or material_error(source) > 1e-10:
            return None
        if isinstance(evidence, Report):
            initial_competing = discover_material(current, evidence)
            record(
                {
                    "stage": "adaptive_proof",
                    "status": "initial_competing_contact",
                    "hardware": asdict(evidence),
                    "negative_discovery": None
                    if initial_competing is None
                    else asdict(initial_competing),
                    "contact_scope": "negative_discovery_only",
                }
            )
            bounded()
            if (
                initial_competing is not None
                and initial_competing.status == "penetration"
                and initial_competing.witness is not None
                and initial_competing.limit is None
            ):
                initial_hardware = evidence
                evidence = initial_competing
                pending = Action.CORRECT_COMPETING
        while iterations < work.updates and pairs < work.pairs:
            bounded()
            action = choose(
                current,
                evidence,
                evidence_source,
                lineage,
                tuple(edits),
                roots.attempted,
                correction,
            )
            if pending is not None and action is not Action.STOP:
                action = pending
            pending = None
            if (
                (
                    (edits and action is Action.REFINE)
                    or (action is Action.CORRECT_COMPETING and "initial_competing_trial" in detail)
                )
                and not paired_spent
                and evidence_source is current
                and isinstance(evidence, ContactResult)
                and roots.attempted <= 6
            ):
                left = remaining()
                initial_pair = not edits and action is Action.CORRECT_COMPETING
                if initial_pair and left is not None:
                    left = Work(
                        min(2, left.updates),
                        left.pairs,
                        left.cpu_seconds,
                        left.wall_seconds,
                        min(12, left.newton_steps),
                    )
                pair_yielded: list[JointHandoff] = []
                child_pair = (
                    None
                    if left is None
                    else recover_pair(
                        current,
                        evidence,
                        current_hardware,
                        terminal,
                        checkpoint,
                        record,
                        work=left,
                        maximum_roots=min(2, 8 - roots.attempted)
                        if initial_pair
                        else 8 - roots.attempted,
                        minimum_straight_mm=minimum_straight_mm,
                        on_event_refinement=pair_yielded.append,
                    )
                )
                if child_pair is not None:
                    paired_spent = True
                    spent_pair = child_pair.detail
                    iterations += spent_pair["updates"]
                    roots.attempted += spent_pair["roots_debited"]
                    roots.newton_steps += spent_pair["newton_steps"]
                    pairs += spent_pair["pairs"]
                    contacts += spent_pair["contact_checks"]
                    contact_seconds += spent_pair["contact_seconds"]
                    detail["paired_return"] = dict(spent_pair)
                    if initial_pair:
                        detail["initial_paired_trial"] = dict(spent_pair)
                    stop = spent_pair["stop_reason"]
                    bounded()
                    if child_pair.accepted is not None:
                        if pair_yielded:
                            raise ArithmeticError(
                                "A paired refinement handoff cannot also claim acceptance"
                            )
                        if not isinstance(child_pair.evidence, ContactResult):
                            raise ArithmeticError(
                                "Accepted paired geometry requires a material certificate"
                            )
                        lineage = reidentify(
                            current, lineage, child_pair.accepted, work.updates + 1
                        )
                        current, accepted, stop = (
                            child_pair.accepted,
                            child_pair.evidence,
                            "accepted",
                        )
                        break
                    if pair_yielded:
                        if len(pair_yielded) != 1 or stop != "event_refinement_handoff":
                            raise ArithmeticError(
                                "Require one explicit closed paired-refinement handoff"
                            )
                        if roots.attempted >= 8 or remaining() is None:
                            stop = "work_exhausted"
                            break
                        state = pair_yielded[0]
                        if (
                            state.route is not child_pair.evidence_route
                            or state.evidence is not child_pair.evidence
                        ):
                            raise ArithmeticError(
                                "Refinement must retain the actual measured paired candidate"
                            )
                        lineage = reidentify(current, lineage, state.route, work.updates + 1)
                        current, evidence, evidence_source = (
                            state.route,
                            state.evidence,
                            state.route,
                        )
                        current_hardware = None
                        correction = Correction.SPENT
                        detail["closed_material_resumes"] += 1
                        detail["paired_material_resumes"] = (
                            detail.get("paired_material_resumes", 0) + 1
                        )
                        record(
                            {
                                "stage": "adaptive_schedule",
                                "action": "refine_after_closed_paired_handoff",
                                "roots_attempted": roots.attempted,
                                "remaining_updates": work.updates - iterations,
                                "route": snapshot(current),
                                "evidence": asdict(evidence),
                            }
                        )
                        continue
                    if remaining() is None:
                        break
                    if initial_pair:
                        correction = Correction.AWAITING_REFINEMENT
                        if initial_hardware is not None:
                            evidence = initial_hardware
                            current_hardware = initial_hardware
                            evidence_source = current
                        pending = Action.REFINE
                        record(
                            {
                                "stage": "adaptive_schedule",
                                "action": "refine_after_bounded_paired_trial",
                                "remaining_updates": work.updates - iterations,
                                "remaining_roots": 8 - roots.attempted,
                                "source_retained": True,
                            }
                        )
                    continue
            if action is Action.CORRECT_COMPETING and "initial_competing_trial" in detail:
                if initial_hardware is None:
                    raise ArithmeticError("Initial correction must retain its hardware evidence")
                evidence = initial_hardware
                current_hardware = initial_hardware
                action = Action.REFINE
            if action is Action.STOP:
                if not edits and iterations == 0:
                    return None
                stop = "work_exhausted" if roots.attempted == 8 else "unsupported_local_witness"
                break
            if action in (
                Action.CORRECT_COMPETING,
                Action.CORRECT_MODULE,
                Action.CORRECT_EXHAUSTED,
                Action.CORRECT_DECLINED,
            ):
                record(
                    {
                        "stage": "adaptive_schedule",
                        "action": action.value,
                        "roots_attempted": roots.attempted,
                        "remaining_updates": work.updates - iterations,
                    }
                )
                left = remaining()
                if left is None:
                    stop = "work_exhausted"
                    break
                correction = (
                    Correction.AWAITING_REFINEMENT
                    if action is Action.CORRECT_COMPETING
                    else Correction.SPENT
                )
                if action is Action.CORRECT_COMPETING:
                    left = Work(
                        1,
                        left.pairs,
                        left.cpu_seconds,
                        left.wall_seconds,
                        min(6, left.newton_steps),
                    )
                yielded: list[JointHandoff] = []
                callbacks: dict[str, Any] = {}
                if roots.attempted < 8:
                    callbacks["on_event_refinement"] = yielded.append
                # Reduced child clocks preserve actual completed counters even
                # when the original clock rejects the following receipt.
                child = continue_fixed(
                    current,
                    evidence,
                    terminal,
                    checkpoint,
                    record,
                    work=left,
                    maximum_length_mm=maximum_length_mm,
                    minimum_straight_mm=minimum_straight_mm,
                    **callbacks,
                )
                spent = child.detail
                iterations += spent["iterations"]
                roots.newton_steps += spent["newton_steps"]
                contacts += spent["contacts"]
                pairs += spent["contact_pairs"]
                contact_seconds += spent["contact_seconds"]
                detail["fixed_continuation"] = dict(spent)
                if action is Action.CORRECT_COMPETING:
                    detail["initial_competing_trial"] = dict(spent)
                detail["correction_schedule"] = action.value
                stop = spent["stop_reason"]
                record(
                    {
                        "stage": "adaptive_continuation",
                        "status": spent["status"],
                        "detail": dict(spent),
                    }
                )
                bounded()
                if yielded and child.contact is not None:
                    raise ArithmeticError("A closed material yield cannot also claim acceptance")
                if child.contact is not None:
                    lineage = reidentify(current, lineage, child.route, work.updates + 1)
                    current, accepted, stop = child.route, child.contact, "accepted"
                    break
                if yielded:
                    if (
                        len(yielded) != 1
                        or stop != "event_refinement_handoff"
                        or spent.get("status") != "unresolved"
                    ):
                        raise ArithmeticError(
                            "Adaptive refinement requires one explicit closed yield"
                        )
                    if roots.attempted >= 8 or remaining() is None:
                        stop = "work_exhausted"
                        break
                    state = yielded[0]
                    lineage = reidentify(current, lineage, state.route, work.updates + 1)
                    current, evidence = state.route, state.evidence
                    evidence_source = current
                    detail["closed_material_resumes"] += 1
                    record(
                        {
                            "stage": "adaptive_schedule",
                            "action": "refine_after_closed_material_handoff",
                            "roots_attempted": roots.attempted,
                            "remaining_updates": work.updates - iterations,
                            "route": snapshot(current),
                            "evidence": asdict(evidence),
                        }
                    )
                    continue
                if action is Action.CORRECT_COMPETING and remaining() is not None:
                    if child.route is not current or initial_hardware is None:
                        raise ArithmeticError(
                            "A failed initial trial must retain its closed incumbent"
                        )
                    pending = Action.CORRECT_COMPETING
                    record(
                        {
                            "stage": "adaptive_schedule",
                            "action": "paired_after_bounded_competing_trial",
                            "remaining_updates": work.updates - iterations,
                            "remaining_newton_steps": work.newton_steps - roots.newton_steps,
                            "source_retained": True,
                        }
                    )
                    continue
                if (
                    action is Action.CORRECT_MODULE
                    and roots.attempted < 8
                    and preparation_declined(child, current, evidence)
                    and remaining() is not None
                ):
                    detail["preparation_only_resumes"] += 1
                    record(
                        {
                            "stage": "adaptive_schedule",
                            "action": "refine_after_preparation_decline",
                            "roots_attempted": roots.attempted,
                            "remaining_updates": work.updates - iterations,
                        }
                    )
                    continue
                break
            stop = "work_exhausted"
            proposed = plan(
                current, evidence, terminal.hardware, bounded, select_window=select_workspace
            )
            if proposed is None:
                if not edits and iterations == 0:
                    return None
                stop = "unsupported_local_witness"
                break
            iterations += 1
            window = proposed.window
            record(
                {
                    "stage": "adaptive_events",
                    "status": "planned",
                    "window": [window.begin, window.end],
                    "event_count": events(current),
                    "offset_mm": asdict(proposed.offset_mm),
                    "evidence": asdict(evidence),
                }
            )
            local = construct(proposed, minimum_straight_mm, roots, bounded, record)
            if local is None:
                stop = "no_closed_local_allocation"
                if correction is Correction.READY:
                    pending = Action.CORRECT_DECLINED
                    continue
                break
            candidate = window.splice(local)
            children = tuple((iterations, i) for i in range(len(local.pieces)))
            edit = Edit(
                children,
                lineage[window.begin : window.end],
                current.pieces[window.begin : window.end],
                local.pieces,
            )
            lineage = lineage[: window.begin] + children + lineage[window.end :]
            edits.append(edit)
            current = candidate
            if correction is Correction.AWAITING_REFINEMENT:
                correction = Correction.READY
            record(
                {
                    "stage": "adaptive_events",
                    "status": "candidate",
                    "route": snapshot(current),
                    "event_count": events(current),
                    "inserted_ids": children,
                    "retired_ids": edit.parents,
                }
            )
            measured, hardware = certify(current)
            current_hardware = (
                hardware if hardware is not None and hardware.status == "blocked" else None
            )
            if (
                hardware is not None
                and hardware.status == "blocked"
                and hardware.witness is not None
            ):
                if (
                    measured is not None
                    and measured.status == "penetration"
                    and measured.witness is not None
                    and measured.limit is None
                    and not contains_contact(current, measured, lineage, tuple(edits))
                ):
                    evidence = measured
                    pending = Action.REFINE
                    detail["hardware_contact_refinements"] = (
                        detail.get("hardware_contact_refinements", 0) + 1
                    )
                else:
                    evidence = hardware
                evidence_source = current
                continue
            if measured is None:
                stop = (
                    "uncertain_global_proof"
                    if hardware is not None
                    else "global_contract_or_pair_budget"
                )
                break
            if (
                measured.status == "separated"
                and hardware is not None
                and hardware.status == "clear"
            ):
                accepted, stop = measured, "accepted"
                break
            if measured.status == "penetration" and measured.witness is not None:
                evidence = measured
                evidence_source = current
            else:
                stop = "uncertain_global_proof"
                break
        if accepted is not None:
            for edit in reversed(edits):
                bounded()
                if iterations >= work.updates or pairs >= work.pairs:
                    break
                reverted = edit.undo(current, lineage)
                if reverted is None:
                    pruning_unavailable += 1
                    continue
                iterations += 1
                pruning_attempted += 1
                simpler, parent_ids = reverted
                measured, hardware = certify(simpler)
                removed = (
                    measured is not None
                    and measured.status == "separated"
                    and hardware is not None
                    and hardware.status == "clear"
                )
                if removed:
                    current, lineage, accepted = simpler, parent_ids, measured
                    pruning_removed += 1
                record(
                    {
                        "stage": "adaptive_events",
                        "status": "module_removed" if removed else "module_retained",
                        "ids": edit.children,
                    }
                )
        bounded()
    except _Exhausted:
        accepted, stop = None, "phase_budget"
    detail.update(
        status="separated" if accepted is not None else "unresolved",
        stop_reason=stop,
        iterations=iterations,
        newton_steps=roots.newton_steps,
        local_reclosures=roots.reclosures,
        contacts=contacts,
        contact_pairs=pairs,
        contact_seconds=contact_seconds,
        hardware_contact_discovery=hardware_contacts.statistics(),
        roots_attempted=roots.attempted,
        declined_roots=roots.declined,
        event_count=events(current),
        rewrites=len(edits),
        pruning_attempted=pruning_attempted,
        modules_removed=pruning_removed,
        pruning_unavailable=pruning_unavailable,
        pruning_unattempted=len(edits) - pruning_attempted - pruning_unavailable,
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
        length_mm=current.material_length_mm,
        length_goal_mm=maximum_length_mm,
        length_goal_excess_mm=max(0.0, current.material_length_mm - maximum_length_mm),
    )
    record(
        {
            "stage": "adaptive_events",
            "status": detail["status"],
            "detail": dict(detail),
            "candidate": snapshot(current),
        }
    )
    if process_time() - cpu >= work.cpu_seconds or perf_counter() - wall >= work.wall_seconds:
        accepted = None
        detail.update(status="unresolved", stop_reason="phase_budget")
        record({"stage": "adaptive_events", "status": "unresolved", "detail": dict(detail)})
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    return Result(current if accepted is not None else source, accepted, detail)
