"""
Select a guide-ranked branch within fixed contact budgets and preserve a safe baseline.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_radius_allocation.solve import Trial
from experiments.experiment_ribbon_radius_allocation.solve import solve as allocate

from .branches import branches
from .guide import Guide, agreement


def solve(
    source: FoldRoute,
    baseline: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, dict[str, Any]]:
    """
    Check at most four ranked branches, then one existing bounded radius allocation.

    The input baseline must already be accepted. Full contact remains authoritative;
    failures and skipped branches remain explicit. A new result must improve guide
    RMS, preserve or reduce fold count and not increase the latest baseline length.
    Otherwise retain that baseline. This is a deterministic bounded comparison,
    not proof of shortest routing or successful guide following for arbitrary caps.
    """
    if source.targets != baseline.targets:
        raise ValueError("Both baseline and construction must use identical ordered targets.")
    options = branches(source, guide, checkpoint, record)
    ledger: list[dict[str, Any]] = []
    selected = None
    tested = 0
    for branch in options:
        row: dict[str, Any] = {
            "id": branch.identifier,
            "agreement": asdict(branch.agreement),
            "folds": fold_count(branch.route),
            "length_mm": branch.route.material_length_mm,
            "rewrites_evaluated": branch.rewrites_evaluated,
            "route": snapshot(branch.route),
        }
        ledger.append(row)
        if selected is not None or tested >= 4:
            row["status"] = (
                "unattempted_after_selection" if selected else "contact_budget_unattempted"
            )
            continue
        checkpoint()
        contact = inspect_contact(branch.route, checkpoint=checkpoint)
        tested += 1
        row.update(status=contact.status, contact=asdict(contact))
        record({"stage": "branch_contact", **row})
        if contact.status == "separated":
            selected = branch
    details: dict[str, Any] = {"branches": ledger, "contact_attempts": tested}
    if selected is None:
        details["reason"] = "no_separated_branch_within_budget"
        return baseline, details

    def record_allocation(trial: Trial) -> None:
        """
        Preserve every radius fraction and full material route before proceeding.
        """
        record(
            {
                "stage": "radius_allocation",
                "fraction": trial.fraction,
                "contact": asdict(trial.contact),
                "route": snapshot(trial.route),
            }
        )

    candidate, optimum, fraction, reason = allocate(
        selected.route, checkpoint=checkpoint, record=record_allocation
    )
    score = agreement(candidate, guide)
    old_score = agreement(baseline, guide)
    details.update(
        selected=selected.identifier,
        radius_fraction=fraction,
        allocation_reason=reason,
        linear=asdict(optimum) if optimum else None,
        candidate_agreement=asdict(score),
        candidate=snapshot(candidate),
    )
    if (
        candidate.material_length_mm
        > baseline.material_length_mm + 1e-8 * source.targets.diameter_mm
        or fold_count(candidate) > fold_count(baseline)
        or score.rms_mm >= old_score.rms_mm - 1e-8 * source.targets.diameter_mm
    ):
        details["reason"] = "candidate_did_not_improve_baseline_contract"
        return baseline, details
    details["reason"] = "guided"
    return candidate, details
