"""
Select a jointly closed first-pass material route without serial offset/reset modules.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_spline_guide.guide import Guide, agreement

from .allocation import Model, allocations
from .frames import topologies


def solve(
    source: FoldRoute,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, dict[str, Any]]:
    """
    Jointly close each exact rotation family, then check up to twelve shortest candidates.

    The source contributes fixed targets/profile/radius bound and a comparison cap,
    never its old fold order, banks or lengths. Guide-derived intermediate orientation
    distributes rotation. No envelope gaps, entry resets, nonlinear attraction or
    post-construction radius pass. Full thick contact remains a separate hard gate.
    """
    families = topologies(source, guide)
    candidates = []
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
            if (
                route.material_length_mm
                > source.material_length_mm + 1e-8 * source.targets.diameter_mm
                or fold_count(route) > fold_count(source)
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
    chosen = None
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
    details = {
        "topologies": len(families),
        "ranked_candidates": len(candidates),
        "candidates": attempts,
        "selected": chosen.topology if chosen else None,
        "stop_reason": "first_separated_joint_route"
        if chosen
        else "no_separated_joint_route_within_families_and_budget",
    }
    return (chosen.route if chosen else source), details
