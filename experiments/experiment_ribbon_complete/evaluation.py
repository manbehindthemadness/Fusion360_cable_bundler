"""
Evaluate complete gym inputs without turning trunk acceptance or missing audits into success.

This numerical entry point accepts an explicitly selected trunk constructor.
It neither installs a gym UI nor authorizes native construction or a work pool.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter, process_time
from typing import Any, Literal

from .execution import RibbonPlan, RibbonTargets, TrunkConstructor, prepare
from .material_witnesses import CompletePathWitness, CompleteWitnessAudit, WitnessWork, audit
from .profile_transition import TransitionTiming


def witness_finding(row: CompletePathWitness) -> dict[str, Any]:
    """
    Serialize the complete source-labelled rejection receipt for either audit ordering.
    """
    return {
        "pin": row.conductor.pin_number,
        "side": row.side,
        "lower_mm": str(row.lower_mm),
        "violation": row.violation,
        "first_terminal": str(row.first_terminal),
        "last_terminal": str(row.last_terminal),
        "first_route_ids": [str(value) for value in row.first_route_ids],
        "last_route_ids": [str(value) for value in row.last_route_ids],
    }


@dataclass(frozen=True)
class CompleteEvaluation:
    """
    Retain complete geometry and planned rejection evidence with qualification still explicit.
    """

    plan: RibbonPlan
    material: CompleteWitnessAudit | None
    status: Literal["trunk_unresolved", "planned_material_violation", "unqualified"]
    audit_wall_seconds: float
    audit_cpu_seconds: float
    outstanding: tuple[str, ...]


def evaluate(
    source: RibbonTargets,
    trunk_constructor: TrunkConstructor,
    work: WitnessWork,
    intervals_per_span: int,
    record: Callable[[dict[str, Any]], None],
    *,
    timing: TransitionTiming = TransitionTiming.QUINTIC,
) -> CompleteEvaluation:
    """
    Freeze all inputs before one trunk call, then check both complete ending chains.

    The caller's checkpoint covers preparation and measurement. The witness count
    is shared, never renewed internally. A witnessed planned violation rejects;
    absence of a witness retains all material/native/physical qualifications.
    Resource, cancellation, provenance and programming errors propagate rather
    than becoming physical outcomes. No failure causes a retry or a native call.
    """
    if type(intervals_per_span) is not int or not 1 <= intervals_per_span <= 64:
        raise ValueError("Freeze1..64intervals per original span before evaluation")
    plan = prepare(source, trunk_constructor, work.checkpoint, record, timing=timing)
    if plan.trunk.route is None:
        return CompleteEvaluation(plan, None, "trunk_unresolved", 0, 0, ("complete_geometry",))
    wall, cpu = perf_counter(), process_time()
    measured = audit(plan, intervals_per_span, work)
    audit_wall, audit_cpu = perf_counter() - wall, process_time() - cpu
    status = "planned_material_violation" if measured.status == "violated" else "unqualified"
    outstanding = tuple(
        dict.fromkeys(
            (
                "trunk_material_metrics",
                "junction_material_correspondence",
                "native_material_correspondence",
            )
            + tuple(gate for branch in plan.branches for gate in branch.outstanding)
        )
    )
    record(
        {
            "stage": "complete_material_witness",
            "status": status,
            "scope": "planned source-labelled absolute increment discrepancy; not native or full physical qualification",
            "witness_calls": work.calls,
            "findings": [witness_finding(row) for row in measured.findings],
            "outstanding": outstanding,
        }
    )
    return CompleteEvaluation(plan, measured, status, audit_wall, audit_cpu, outstanding)
