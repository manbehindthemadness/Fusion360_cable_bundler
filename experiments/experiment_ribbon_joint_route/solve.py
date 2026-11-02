"""
Select a jointly closed first-pass material route without serial offset/reset modules.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_spline_guide.guide import Agreement, Guide, agreement

from .allocation import Allocation, Model, allocations
from .boundary import FoldBoundary
from .frames import topologies
from .optimization import optimize


def construct(
    source: FoldBoundary,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    comparison: FoldRoute | None = None,
    first_pass_optimization: bool = True,
) -> tuple[FoldRoute | None, dict[str, Any]]:
    """
    Close exact rotation families, then optimize the accepted first pass with free bend orientations.

    The source contributes fixed targets/profile/radius bound. An optional existing
    comparison limits length/fold regression; cold endpoint construction requires
    no successful route or historical artifact. Guide-derived rotation families
    provide a rough closed route. Its angles, banks, radii and straight slots then
    optimize together before first-pass output. Full thick contact remains a hard
    gate throughout; optional aesthetic smoothing is owned by the caller.
    Disabling optimization returns the selected separated coarse route unchanged.
    """
    families = topologies(source, guide)
    candidates: list[tuple[Allocation, Agreement]] = []
    seen = set()
    for topology in families:
        checkpoint()
        record(
            {
                "stage": "topology",
                "id": topology.identifier,
                "folds": [asdict(f) for f in topology.folds],
                "middle_after": topology.middle_after,
            }
        )
        for item in allocations(Model(source, topology), checkpoint, record):
            route = item.route
            if comparison is not None and (
                route.material_length_mm
                > comparison.material_length_mm + 1e-8 * source.targets.diameter_mm
                or fold_count(route) > fold_count(comparison)
            ):
                record(
                    {
                        "stage": "comparison_guard",
                        "topology": item.topology,
                        "status": "longer_or_more_folds",
                        "route": snapshot(route),
                    }
                )
                continue
            signature = tuple(
                (p.geometry.__class__.__name__, tuple(vars(p.geometry).values()))
                for p in route.pieces
            )
            if signature in seen:
                continue
            seen.add(signature)
            score = agreement(route, guide)
            candidates.append((item, score))
    candidates.sort(
        key=lambda pair: (
            round(pair[0].route.material_length_mm, 10),
            round(pair[1].rms_mm, 10),
            fold_count(pair[0].route),
            pair[0].topology,
            pair[0].support,
        )
    )
    attempts = []
    chosen: Allocation | None = None
    chosen_contact: ContactResult | None = None
    for index, (item, score) in enumerate(candidates):
        row: dict[str, Any] = {
            "rank": index,
            "topology": item.topology,
            "support": item.support,
            "length_mm": item.route.material_length_mm,
            "folds": fold_count(item.route),
            "agreement": asdict(score),
        }
        attempts.append(row)
        if chosen is not None or index >= 12:
            row["status"] = (
                "unattempted_after_selection" if chosen else "contact_budget_unattempted"
            )
            continue
        checkpoint()
        contact = inspect_contact(item.route, checkpoint=checkpoint)
        row.update(status=contact.status, contact=asdict(contact))
        record({"stage": "contact", "route": snapshot(item.route), **row})
        if contact.status == "separated":
            chosen = item
            chosen_contact = contact
    details: dict[str, Any] = {
        "topologies": len(families),
        "ranked_candidates": len(candidates),
        "candidates": attempts,
        "selected": chosen.topology if chosen else None,
        "stop_reason": "first_separated_joint_route"
        if chosen
        else "no_separated_joint_route_within_families_and_budget",
    }
    if chosen is None or chosen_contact is None:
        return None, details
    if not first_pass_optimization:
        details["optimization"] = {"reason": "disabled", "seconds": 0.0}
        return chosen.route, details
    optimized = optimize(chosen.route, guide, checkpoint, record, baseline_contact=chosen_contact)
    details["optimization"] = optimized.summary()
    return optimized.route, details


def solve(
    source: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, dict[str, Any]]:
    """
    Preserve the historical comparison entry point and its unchanged valid fallback.
    """
    route, details = construct(source, guide, checkpoint, record, comparison=source)
    return (route if route is not None else source), details
