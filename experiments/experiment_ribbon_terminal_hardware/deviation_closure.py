"""
Reclose one original deviation topology using only its caller's unspent correction allowance.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.reclosure import Unclosed, refine
from experiments.experiment_ribbon_feature_insertion.repair import nearest
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary


def close(
    boundary: Boundary,
    attempted: Sequence[Chain],
    threshold_mm: float,
    maximum_straight_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Allocation | None:
    """
    Refine only the closest original nonclosed endpoint, without another guide or root.

    The caller charges this preparation and action as one original logical
    update, tracks accepted correction events and shares its existing clocks.
    At most four angular corrections retain the original straight-travel budget,
    cap targets and radii. Already closed endpoints whose full allocation failed
    are ineligible: closure work cannot bypass those other allocation contracts.
    Failed or still-unclosed work ends this action; no next topology is tried.
    A returned allocation grants no material-contact or hardware clearance.
    """
    pending: list[Unclosed] = []
    for chain in attempted:
        checkpoint()
        measured = nearest(
            Model(boundary, chain.topology), checkpoint, maximum_straight_mm=maximum_straight_mm
        )
        if measured.error > 1e-7 / boundary.targets.diameter_mm:
            pending.append(Unclosed(chain, measured, branch_policy=BranchPolicy.CONTINUOUS))
    if not pending:
        return None
    selected = min(pending, key=lambda item: (item.closure.error, item.chain.roots))
    record(
        {
            "stage": "spatial_deviation_closure",
            "status": "started",
            "roots": selected.chain.roots,
            "position_error_diameters": selected.closure.error,
            "branch_policy": selected.branch_policy.value,
            "maximum_steps": 4,
            "maximum_straight_mm": maximum_straight_mm,
        }
    )
    result = refine(
        boundary,
        selected,
        threshold_mm,
        4,
        checkpoint,
        record,
        maximum_straight_mm=maximum_straight_mm,
    )
    record(
        {
            "stage": "spatial_deviation_closure",
            "status": "closed" if isinstance(result, Allocation) else "unresolved",
            "roots": selected.chain.roots,
        }
    )
    return result if isinstance(result, Allocation) else None
