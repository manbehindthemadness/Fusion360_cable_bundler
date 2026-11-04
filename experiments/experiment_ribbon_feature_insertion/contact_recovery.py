"""
Recover one rejected closed plan through bounded joint separation without accepting its baseline.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import MovableBends, retract_active
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight

from .separation import Separation, Side, TopologyChanged
from .separation_step import InitialStep, plan_step

MAXIMUM_CPU_SECONDS = 0.35
MAXIMUM_WALL_SECONDS = 2.0


class ContactContinuation(Enum):
    """
    Keep following contact locally or yield unused work when a different material pair collides.
    """

    FOLLOW = "follow"
    YIELD_ON_NEW_PAIR = "yield_on_new_pair"


class _Exhausted(RuntimeError):
    """
    Stop optional local work without catching caller resource or source errors.
    """


@dataclass(frozen=True)
class Recovery:
    """
    Return only a newly separated route, with all recovery work accounted separately.
    """

    route: FoldRoute | None
    contact: ContactResult | None
    pairs: int
    contacts: int
    contact_seconds: float
    detail: dict[str, Any]


def recover(
    source: FoldRoute,
    measurement: ContactResult,
    remaining_pairs: int,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_cpu_seconds: float = MAXIMUM_CPU_SECONDS,
    maximum_seconds: float = MAXIMUM_WALL_SECONDS,
    maximum_updates: int = 4,
    continuation: ContactContinuation = ContactContinuation.FOLLOW,
    initial_step: InitialStep | None = None,
) -> Recovery:
    """
    Apply at most four gap-increasing joint updates and strict contact certificates.

    Keep radii, profile, fold count/order and both caps. Use a minimum-norm
    linearized separation constraint, bounded joint steps and existing nonlinear
    cap retraction. Local limits are0.35CPU/2wall seconds, subordinate to caller
    limits. Callers may reserve part of those allowances for selection; explicit
    sublimits may only reduce the defaults. Never return the rejected source as
    an accepted fallback. Pair/depth
    ambiguity and failed improvement remain unresolved; caller hard errors propagate.
    A scheduler can reserve updates and request a yield after a different stable
    material pair penetrates. This returns no accepted geometry or certificate.
    A cached first motion requires the identical immutable source and measurement;
    subsequent updates always recompute their derivatives on the changed geometry.
    """
    if type(remaining_pairs) is not int or not 0 < remaining_pairs <= 2048:
        raise ValueError("Supply positive remaining first-pass work, at most2048pairs")
    if not math.isfinite(threshold_mm) or threshold_mm <= 0:
        raise ValueError("A positive native straight threshold is required")
    if type(maximum_updates) is not int or not 1 <= maximum_updates <= 4:
        raise ValueError("Recovery sublimits require one to four updates")
    if not isinstance(continuation, ContactContinuation):
        raise ValueError("Supply an explicit contact continuation policy")
    if initial_step is not None and (
        initial_step.source is not source or initial_step.measurement is not measurement
    ):
        raise ValueError("A cached first step requires the identical source and measurement")
    for allowance, ceiling in (
        (maximum_cpu_seconds, MAXIMUM_CPU_SECONDS),
        (maximum_seconds, MAXIMUM_WALL_SECONDS),
    ):
        if (
            type(allowance) not in (int, float)
            or not math.isfinite(allowance)
            or not 0 < allowance <= ceiling
        ):
            raise ValueError("Recovery sublimits must be positive and within original ceilings")
    started, cpu = perf_counter(), process_time()
    model = MovableBends(source)
    values, route = model.initial, source
    bound: Separation | None = None
    side: Side | None = None
    selected = None
    accepted = None
    spent, contacts, contact_seconds = 0, 0, 0.0
    detail: dict[str, Any] = {"status": "unresolved", "iterations": 0}

    def bounded() -> None:
        """
        Preserve caller hard gates and distinguish exhaustion of this optional operation.
        """
        checkpoint()
        if (
            process_time() - cpu >= maximum_cpu_seconds
            or perf_counter() - started >= maximum_seconds
        ):
            raise _Exhausted("Joint separation recovery exhausted its local allowance")

    try:
        for iteration in range(maximum_updates):
            bounded()
            detail["iterations"] += 1
            if bound is None:
                bound = Separation.from_measurement(model, route, measurement)
                if bound is None:
                    detail["stop_reason"] = "no_supported_contact_region"
                    break
            assert bound is not None
            planned = (
                initial_step.step
                if iteration == 0 and initial_step is not None
                else plan_step(model, values, bound, side, bounded)
            )
            if planned is None:
                detail["stop_reason"] = "no_projected_separation"
                break
            chosen_side, gap, delta = planned.side, planned.gap, planned.delta
            side = chosen_side
            step = planned.fraction
            changed = None
            for _ in range(2):
                bounded()
                candidate = retract_active(model, advance(model, values, delta, step), bounded)
                if candidate is not None and bound.gap(candidate, chosen_side) > gap:
                    changed = candidate
                    break
                step /= 2
            if changed is None:
                detail["stop_reason"] = "no_gap_improvement"
                break
            values = changed
            route = FoldRoute(source.targets, model.pieces(values), source.radius_mm)
            if cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                raise ArithmeticError("Joint recovery lost its exact cap/material contract")
            gap_mm = bound.gap(values, chosen_side) * model.scale
            record(
                {
                    "stage": "joint_separation_recovery",
                    "status": "gap_improved",
                    "iteration": iteration,
                    "gap_mm": gap_mm,
                    "route": snapshot(route),
                }
            )
            if gap_mm <= 0:
                continue
            if any(
                isinstance(p.geometry, Straight) and p.geometry.material_length_mm <= threshold_mm
                for p in route.pieces
            ):
                detail["stop_reason"] = "sub_tolerance_straight"
                break
            allowance = min(1024, remaining_pairs - spent)
            if allowance <= 0:
                detail["stop_reason"] = "pair_budget"
                break
            now = perf_counter()
            measurement = inspect_contact(route, maximum_pairs=allowance, checkpoint=bounded)
            if (
                type(measurement.pairs_checked) is not int
                or not 0 <= measurement.pairs_checked <= allowance
            ):
                raise ArithmeticError("Recovery contact exceeded its pair allowance")
            contact_seconds += perf_counter() - now
            contacts += 1
            spent += measurement.pairs_checked
            record(
                {
                    "stage": "joint_separation_recovery",
                    "status": measurement.status,
                    "iteration": iteration,
                    "contact": asdict(measurement),
                    "remaining_pair_budget": remaining_pairs - spent,
                    "route": snapshot(route),
                }
            )
            if measurement.status == "separated":
                selected, accepted = route, measurement
                detail["status"] = "separated"
                break
            if (
                continuation is ContactContinuation.YIELD_ON_NEW_PAIR
                and measurement.status == "penetration"
            ):
                next_bound = Separation.from_measurement(model, route, measurement)
                if next_bound is not None and next_bound.pair != bound.pair:
                    detail["stop_reason"] = "different_contact_pair"
                    break
            bound, side = None, None
    except _Exhausted:
        detail["stop_reason"] = "local_budget"
    except TopologyChanged:
        detail["stop_reason"] = "fold_topology_changed"
    detail.update(
        cpu_seconds=process_time() - cpu,
        elapsed_seconds=perf_counter() - started,
        contacts=contacts,
        pairs=spent,
        remaining_pair_budget=remaining_pairs - spent,
    )
    record({"stage": "joint_separation_recovery", "status": detail["status"], "detail": detail})
    return Recovery(selected, accepted, spent, contacts, contact_seconds, detail)
