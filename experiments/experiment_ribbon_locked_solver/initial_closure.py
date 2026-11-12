"""
Connect an actual missing construction direction to the existing bounded physical recovery.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
from experiments.experiment_ribbon_feature_insertion.selection import Policy
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, Result
from experiments.experiment_ribbon_fold_route.contact import ProjectionReuse, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_affine_witness import AffineWitnesses
from experiments.experiment_ribbon_fold_route.contact_axes import (
    AxisContinuation,
    AxisLearning,
    ProposedAxes,
)
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_subdivision import Subdivision
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.cone_escape import construct, plan
from experiments.experiment_ribbon_terminal_hardware.deviation_sequence import (
    recover as continue_route,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work


class _Exhausted(RuntimeError):
    """
    End only this initial-construction allocation, preserving caller failures.
    """


def recover(
    result: Result,
    boundary: Boundary,
    terminal: Gate | None,
    threshold_mm: float,
    maximum_straight_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    selection_policy: Policy,
) -> tuple[Result, dict[str, Any] | None]:
    """
    Spend one original recovery allocation on a measured initial cone miss.

    Existing accepted, physically rejected and deferred constructions never enter.
    One added direction and its exact compensations use one logical update and
    at most four angular corrections. Only the genuine remainder reaches the
    existing physical sequence, with the same hardware gate and pair pool.
    No alternate construction follows decline. Every candidate is retained as
    inspection evidence before physical checks; evidence alone cannot be output.
    Interrupted initial contact charges its allowance as an explicit upper bound.
    """
    if (
        terminal is None
        or selection_policy is not Policy.MONOTONIC
        or result.route is not None
        or result.inspection_route is not None
        or result.status != "no_fixed_radius_closure"
        or result.closed_branches != 0
        or result.rejected
        or result.deferred
        or not result.closure_candidates
        or result.contact_pairs >= CONTACT_PAIR_BUDGET
    ):
        return result, None
    if terminal.hardware.targets != boundary.targets:
        raise ValueError("Initial closure must retain the caller's fixed boundary")
    limit = ClosureGoal.MATING.normalized_limit(boundary.targets.diameter_mm)
    if any(candidate.closure.error <= limit for candidate in result.closure_candidates):
        return result, None
    cpu, wall = process_time(), perf_counter()
    work = Work(4, CONTACT_PAIR_BUDGET - result.contact_pairs, 0.35, 2.0)
    roots = Roots()
    detail: dict[str, Any] = {
        "status": "unresolved",
        "purpose": "initial_closure_cone_escape",
        "iterations": 0,
        "newton_steps": 0,
        "newton_steps_scope": "whole_recovery",
        "contacts": 0,
        "contact_pairs": 0,
        "contact_seconds": 0.0,
        "stop_reason": "unsupported_missing_direction",
    }
    candidate = None
    accepted = None
    contact = None

    def bounded() -> None:
        """
        Preserve source/cancellation failures and include all preparation in one phase clock.
        """
        checkpoint()
        if process_time() - cpu >= work.cpu_seconds or perf_counter() - wall >= work.wall_seconds:
            raise _Exhausted("Initial closure recovery exhausted its original phase")

    try:
        source = min(
            result.closure_candidates, key=lambda item: (item.closure.error, item.chain.roots)
        )
        escape = plan(boundary, source, bounded)
        if escape is not None:
            detail["iterations"] = 1
            candidate = construct(escape, threshold_mm, maximum_straight_mm, roots, bounded, record)
            detail["stop_reason"] = "closure_declined"
        if candidate is not None:
            record(
                {
                    "stage": "initial_closure_recovery",
                    "status": "candidate",
                    "route": snapshot(candidate),
                }
            )
            bounded()
            allowance = min(1024, work.pairs)
            contact_started = perf_counter()
            detail["contacts"] += 1
            try:
                contact = inspect_contact(
                    candidate,
                    maximum_pairs=allowance,
                    checkpoint=bounded,
                    cap_policy=CapPolicy.ANALYTIC_SUPPORT,
                    projection_reuse=ProjectionReuse.CELLS,
                    proposed_axes=ProposedAxes(
                        AxisContinuation.MATERIAL_CELLS, learning=AxisLearning.LOCAL_SEPARATIONS
                    ),
                    affine_witnesses=AffineWitnesses(),
                    subdivision=Subdivision.MATERIAL_PHASES,
                )
            except _Exhausted:
                detail["contact_pairs"] += allowance
                detail["interrupted_pair_charge"] = "allowance_upper_bound"
                raise
            finally:
                detail["contact_seconds"] += perf_counter() - contact_started
            if (
                type(contact.pairs_checked) is not int
                or not 0 <= contact.pairs_checked <= allowance
            ):
                raise ArithmeticError("Initial contact exceeded its declared allowance")
            detail["contact_pairs"] += contact.pairs_checked
            record(
                {
                    "stage": "initial_closure_recovery",
                    "status": "contact",
                    "contact": asdict(contact),
                }
            )
            bounded()
            if (
                contact.status == "separated"
                and terminal.certify(candidate, "initial_closure_final").status == "clear"
            ):
                accepted = candidate
            else:
                left = work.remaining(
                    updates=detail["iterations"],
                    pairs=detail["contact_pairs"],
                    cpu_seconds=process_time() - cpu,
                    wall_seconds=perf_counter() - wall,
                    newton_steps=roots.newton_steps,
                )
                detail["stop_reason"] = "work_exhausted"
                if left is not None:
                    child = continue_route(
                        candidate,
                        contact,
                        terminal,
                        checkpoint,
                        record,
                        work=left,
                        maximum_length_mm=candidate.material_length_mm,
                        minimum_straight_mm=threshold_mm,
                    )
                    if any(
                        type(child.detail.get(key)) is not int or child.detail[key] < 0
                        for key in ("iterations", "newton_steps", "contacts", "contact_pairs")
                    ) or (
                        child.detail["iterations"] > left.updates
                        or child.detail["newton_steps"] > left.newton_steps
                        or child.detail["contact_pairs"] > left.pairs
                    ):
                        raise ArithmeticError("Physical sequence exceeded the remaining allocation")
                    detail["sequence"] = child.detail
                    for key in ("iterations", "contacts", "contact_pairs", "contact_seconds"):
                        detail[key] += child.detail[key]
                    detail["newton_steps"] = child.detail["newton_steps"]
                    detail["stop_reason"] = child.detail["stop_reason"]
                    if child.contact is not None and child.contact.status == "separated":
                        candidate, contact = child.route, child.contact
                        if (
                            terminal.certify(candidate, "initial_closure_recovered").status
                            == "clear"
                        ):
                            accepted = candidate
        bounded()
    except _Exhausted:
        accepted = None
        detail["stop_reason"] = "phase_budget"
    detail.update(
        newton_steps=roots.newton_steps + detail["newton_steps"],
        roots_attempted=roots.attempted,
        local_reclosures=roots.reclosures,
        pairs=detail["contact_pairs"],
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - wall,
    )
    if (
        detail["iterations"] > work.updates
        or detail["newton_steps"] > work.newton_steps
        or detail["pairs"] > work.pairs
    ):
        raise ArithmeticError("Initial closure recovery renewed its original allocation")
    if accepted is not None:
        if (
            accepted.targets != boundary.targets
            or not ordered_mating_caps(accepted.pieces, accepted.targets)
            or cap_error(accepted) > 1e-7
            or material_error(accepted) > 1e-10
            or any(
                p.geometry.material_length_mm <= threshold_mm
                for p in accepted.pieces
                if isinstance(p.geometry, Straight)
            )
        ):
            raise ArithmeticError(
                "Initial closure recovery lost fixed caps, material or native sizes"
            )
        detail.update(status="separated", stop_reason="accepted")
    detail.update(cpu_seconds=process_time() - cpu, elapsed_seconds=perf_counter() - wall)
    if detail["cpu_seconds"] >= work.cpu_seconds or detail["elapsed_seconds"] >= work.wall_seconds:
        accepted = None
        detail.update(status="unresolved", stop_reason="phase_budget")
    record({"stage": "initial_closure_recovery", "status": detail["status"], "detail": detail})
    return replace(
        result,
        route=accepted,
        allocation=None,
        contact=contact if accepted is not None else None,
        status="separated" if accepted is not None else result.status,
        closed_branches=1 if candidate is not None else 0,
        inspection_route=candidate,
        contacts=result.contacts + detail["contacts"],
        contact_pairs=result.contact_pairs + detail["contact_pairs"],
        contact_seconds=result.contact_seconds + detail["contact_seconds"],
    ), detail
