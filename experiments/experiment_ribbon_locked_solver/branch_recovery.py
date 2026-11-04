"""
Spend remaining construction work on measured failures that dominate a poor safe fallback.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.attached_regions import RegionPolicy
from experiments.experiment_ribbon_feature_insertion.contact_recovery import recover
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, Policy, improves
from experiments.experiment_ribbon_feature_insertion.solve import CONTACT_PAIR_BUDGET, Result

from .recovery_queue import recover_failed


def recover_construction(
    result: Result,
    frames: Frames,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    selection_policy: Policy,
) -> tuple[Result, dict[str, Any] | None]:
    """
    Correct existing failed branches without losing an already separated baseline.

    Unaccepted constructions select by their initial bounded separation correction,
    yielding unused updates to the next branch only after a different pair collides.
    Accepted-fallback recovery may group a colliding fold with a confirmed crossing
    attached straight only if that complete correction fits one original trust step;
    otherwise preserve the original witness correction.
    With monotonic optimization enabled, a separated fallback also permits recovery
    of one measured penetration that is shorter and no worse on both whole-guide
    measures. Recovered geometry must satisfy those preferences again before use.
    No new roots or pair allowance are added: recovery shares the original2048pool
    and caller's four-second deadline, with its existing four-update/.35CPU cap.
    Unsupported failures, exhausted work and unsuccessful improvement retain the
    baseline. Caller errors propagate; actual spent work is counted even if rejected.
    """
    if not result.rejected or result.contact_pairs >= CONTACT_PAIR_BUDGET:
        return result, None
    baseline = None
    candidates = result.rejected
    if result.route is not None:
        if (
            selection_policy is not Policy.MONOTONIC
            or result.contact is None
            or result.contact.status != "separated"
        ):
            return result, None
        baseline = Branch.measure((), result.route, frames.guide)
        candidates = tuple(
            (branch, measurement)
            for branch, measurement in candidates
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
        )
    selected = recovery.route
    if selected is not None and (
        recovery.contact is None or recovery.contact.status != "separated"
    ):
        raise ArithmeticError("Recovered construction lacks a separated contact certificate")
    detail = dict(recovery.detail)
    if baseline is not None:
        assert fallback_branch is not None
        if selected is not None:
            candidate = Branch.measure(fallback_branch.roots, selected, frames.guide)
            if not improves(candidate, baseline):
                selected = None
        detail.update(
            purpose="improve_separated_fallback",
            roots=fallback_branch.roots,
            baseline_length_mm=baseline.route.material_length_mm,
            accepted_improvement=selected is not None,
        )
        record(
            {
                "stage": "fallback_branch_recovery",
                "status": "improved" if selected is not None else "baseline_retained",
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
