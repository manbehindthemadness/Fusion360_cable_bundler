"""
Replace exhausted local terminal correction with one measured spatial offset-and-return construction.
"""

from __future__ import annotations

from dataclasses import asdict
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation, fit
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_fold_route.contact import ProjectionReuse, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_traversal import ContactTraversal
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .deviation_closure import close as close_deviation
from .deviation_plan import plan
from .deviation_refinement import refine
from .gate import Gate
from .recovery_limits import Work, validate


class _Exhausted(RuntimeError):
    """
    Stop only this substituted recovery's original CPU/wall allocation.
    """


def recover(
    original: FoldRoute,
    terminal: Gate,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_length_mm: float,
    minimum_straight_mm: float,
    remaining_pairs: int,
    maximum_cpu_seconds: float,
    maximum_seconds: float,
    maximum_updates: int = 4,
) -> Result | None:
    """
    Derive one changed spatial reference from actual full-feature intrusion and construct exact roots.

    The two fixed cap poses, material profile/order and radius floor remain
    authoritative. One offset guide adds a third orientation stage, at most six
    folds/eight exact algebraic roots/128linear masks per root. Exact construction
    first attempts exact straight allocation. If every allocation fails, one
    original logical update permits at most four closure corrections of the
    closest original topology, retaining its physical factor policy. No other
    topology is refined after failure. Subsequent coupled refinement shares the
    original joint allowance; no alternate direction, guide or radius family is tried.
    Only the shortest closed allocation receives a self-contact certificate.
    Measured failure may consume genuinely unused work on one evidence-driven
    sequence of contact-selected returns and fixed-bend hardware correction.
    No other guide/root is attempted and no stage renews work.
    Pair-limited initial contact may resume its exact immutable material-cell
    traversal once within the original remaining pool. Comparisons are cumulative;
    changed geometry still needs a fresh full proof with only unspent work.
    All work consumes the caller's original
    clocks and remaining pair pool. The invalid parent's length is reported as
    a quality goal; guide-derived straight travel stays bounded. Final physical
    acceptance is strict and independent of the gym stress envelope.
    """
    validate(
        remaining_pairs=remaining_pairs,
        maximum_cpu_seconds=maximum_cpu_seconds,
        maximum_seconds=maximum_seconds,
        maximum_updates=maximum_updates,
        maximum_length_mm=maximum_length_mm,
        minimum_straight_mm=minimum_straight_mm,
    )
    cpu, wall = process_time(), perf_counter()
    detail: dict[str, Any] = {
        "status": "unresolved",
        "purpose": "spatial_deviation",
        "iterations": 0,
        "newton_steps": 0,
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "maximum_length_goal_mm": maximum_length_mm,
        "roots_attempted": 0,
        "maximum_roots": 8,
        "maximum_masks_per_root": 128,
        "closed_roots": 0,
    }
    candidate = original
    contact = None
    accepted = False
    active_pairs = 0
    contact_started = 0.0

    def bounded() -> None:
        """
        Preserve caller hard failures and debit every planning, allocation and certificate operation.
        """
        checkpoint()
        if process_time() - cpu >= maximum_cpu_seconds or perf_counter() - wall >= maximum_seconds:
            raise _Exhausted()

    try:
        bounded()
        evidence = terminal.measure(original, "spatial_deviation_source")
        if evidence.status != "blocked" or evidence.witness is None:
            return None
        proposed = plan(original, evidence, terminal.hardware, bounded)
        if proposed is None:
            return None
        frames = proposed.frames
        guide = frames.guide
        parameters = proposed.parameters
        record(
            {
                "stage": "spatial_deviation",
                "status": "planned",
                "source": snapshot(original),
                "evidence": asdict(evidence),
                "offset_mm": asdict(proposed.offset_mm),
                "parameters": parameters,
                "feature_gap_mm": proposed.source_gap_mm,
                "guide_length_mm": guide.distances[-1],
            }
        )
        allocations: list[Allocation] = []
        boundary = Boundary(original.targets, original.radius_mm)
        attempted = chains(boundary, frames, parameters, bounded, record)
        for chain in attempted:
            detail["roots_attempted"] += 1
            allocation = fit(
                boundary,
                chain,
                minimum_straight_mm,
                bounded,
                record,
                maximum_straight_mm=guide.distances[-1],
            )
            if allocation is not None:
                allocations.append(allocation)
        detail["closed_roots"] = len(allocations)
        detail["exact_closed_roots"] = len(allocations)
        if not allocations and attempted:
            detail["iterations"] = 1

            def record_closure(event: dict[str, Any]) -> None:
                """
                Charge every accepted angular correction before forwarding the original evidence.
                """
                if (
                    event.get("stage") == "feature_reclosure"
                    and event.get("status") == "residual_reduced"
                ):
                    detail["newton_steps"] += 1
                record(event)

            closed = close_deviation(
                boundary,
                attempted,
                minimum_straight_mm,
                guide.distances[-1],
                bounded,
                record_closure,
            )
            detail["closure_refined"] = closed is not None
            if closed is not None:
                allocations.append(closed)
                detail["closed_roots"] = len(allocations)
        if allocations:
            selected = min(
                allocations, key=lambda a: (a.route.material_length_mm, a.score, a.chain.roots)
            )
            candidate = selected.route
            if (
                candidate.targets != original.targets
                or cap_error(candidate) > 1e-7
                or material_error(candidate) > 1e-10
            ):
                raise ArithmeticError("Spatial deviation lost ordered caps or material geometry")
            bounded()
            active_pairs = min(1024, remaining_pairs)
            detail["contacts"] = 1
            contact_started = perf_counter()
            traversal = (
                ContactTraversal(
                    candidate,
                    maximum_pairs=remaining_pairs,
                    checkpoint=bounded,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    projection_reuse=ProjectionReuse.CELLS,
                )
                if remaining_pairs > active_pairs
                else None
            )
            contact = (
                traversal.advance(active_pairs)
                if traversal is not None
                else inspect_contact(
                    candidate,
                    maximum_pairs=active_pairs,
                    checkpoint=bounded,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    projection_reuse=ProjectionReuse.CELLS,
                )
            )
            detail["contact_seconds"] = perf_counter() - contact_started
            detail["contact_pairs"] = contact.pairs_checked
            active_pairs = 0
            record(
                {
                    "stage": "spatial_deviation",
                    "status": "contact",
                    "contact": asdict(contact),
                    "route": snapshot(candidate),
                }
            )
            if contact.limit == "pairs" and traversal is not None:
                bounded()
                active_pairs = remaining_pairs - detail["contact_pairs"]
                contact_started = perf_counter()
                contact = traversal.advance(remaining_pairs)
                detail["contact_seconds"] += perf_counter() - contact_started
                detail["contact_pairs"] = contact.pairs_checked
                detail["contact_resumptions"] = 1
                active_pairs = 0
                record(
                    {
                        "stage": "spatial_deviation",
                        "status": "contact_resumed",
                        "contact": asdict(contact),
                        "pair_ceiling": remaining_pairs,
                    }
                )
            if contact.status == "separated":
                report = terminal.certify(candidate, "spatial_deviation_final")
                bounded()
                accepted = report.status == "clear"
                detail["stop_reason"] = "accepted" if accepted else "hardware_not_clear"
            if not accepted:
                if contact.status != "separated":
                    detail["stop_reason"] = "contact_not_separated"
                left = Work(
                    maximum_updates, remaining_pairs, maximum_cpu_seconds, maximum_seconds
                ).remaining(
                    updates=detail["iterations"],
                    pairs=detail["contact_pairs"],
                    cpu_seconds=process_time() - cpu,
                    wall_seconds=perf_counter() - wall,
                )
                if left is not None:
                    refined = refine(
                        candidate,
                        contact,
                        terminal,
                        checkpoint,
                        record,
                        work=left,
                        maximum_length_mm=maximum_length_mm,
                        minimum_straight_mm=minimum_straight_mm,
                    )
                    if refined is not None:
                        detail["refinement"] = refined.detail
                        for name in (
                            "iterations",
                            "newton_steps",
                            "contacts",
                            "contact_pairs",
                            "contact_seconds",
                        ):
                            detail[name] += refined.detail.get(name, 0)
                        bounded()
                        if refined.contact is not None and refined.detail["status"] == "separated":
                            candidate, contact, accepted = refined.route, refined.contact, True
                            detail["stop_reason"] = "accepted_after_coupled_refinement"
        else:
            detail["stop_reason"] = "no_exact_deviation_allocation"
    except _Exhausted:
        detail["stop_reason"] = "phase_budget"
        if active_pairs:
            detail["contact_pairs"] += active_pairs
            detail["contact_seconds"] += perf_counter() - contact_started
            detail["interrupted_pairs_charged_as_upper_bound"] = active_pairs
    detail.update(
        status="separated" if accepted else "unresolved",
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
        length_mm=candidate.material_length_mm,
        length_goal_excess_mm=max(0.0, candidate.material_length_mm - maximum_length_mm),
    )
    record(
        {
            "stage": "spatial_deviation",
            "status": detail["status"],
            "detail": detail,
            "candidate": snapshot(candidate),
        }
    )
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    if accepted and (
        detail["cpu_seconds"] >= maximum_cpu_seconds or detail["elapsed_seconds"] >= maximum_seconds
    ):
        accepted = False
        detail.update(status="unresolved", stop_reason="phase_budget")
        record({"stage": "spatial_deviation", "status": "unresolved", "detail": detail})
    return Result(candidate if accepted else original, contact if accepted else None, detail)
