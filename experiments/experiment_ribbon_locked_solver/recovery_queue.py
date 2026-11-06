"""
Share one recovery allowance across derived branches when a correction exposes another collision.
"""

from __future__ import annotations

from time import perf_counter, process_time
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    MAXIMUM_CPU_SECONDS,
    MAXIMUM_WALL_SECONDS,
    ContactContinuation,
    Recovery,
    recover,
)
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy

from .recovery_selection import select_recovery


def recover_failed(
    candidates: tuple[tuple[Branch, ContactResult], ...],
    remaining_pairs: int,
    threshold_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Recovery:
    """
    Spend at most four total updates,.35CPU/2wall and the original remaining pair pool.

    Preserve prediction order. Only a different penetrating material feature
    permits handing unused updates to the next already-derived branch. A fold
    and its attached straight retain the correction against the same opposing
    region. Do
    not retry a branch, extend exhausted work or install a partially corrected
    collision. The last branch follows the original local contact policy.
    Selection and handoff overhead count toward the same time allowance.
    Reuse each exact source/witness prediction on its first update only.
    Use the same existing analytic cap support proof as v2 construction and
    accepted-fallback recovery, without exempting adjacent material interiors.
    """
    started, cpu = perf_counter(), process_time()
    selection = select_recovery(candidates, checkpoint, record)
    choices = (selection.choice, *selection.alternatives) if selection.choice else ()
    selected, certificate = None, None
    pairs, contacts, updates, contact_seconds = 0, 0, 0, 0.0
    attempts: list[dict[str, Any]] = []
    stop = selection.detail["status"]
    for index, (branch, measurement) in enumerate(choices):
        checkpoint()
        cpu_left = MAXIMUM_CPU_SECONDS - (process_time() - cpu)
        wall_left = MAXIMUM_WALL_SECONDS - (perf_counter() - started)
        if cpu_left <= 0 or wall_left <= 0:
            stop = "local_budget"
            break
        if updates >= 4 or pairs >= remaining_pairs:
            stop = "update_budget" if updates >= 4 else "pair_budget"
            break
        has_next = index + 1 < len(choices)
        record(
            {
                "stage": "recovery_branch",
                "status": "started",
                "roots": branch.roots,
                "remaining_updates": 4 - updates,
                "remaining_pair_budget": remaining_pairs - pairs,
            }
        )
        result = recover(
            branch.route,
            measurement,
            remaining_pairs - pairs,
            threshold_mm,
            checkpoint,
            record,
            maximum_cpu_seconds=cpu_left,
            maximum_seconds=wall_left,
            maximum_updates=4 - updates,
            continuation=(
                ContactContinuation.YIELD_ON_NEW_FEATURE if has_next else ContactContinuation.FOLLOW
            ),
            initial_step=next(
                (
                    planned
                    for planned in selection.initial_steps
                    if planned.source is branch.route and planned.measurement is measurement
                ),
                None,
            ),
            cap_policy=CapPolicy.ANALYTIC_SUPPORT,
        )
        pairs += result.pairs
        contacts += result.contacts
        updates += result.detail["iterations"]
        contact_seconds += result.contact_seconds
        attempts.append({"roots": branch.roots, **result.detail})
        if result.route is not None:
            selected, certificate = result.route, result.contact
            stop = "separated"
            break
        stop = result.detail.get("stop_reason", "update_budget")
        if stop != "different_contact_pair":
            break
    detail = {
        "status": "separated" if selected is not None else "unresolved",
        "iterations": updates,
        "contacts": contacts,
        "pairs": pairs,
        "remaining_pair_budget": remaining_pairs - pairs,
        "cpu_seconds": process_time() - cpu,
        "elapsed_seconds": perf_counter() - started,
        "selection": selection.detail,
        "attempts": attempts,
        "cap_support_policy": CapPolicy.ANALYTIC_SUPPORT.value,
    }
    if selected is None:
        detail["stop_reason"] = stop
    record({"stage": "branch_recovery_complete", **detail})
    return Recovery(selected, certificate, pairs, contacts, contact_seconds, detail)
