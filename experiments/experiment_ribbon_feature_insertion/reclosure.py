"""
Bound residual-driven closure work while retaining unfinished, still-progressing chains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .allocation import Allocation, closure_allocation, fit
from .closure_goal import ClosureGoal
from .continuation import BranchPolicy
from .features import Chain
from .repair import Closure, StraightMotion, changed, correction, nearest, reframed


@dataclass(frozen=True)
class Unclosed:
    """
    Retain one algebraic branch, its measured residual and the policy that produced its progress.
    """

    chain: Chain
    closure: Closure
    iteration: int = 0
    branch_policy: BranchPolicy = BranchPolicy.INDEX
    goal: ClosureGoal = ClosureGoal.ROUTE

    def __post_init__(self) -> None:
        """
        Keep unfinished progress bound to an explicit physical-factor selection policy.
        """
        if not isinstance(self.branch_policy, BranchPolicy):
            raise ValueError("Retain an explicit unfinished branch policy")
        if not isinstance(self.goal, ClosureGoal):
            raise ValueError("Retain an explicit unfinished closure goal")


def refine(
    boundary: Boundary,
    unfinished: Unclosed,
    threshold_mm: float,
    maximum_steps: int,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    branch_policy: BranchPolicy | None = None,
    maximum_straight_mm: float | None = None,
) -> Allocation | Unclosed | None:
    """
    Continue the same residual-derived corrections until exact closure, stalling or a finite cap.

    Every accepted step must reduce the actual globally reprojected residual.
    The original pi/4 angular cap and two step halvings remain. Return an
    unfinished state only after exhausting the cap while still progressing;
    derivative failure or stalling returns None. Every step of a resumed
    continuation eliminates legal positive-straight freedom from its angular
    system, matching the actual subsequent reallocation. Initial actions retain
    their established fixed-straight behavior. The step count,
    targets, roots and radii stay fixed.
    A supplied straight budget follows every nearest projection and closed fit;
    no resumed or physical-factor continuation can drop or renew that budget.
    Omitted policy resumes the unfinished state's recorded policy; an explicit
    override affects this action and the policy retained by any resulting state.
    """
    policy = unfinished.branch_policy if branch_policy is None else branch_policy
    if not isinstance(policy, BranchPolicy):
        raise ValueError("Select an explicit physical-factor policy")
    checkpoint()
    goal = unfinished.goal
    diameter = boundary.targets.diameter_mm
    limit = ClosureGoal.ROUTE.normalized_limit(diameter)
    precision_pending = False
    goal_options = {"goal": goal} if goal is ClosureGoal.MATING else {}
    current, closure = unfinished.chain, unfinished.closure
    if closure.error <= limit:
        measured = closure_allocation(
            boundary,
            current,
            closure.values,
            threshold_mm,
            checkpoint,
            record,
            maximum_straight_mm=maximum_straight_mm,
        )
        if measured is not None:
            checkpoint()
            if goal.accepts(measured.route):
                checkpoint()
                return measured
            precision_pending = True
    for iteration in range(unfinished.iteration, unfinished.iteration + maximum_steps):
        motion = StraightMotion.REALLOCATABLE if unfinished.iteration > 0 else StraightMotion.FIXED
        delta = correction(
            boundary,
            current,
            closure,
            checkpoint,
            straight_motion=motion,
            branch_policy=policy,
            maximum_straight_mm=maximum_straight_mm,
            minimum_straight_mm=threshold_mm,
            **goal_options,
        )
        if delta is None:
            record(
                {
                    "stage": "feature_reclosure",
                    "roots": current.roots,
                    "iteration": iteration,
                    "status": "derivative_unresolved",
                    "position_error_diameters": closure.error,
                    "straight_motion": motion.value,
                }
            )
            return None
        progressed = False
        for halving in range(2):
            checkpoint()
            probe = reframed(
                boundary,
                current,
                changed(current.targets, delta, 0.5**halving, **goal_options),
                branch_policy=policy,
            )
            if probe is None:
                record(
                    {
                        "stage": "feature_reclosure",
                        "roots": current.roots,
                        "iteration": iteration,
                        "halving": halving,
                        "status": "branch_unresolved",
                    }
                )
                continue
            trial = nearest(
                Model(boundary, probe.topology),
                checkpoint,
                maximum_straight_mm=maximum_straight_mm,
                minimum_straight_mm=threshold_mm,
            )
            improved = goal.improves(closure.error, trial.error, diameter)
            record(
                {
                    "stage": "feature_reclosure",
                    "roots": current.roots,
                    "iteration": iteration,
                    "halving": halving,
                    "closure_goal": goal.value,
                    "status": "residual_reduced" if improved else "no_gain",
                    "position_error_diameters": trial.error,
                    "angular_delta": delta,
                    "branch_policy": policy.value,
                    "straight_motion": motion.value,
                }
            )
            if improved:
                current, closure, progressed = probe, trial, True
                precision_pending = False
                if trial.error <= limit:
                    allocation = fit(
                        boundary,
                        current,
                        threshold_mm,
                        checkpoint,
                        record,
                        maximum_straight_mm=maximum_straight_mm,
                        feasible_values=trial.values,
                    )
                    if allocation is not None:
                        checkpoint()
                        if goal.accepts(allocation.route):
                            checkpoint()
                            return allocation
                        precision_pending = True
                        if allocation.values != trial.values:
                            retained = closure_allocation(
                                boundary,
                                current,
                                trial.values,
                                threshold_mm,
                                checkpoint,
                                record,
                                maximum_straight_mm=maximum_straight_mm,
                            )
                            if retained is not None and goal.accepts(retained.route):
                                checkpoint()
                                return retained
                break
        if not progressed:
            return None
    return (
        Unclosed(current, closure, unfinished.iteration + maximum_steps, policy, goal)
        if closure.error > limit or precision_pending
        else None
    )


def refine_preserving_legacy(
    boundary: Boundary,
    unfinished: Unclosed,
    threshold_mm: float,
    maximum_steps: int,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    maximum_straight_mm: float | None = None,
) -> Allocation | Unclosed | None:
    """
    Keep closed continuous legacy results; correct detected factor jumps without losing fallback.

    Initial reclosure gets at most one additional equally bounded continuation
    attempt, within the caller's unchanged first-pass time/contact limits. Resumed
    work retains its recorded policy. A continuous result replaces a closed legacy
    result only with non-increasing site error and material length. Hard errors
    propagate; unsuccessful continuation retains the original result. When both
    outcomes are unfinished, keep the lower measured residual, retaining legacy
    ties. Already computed continuous progress also survives a stalled legacy
    action. This changes neither the two initial actions nor the one resumed
    action's original correction limit.
    """
    options = (
        {"maximum_straight_mm": maximum_straight_mm} if maximum_straight_mm is not None else {}
    )
    legacy = refine(
        boundary, unfinished, threshold_mm, maximum_steps, checkpoint, record, **options
    )
    if unfinished.iteration or (
        isinstance(legacy, Allocation) and not legacy.chain.factor_discontinuity
    ):
        return legacy
    continuous = refine(
        boundary,
        unfinished,
        threshold_mm,
        maximum_steps,
        checkpoint,
        record,
        branch_policy=BranchPolicy.CONTINUOUS,
        **options,
    )
    if not isinstance(continuous, Allocation):
        if isinstance(continuous, Unclosed) and (
            legacy is None
            or (isinstance(legacy, Unclosed) and continuous.closure.error < legacy.closure.error)
        ):
            record(
                {
                    "stage": "factor_continuation",
                    "status": "unfinished",
                    "roots": continuous.chain.roots,
                    "branch_policy": continuous.branch_policy.value,
                    "position_error_diameters": continuous.closure.error,
                    "legacy_position_error_diameters": legacy.closure.error
                    if isinstance(legacy, Unclosed)
                    else None,
                }
            )
            return continuous
        return legacy
    if isinstance(legacy, Allocation) and (
        continuous.score > legacy.score
        or continuous.route.material_length_mm > legacy.route.material_length_mm
    ):
        return legacy
    record(
        {
            "stage": "factor_continuation",
            "status": "closed",
            "roots": unfinished.chain.roots,
            "legacy_closed": isinstance(legacy, Allocation),
        }
    )
    return continuous
