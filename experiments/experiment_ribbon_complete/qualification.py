"""
Measure available branch qualifications without transferring them to complete-ribbon acceptance.

Each emitted row names its limited scope. The caller retains rows immediately,
owns one shared resource checkpoint, and records any interrupted suffix. No
solver, native builder, retry or complete physical pass is invoked here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .branch_bends import audit as audit_bends
from .execution import RibbonPlan
from .material_atlas import audit as audit_atlas


def inspect(
    plan: RibbonPlan,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> None:
    """
    Reuse the exact saved plans and measure bending and material-coordinate maps once.

    A certified coordinate map establishes injectivity and conditioning, not
    material metric preservation. An unresolved sufficient bound is not a
    witnessed violation. Errors propagate after the caller's last flushed row;
    later branches are never silently counted as measured.
    """
    checkpoint()
    if plan.trunk.route is None or plan.unattempted_route_ids:
        record({"gate": "branch_audits", "status": "not_attempted", "reason": "incomplete_plan"})
        return
    for branch in plan.branches:
        checkpoint()
        route_id = str(branch.source.source.leg.route_id)
        record({"gate": "branch_bending", "route_id": route_id, "status": "started"})
        bends = audit_bends(branch, checkpoint)
        record(
            {
                "gate": "branch_bending",
                "route_id": route_id,
                "status": "measured",
                "principal_reach": bends.principal_reach_status,
                "normal_field": bends.normal_field_status,
                "coordinates": bends.coordinate_status,
                "lateral": bends.lateral_status,
                "lateral_excursion_upper_mm": (
                    None
                    if bends.lateral_excursion_upper_mm is None
                    else str(bends.lateral_excursion_upper_mm)
                ),
                "scope": "ending geometric support bounds; not complete material curvature",
            }
        )
        checkpoint()
        record({"gate": "branch_material_coordinates", "route_id": route_id, "status": "started"})
        atlas = audit_atlas(branch, checkpoint)
        record(
            {
                "gate": "branch_material_coordinates",
                "route_id": route_id,
                "status": atlas.status,
                "world_condition_upper": (
                    None
                    if atlas.world_condition_upper is None
                    else str(atlas.world_condition_upper)
                ),
                "scope": "piecewise material coordinates; no isometry or native correspondence",
            }
        )
    checkpoint()
