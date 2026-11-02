"""
Merge compatible equal-crease turn groups without requiring equal original bend radii.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Callable

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_reduction.rewrite import Rewrite, reclose
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .layout_model import surface_score
from .model import peak_curvature


def proposals(route: FoldRoute) -> tuple[Rewrite, ...]:
    """
    Combine same-direction common-crease turns of total angle at most a half-turn.

    Use the angle-weighted mean radius, preserving total curved material length.
    Required outer leads remain unchanged; intermediate leads become available
    runway. Complete positional closure and contact are checked after replacement.
    Different-axis turns are not silently replaced by a scalar angle sum.
    """
    folds = [
        (i, p.geometry)
        for i, p in enumerate(route.pieces)
        if isinstance(p.geometry, CylindricalFold)
    ]
    output = []
    for index, (first_index, first) in enumerate(folds):
        group = [first]
        for last_index, following in folds[index + 1 :]:
            if (
                abs(following.bank_radians - first.bank_radians) > 1e-10
                or abs(following.width_mm - first.width_mm) > 1e-10
                or following.angle_radians * first.angle_radians <= 0
            ):
                break
            group.append(following)
            total = math.fsum(f.angle_radians for f in group)
            if abs(total) > math.pi:
                break
            radius = math.fsum(f.radius_mm * abs(f.angle_radians) for f in group) / abs(total)
            replacement = CylindricalFold(
                radius,
                total,
                first.bank_radians,
                first.width_mm,
                first.before_mm,
                following.after_mm,
            )
            output.append(Rewrite(first_index, last_index, len(group) - 1, replacement))
    return tuple(sorted(output, key=lambda r: (-r.removed_folds, r.first, r.last)))


def merge(
    route: FoldRoute,
    maximum_length_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, str]:
    """
    Accept at most two merge passes, twelve algebraic proposals and four contact checks.

    Fewer folds must preserve complete target frames, the original total-length
    budget, no worse peak lane curvature and no worse full-surface curvature score.
    Unresolved contact is never accepted. The caller certifies the input first.
    """
    current = route
    evaluated = 0
    contacts = 0
    for stage in range(2):
        options = proposals(current)
        if not options:
            return current, "no_compatible_common_crease_group"
        for rewrite in options:
            if evaluated >= 12:
                return current, "merge_proposal_budget"
            checkpoint()
            evaluated += 1
            candidate = reclose(current, rewrite)
            event: dict[str, Any] = {
                "stage": stage,
                "rewrite": asdict(rewrite),
                "status": "closure_unresolved",
                "route": snapshot(candidate) if candidate else None,
            }
            if candidate is not None:
                if (
                    candidate.material_length_mm
                    > maximum_length_mm + 1e-8 * route.targets.diameter_mm
                ):
                    event["status"] = "length_budget_rejected"
                elif (
                    peak_curvature(candidate)
                    > peak_curvature(route) + 1e-10 / route.targets.diameter_mm
                ):
                    event["status"] = "peak_lane_curvature_rejected"
                elif (
                    surface_score(candidate, route.material_length_mm)
                    > surface_score(current, route.material_length_mm) + 1e-9
                ):
                    event["status"] = "surface_curvature_rejected"
                elif contacts >= 4:
                    event["status"] = "unattempted_contact_budget"
                    record(event)
                    return current, "merge_contact_budget"
                else:
                    record({**event, "status": "contact_started"})
                    contact = inspect_contact(candidate, checkpoint=checkpoint)
                    contacts += 1
                    event.update(
                        contact=asdict(contact),
                        status="accepted" if contact.status == "separated" else contact.status,
                    )
            record(event)
            if event["status"] == "accepted" and candidate is not None:
                current = candidate
                break
        else:
            return current, "no_accepted_merge"
    return current, "merge_pass_budget"
