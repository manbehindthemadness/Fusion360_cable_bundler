"""
Recover one rejected closed plan through bounded joint separation without accepting its baseline.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from enum import Enum
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_bend_relocation.model import (
    ClosurePolicy,
    MovableBends,
    retract_active,
)
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_relaxation.steps import advance
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work

from .attached_regions import RegionPolicy, continues_feature, with_attached_straights
from .separation import Separation, Side, TopologyChanged, regions
from .separation_step import InitialStep, plan_step

MAXIMUM_CPU_SECONDS = 0.35
MAXIMUM_WALL_SECONDS = 2.0


class ContactContinuation(Enum):
    """
    Keep following contact locally or yield unused work when a different material pair collides.
    """

    FOLLOW = "follow"
    YIELD_ON_NEW_PAIR = "yield_on_new_pair"
    YIELD_ON_NEW_FEATURE = "yield_on_new_feature"


class _Exhausted(RuntimeError):
    """
    Stop optional local work without catching caller resource or source errors.
    """


class InitialPolicy(Enum):
    """
    Follow the original first correction or reserve work when its linear trust demand exceeds the allowance.
    """

    FOLLOW = "follow"
    DEFER_OVERFLOW = "defer_overflow"


class BaselinePolicy(Enum):
    """
    Distinguish guide improvement, length-bounded restoration and explicitly released blocked quality.
    """

    GUIDE_IMPROVEMENT = "guide_improvement"
    RESTORE_BLOCKED = "restore_blocked"
    RESTORE_BLOCKED_GOAL = "restore_blocked_goal"


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
    baseline_policy: BaselinePolicy = BaselinePolicy.GUIDE_IMPROVEMENT


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
    cap_policy: CapPolicy = CapPolicy.MONOTONE,
    region_policy: RegionPolicy = RegionPolicy.WITNESS,
    initial_policy: InitialPolicy = InitialPolicy.FOLLOW,
    before_first_motion: Callable[[Work], Recovery | None] | None = None,
) -> Recovery:
    """
    Apply at most four gap-increasing joint updates and strict contact certificates.

    Keep radii, profile, fold count/order and both caps. Use a minimum-norm
    linearized separation constraint, bounded joint steps and existing nonlinear
    cap retraction with actual ordered mating frames before certification. The
    stronger stopping rule uses the same six Newton steps, not output snapping.
    Local limits are0.35CPU/2wall seconds, subordinate to caller
    limits. Callers may reserve part of those allowances for selection; explicit
    sublimits may only reduce the defaults. Never return the rejected source as
    an accepted fallback. Pair/depth
    ambiguity and failed improvement remain unresolved; caller hard errors propagate.
    A scheduler can reserve updates and request a yield after a different stable
    material pair penetrates. This returns no accepted geometry or certificate.
    Feature-aware yielding may retain a fold-to-attached-straight transition
    against an unchanged opposing region; no other new pair gains that exception.
    A cached first motion requires the identical immutable source and measurement;
    subsequent updates always recompute their derivatives on the changed geometry.
    An optional initial-overflow policy may defer before any motion or certificate
    when the first prediction exceeds the supplied update count. Preparation time
    remains measured; deferral grants no clearance or renewed work allowance.
    A first-motion callback runs only after the existing overflow decision and
    before any motion or certificate. It receives genuinely remaining work and
    may replace this action with a fully accounted recovery. None permits the
    original action and must mean no motion or contact certificate was attempted.
    Callback preparation, including eligibility checks, shares the original
    clocks; returned work cannot exceed the supplied update/pair allocation.
    """
    if type(remaining_pairs) is not int or not 0 < remaining_pairs <= 2048:
        raise ValueError("Supply positive remaining first-pass work, at most2048pairs")
    if not math.isfinite(threshold_mm) or threshold_mm <= 0:
        raise ValueError("A positive native straight threshold is required")
    if type(maximum_updates) is not int or not 1 <= maximum_updates <= 4:
        raise ValueError("Recovery sublimits require one to four updates")
    if not isinstance(continuation, ContactContinuation):
        raise ValueError("Supply an explicit contact continuation policy")
    if not isinstance(cap_policy, CapPolicy):
        raise ValueError("Supply an explicit cap separation policy")
    if not isinstance(region_policy, RegionPolicy):
        raise ValueError("Supply an explicit separation-region policy")
    if not isinstance(initial_policy, InitialPolicy):
        raise ValueError("Supply an explicit initial recovery policy")
    if initial_step is not None and (
        initial_step.source is not source
        or initial_step.measurement is not measurement
        or region_policy is not RegionPolicy.WITNESS
    ):
        raise ValueError(
            "A cached first step requires the identical source and measurement with witness regions"
        )
    if initial_step is not None and initial_step.plane is not None:
        witness = measurement.witness
        if (
            witness is None
            or not all(isinstance(source.pieces[i].geometry, Straight) for i in witness.pieces)
            or initial_step.plane != regions(source)[witness.pieces[0]]
        ):
            raise ValueError("A cached moving plane requires the first confirmed straight sheet")
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
            planned = None
            if bound is None:
                bound = (
                    Separation.from_measurement(model, route, measurement)
                    if iteration == 0
                    else Separation.following_measurement(model, route, measurement)
                )
                if bound is not None and iteration == 0 and initial_step is not None:
                    bound = replace(bound, plane=initial_step.plane)
                if bound is not None and region_policy is RegionPolicy.ATTACHED_STRAIGHTS:
                    expanded = with_attached_straights(bound, route, measurement)
                    if expanded.extra_regions:
                        trial = plan_step(model, values, expanded, None, bounded)
                        fits = trial is not None and trial.fraction == 1.0
                        record(
                            {
                                "stage": "attached_region_selection",
                                "status": "used" if fits else "deferred_to_witness",
                                "fraction": trial.fraction if trial else None,
                                "additional_regions": len(expanded.extra_regions),
                            }
                        )
                        if fits:
                            bound, planned = expanded, trial
                if bound is None:
                    detail["stop_reason"] = "no_supported_contact_region"
                    break
            assert bound is not None
            if planned is None:
                planned = (
                    initial_step.step
                    if iteration == 0 and initial_step is not None
                    else plan_step(model, values, bound, side, bounded)
                )
            if planned is None:
                detail["stop_reason"] = "no_projected_separation"
                break
            if (
                iteration == 0
                and initial_policy is InitialPolicy.DEFER_OVERFLOW
                and planned.fraction < 1 / maximum_updates
            ):
                detail.update(
                    status="deferred",
                    iterations=0,
                    stop_reason="initial_prediction_exceeds_update_budget",
                    initial_fraction=planned.fraction,
                )
                break
            if iteration == 0 and before_first_motion is not None:
                bounded()
                cpu_left = maximum_cpu_seconds - (process_time() - cpu)
                wall_left = maximum_seconds - (perf_counter() - started)
                if cpu_left <= 0 or wall_left <= 0:
                    raise _Exhausted("No first-motion preparation allowance remains")
                replacement = before_first_motion(
                    Work(maximum_updates, remaining_pairs, cpu_left, wall_left)
                )
                if replacement is not None:
                    used = replacement.detail.get("iterations")
                    newton = replacement.detail.get("newton_steps", 0)
                    if (
                        type(used) is not int
                        or not 0 <= used <= maximum_updates
                        or type(newton) is not int
                        or not 0 <= newton <= 6 * maximum_updates
                        or type(replacement.pairs) is not int
                        or not 0 <= replacement.pairs <= remaining_pairs
                    ):
                        raise ArithmeticError("First-motion continuation exceeded its shared work")
                    summary = dict(replacement.detail)
                    summary.update(
                        cpu_seconds=process_time() - cpu,
                        elapsed_seconds=perf_counter() - started,
                        pairs=replacement.pairs,
                    )
                    if (
                        summary["cpu_seconds"] >= maximum_cpu_seconds
                        or summary["elapsed_seconds"] >= maximum_seconds
                    ):
                        summary.update(status="unresolved", stop_reason="local_budget")
                        return replace(replacement, route=None, contact=None, detail=summary)
                    return replace(replacement, detail=summary)
            chosen_side, gap, delta = planned.side, planned.gap, planned.delta
            side = chosen_side
            step = planned.fraction
            changed = None
            for _ in range(2):
                bounded()
                candidate = retract_active(
                    model,
                    advance(model, values, delta, step),
                    bounded,
                    closure_policy=ClosurePolicy.ORDERED_CAPS,
                )
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
            options = {"cap_policy": cap_policy} if cap_policy is not CapPolicy.MONOTONE else {}
            measurement = inspect_contact(
                route, maximum_pairs=allowance, checkpoint=bounded, **options
            )
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
                continuation is not ContactContinuation.FOLLOW
                and measurement.status == "penetration"
            ):
                next_bound = Separation.from_measurement(model, route, measurement)
                if next_bound is not None and next_bound.pair != bound.pair:
                    attached = (
                        continuation is ContactContinuation.YIELD_ON_NEW_FEATURE
                        and continues_feature(bound.pair, next_bound.pair)
                    )
                    if not attached:
                        detail["stop_reason"] = "different_contact_pair"
                        break
                    record(
                        {
                            "stage": "contact_feature_continuation",
                            "status": "attached_straight",
                            "before": tuple(asdict(region) for region in bound.pair),
                            "after": tuple(asdict(region) for region in next_bound.pair),
                        }
                    )
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
