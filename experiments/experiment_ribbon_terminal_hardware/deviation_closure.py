"""
Reclose one original deviation topology using only its caller's unspent correction allowance.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from experiments.experiment_ribbon_feature_insertion.allocation import (
    Allocation,
    closure_allocation,
)
from experiments.experiment_ribbon_feature_insertion.closure_goal import ClosureGoal
from experiments.experiment_ribbon_feature_insertion.continuation import BranchPolicy
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.reclosure import (
    ReclosureAllocation,
    Unclosed,
    refine,
)
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
    *,
    maximum_steps: int = 4,
    allocation_policy: ReclosureAllocation = ReclosureAllocation.GUIDE,
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
    MEASURED uses only native-cone coordinates and the strict mating goal;
    it never renews guide masks. The caller supplies its remaining step ceiling.
    """
    if type(maximum_steps) is not int or not 0 <= maximum_steps <= 4:
        raise ValueError("Use zero to four unspent local corrections")
    if not isinstance(allocation_policy, ReclosureAllocation):
        raise ValueError("Select an explicit closure allocation policy")
    pending: list[Unclosed] = []
    for chain in attempted:
        checkpoint()
        measured = nearest(
            Model(boundary, chain.topology),
            checkpoint,
            maximum_straight_mm=maximum_straight_mm,
            minimum_straight_mm=threshold_mm,
        )
        if (
            allocation_policy is ReclosureAllocation.MEASURED
            and measured.error <= 1e-7 / boundary.targets.diameter_mm
        ):
            closed = closure_allocation(
                boundary,
                chain,
                measured.values,
                threshold_mm,
                checkpoint,
                record,
                maximum_straight_mm=maximum_straight_mm,
            )
            if closed is not None and ClosureGoal.MATING.accepts(closed.route):
                return closed
        limit = (
            ClosureGoal.MATING
            if allocation_policy is ReclosureAllocation.MEASURED
            else ClosureGoal.ROUTE
        ).normalized_limit(boundary.targets.diameter_mm)
        if measured.error > limit:
            pending.append(
                Unclosed(
                    chain,
                    measured,
                    branch_policy=BranchPolicy.CONTINUOUS,
                    goal=ClosureGoal.MATING,
                    allocation_policy=allocation_policy,
                )
            )
    if not pending or maximum_steps == 0:
        return None
    selected = min(pending, key=lambda item: (item.closure.error, item.chain.roots))
    record(
        {
            "stage": "spatial_deviation_closure",
            "status": "started",
            "roots": selected.chain.roots,
            "position_error_diameters": selected.closure.error,
            "branch_policy": selected.branch_policy.value,
            "maximum_steps": maximum_steps,
            "closure_goal": selected.goal.value,
            "maximum_straight_mm": maximum_straight_mm,
        }
    )
    result = refine(
        boundary,
        selected,
        threshold_mm,
        maximum_steps,
        checkpoint,
        record,
        maximum_straight_mm=maximum_straight_mm,
        **(
            {"allocation_policy": allocation_policy}
            if allocation_policy is ReclosureAllocation.MEASURED
            else {}
        ),
    )
    record(
        {
            "stage": "spatial_deviation_closure",
            "status": "closed" if isinstance(result, Allocation) else "unresolved",
            "roots": selected.chain.roots,
        }
    )
    return result if isinstance(result, Allocation) else None
