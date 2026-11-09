"""
Spend remaining construction work on measured failures that dominate a poor safe fallback.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.attached_regions import RegionPolicy
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
    BaselinePolicy,
    InitialPolicy,
    recover,
)
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, Policy, improves
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, Result
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_fold_route.contact_core import core_witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate

from .fallback_feasibility import before_optional_motion
from .recovery_queue import recover_failed


def recover_construction(
    result: Result,
    frames: Frames,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    selection_policy: Policy,
    terminal: Gate | None = None,
) -> tuple[Result, dict[str, Any] | None]:
    """
    Correct existing failed branches without losing an already separated baseline.

    Unaccepted constructions select by their initial bounded separation correction,
    yielding unused updates to the next branch only after a different pair collides.
    Accepted-fallback recovery may group a colliding fold with a confirmed crossing
    attached straight only if that complete correction fits one original trust step;
    otherwise preserve the original witness correction.
    Accepted-fallback recovery uses the existing analytic full-cap support proof
    to reduce certificate work within the same allowance.
    Pair-limited straight evidence may be strengthened only by a verified common
    interior point in the existing material cores; a missed witness stays unresolved.
    With monotonic optimization enabled, a separated fallback also permits recovery
    of one measured penetration that is shorter and no worse on both whole-guide
    measures. Recovered geometry must satisfy those preferences again before use.
    An accepted fallback's first correction may defer without motion when its
    trust demand exceeds four updates, retaining preparation cost for the caller's
    optional contraction recovery. Other recovery policies retain their behavior.
    If actual fallback hardware eligibility is blocked, a supported first-motion
    action may instead couple the selected shorter branch's physical constraints.
    It runs after overflow deferral, retains every original work debit and must
    satisfy the same guide/shortening selection before replacing the fallback.
    A witnessed mating-runway crossing may instead carry explicit blocked-baseline
    restoration policy after coupled self/hardware certification. That policy
    retains the baseline length ceiling but permits a guide tradeoff to recover
    physical feasibility. Explicit released-quality restoration may exceed that
    blocked baseline's length after its constrained projection failed; every
    physical certificate remains required. Report restoration separately from guide improvement;
    internal crossings and the existing paired-fold policy remain unchanged.
    No new roots or pair allowance are added: recovery shares the original2048pool
    and caller's four-second deadline, with its existing four-update/.35CPU cap.
    Unsupported failures, exhausted work and unsuccessful improvement retain the
    baseline. Caller errors propagate; actual spent work is counted even if rejected.
    """
    if not result.rejected or result.contact_pairs >= CONTACT_PAIR_BUDGET:
        return result, None
    baseline = None
    candidates = result.rejected
    started, cpu = perf_counter(), process_time()
    if result.route is not None:
        if (
            selection_policy is not Policy.MONOTONIC
            or result.contact is None
            or result.contact.status != "separated"
        ):
            return result, None
        baseline = Branch.measure((), result.route, frames.guide)
        strengthened = []
        for branch, measurement in candidates:
            checkpoint()
            pair = measurement.unresolved_pieces
            if measurement.status == "unresolved" and measurement.limit == "pairs" and pair:
                witness = core_witness(branch.route, *pair)
                if witness is not None:
                    measurement = replace(
                        measurement,
                        status="penetration",
                        witness=witness,
                        unresolved_pieces=None,
                        unresolved_regions=None,
                        limit=None,
                        reason="Confirmed straight material-core intersection replaces pair-limited evidence.",
                    )
                    record(
                        {
                            "stage": "recovery_contact_evidence",
                            "status": "confirmed_straight_core",
                            "roots": branch.roots,
                            "witness": asdict(witness),
                        }
                    )
            strengthened.append((branch, measurement))
        candidates = tuple(
            (branch, measurement)
            for branch, measurement in strengthened
            if measurement.status == "penetration"
            and measurement.witness is not None
            and improves(branch, baseline)
        )
        if not candidates:
            return result, None
    fallback_branch: Branch | None = None
    if baseline is None:
        recovery = recover_failed(
            candidates,
            CONTACT_PAIR_BUDGET - result.contact_pairs,
            threshold_mm,
            checkpoint,
            record,
        )
    else:
        cpu_left = MAXIMUM_CPU_SECONDS - (process_time() - cpu)
        wall_left = MAXIMUM_WALL_SECONDS - (perf_counter() - started)
        if cpu_left <= 0 or wall_left <= 0:
            return result, None
        branch, measurement = min(candidates, key=lambda item: item[0].priority)
        fallback_branch = branch
        record(
            {
                "stage": "fallback_branch_recovery",
                "status": "started",
                "roots": branch.roots,
                "baseline_length_mm": baseline.route.material_length_mm,
                "source_length_mm": branch.route.material_length_mm,
                "remaining_pair_budget": CONTACT_PAIR_BUDGET - result.contact_pairs,
            }
        )
        recovery = recover(
            branch.route,
            measurement,
            CONTACT_PAIR_BUDGET - result.contact_pairs,
            threshold_mm,
            checkpoint,
            record,
            region_policy=RegionPolicy.ATTACHED_STRAIGHTS,
            cap_policy=CapPolicy.ANALYTIC_SUPPORT,
            maximum_cpu_seconds=cpu_left,
            maximum_seconds=wall_left,
            initial_policy=InitialPolicy.DEFER_OVERFLOW,
            before_first_motion=before_optional_motion(
                baseline.route,
                branch.route,
                measurement,
                terminal,
                threshold_mm,
                checkpoint,
                record,
            ),
        )
    selected = recovery.route
    if selected is not None and (
        recovery.contact is None or recovery.contact.status != "separated"
    ):
        raise ArithmeticError("Recovered construction lacks a separated contact certificate")
    detail = dict(recovery.detail)
    if baseline is not None:
        assert fallback_branch is not None
        guide_improvement = False
        restoring = recovery.baseline_policy in (
            BaselinePolicy.RESTORE_BLOCKED,
            BaselinePolicy.RESTORE_BLOCKED_GOAL,
        )
        if selected is not None:
            candidate = Branch.measure(fallback_branch.roots, selected, frames.guide)
            guide_improvement = improves(candidate, baseline)
            if recovery.baseline_policy is BaselinePolicy.RESTORE_BLOCKED:
                permitted = selected.material_length_mm <= baseline.route.material_length_mm
            elif recovery.baseline_policy is BaselinePolicy.RESTORE_BLOCKED_GOAL:
                permitted = True
            else:
                permitted = guide_improvement
            if not permitted:
                selected = None
        detail.update(
            purpose="restore_blocked_fallback" if restoring else "improve_separated_fallback",
            roots=fallback_branch.roots,
            baseline_length_mm=baseline.route.material_length_mm,
            accepted_improvement=selected is not None and guide_improvement,
            cap_support_policy=CapPolicy.ANALYTIC_SUPPORT.value,
            cpu_seconds=process_time() - cpu,
            elapsed_seconds=perf_counter() - started,
        )
        if restoring:
            detail["accepted_feasibility_restoration"] = selected is not None
        record(
            {
                "stage": "fallback_branch_recovery",
                "status": "restored"
                if selected is not None and restoring
                else "improved"
                if selected is not None
                else "baseline_retained",
                "detail": detail,
            }
        )
    updated = replace(
        result,
        route=selected if selected is not None else result.route,
        allocation=None if selected is not None else result.allocation,
        status="separated" if selected is not None else result.status,
        contact=recovery.contact if selected is not None else result.contact,
        contacts=result.contacts + recovery.contacts,
        contact_pairs=result.contact_pairs + recovery.pairs,
        contact_seconds=result.contact_seconds + recovery.contact_seconds,
    )
    return updated, detail
