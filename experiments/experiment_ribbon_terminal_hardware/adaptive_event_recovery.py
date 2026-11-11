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
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .adaptive_event_construction import Roots, construct
from .adaptive_event_plan import plan
from .adaptive_event_window import Edit, events
from .check import Report
from .gate import Gate
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
    transferred. Unresolved proofs cannot trigger insertion. A failed attempted
    rewrite returns the original source, not an enlarged fallback allocation.
    Removal prefers simpler certified geometry; missing pruning work is explicit,
    and no global minimality is claimed. All original physical checks remain.
    """
    validate(
        remaining_pairs=work.pairs,
        maximum_cpu_seconds=work.cpu_seconds,
        maximum_seconds=work.wall_seconds,
        maximum_updates=work.updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    if evidence.witness is None or evidence.status != (
        "blocked" if isinstance(evidence, Report) else "penetration"
    ):
        return None
    cpu, wall = process_time(), perf_counter()
    roots = Roots()
    current = source
    lineage = tuple((0, i) for i in range(len(source.pieces)))
    edits: list[Edit] = []
    iterations = pairs = contacts = 0
    contact_seconds = 0.0
    accepted: ContactResult | None = None
    stop = "work_exhausted"
    pruning_attempted = pruning_removed = pruning_unavailable = 0
    detail: dict[str, Any] = {
        "purpose": "adaptive_local_events",
        "initial_event_count": events(source),
    }

    def bounded() -> None:
        """
        Charge preparation, all local roots and every global proof to the original clocks.
        """
        checkpoint()
        if process_time() - cpu >= work.cpu_seconds or perf_counter() - wall >= work.wall_seconds:
            raise _Exhausted()

    def certify(route: FoldRoute) -> tuple[ContactResult | None, Report | None]:
        """
        Check physical contracts and complete changed-route clearance without a new pair or hardware pool.
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
        contacts += 1
        started = perf_counter()
        try:
            proof = inspect_contact(
                route,
                maximum_pairs=allowance,
                checkpoint=bounded,
                cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                projection_reuse=ProjectionReuse.CELLS,
                witness_probe=FlatProbe(),
                probe_order=ProbeOrder.ORIGINAL_PAIRS,
            )
        except _Exhausted:
            pairs += allowance
            detail["interrupted_pairs_charged_as_upper_bound"] = allowance
            raise
        finally:
            contact_seconds += perf_counter() - started
        if type(proof.pairs_checked) is not int or not 0 <= proof.pairs_checked <= allowance:
            raise ArithmeticError("Adaptive proof exceeded its remaining pair allocation")
        if proof.status == "separated" and proof.limit is not None:
            raise ArithmeticError("Incomplete material proof cannot certify adaptive geometry")
        pairs += proof.pairs_checked
        bounded()
        terminal_proof = (
            terminal.certify(route, "adaptive_events_complete")
            if proof.status == "separated"
            else None
        )
        bounded()
        return proof, terminal_proof

    try:
        bounded()
        if cap_error(source) > 1e-7 or material_error(source) > 1e-10:
            return None
        while iterations < work.updates and pairs < work.pairs and roots.attempted < 8:
            proposed = plan(current, evidence, terminal.hardware, bounded)
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
            if measured is None:
                stop = "global_contract_or_pair_budget"
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
            elif (
                measured.status == "separated"
                and hardware is not None
                and hardware.status == "blocked"
                and hardware.witness is not None
            ):
                evidence = hardware
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
        newton_steps=0,
        contacts=contacts,
        contact_pairs=pairs,
        contact_seconds=contact_seconds,
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
