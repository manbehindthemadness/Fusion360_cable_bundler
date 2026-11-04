"""
Bound residual-driven closure work while retaining unfinished, still-progressing chains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary

from .allocation import Allocation, fit
from .continuation import BranchPolicy
from .features import Chain
from .repair import Closure, StraightMotion, changed, correction, nearest, reframed


@dataclass(frozen=True)
class Unclosed:
    """
    Retain one existing algebraic branch and its measured positional residual.
    """

    chain: Chain
    closure: Closure
    iteration: int = 0


def refine(
    boundary: Boundary,
    unfinished: Unclosed,
    threshold_mm: float,
    maximum_steps: int,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
    *,
    branch_policy: BranchPolicy = BranchPolicy.INDEX,
) -> Allocation | Unclosed | None:
    """
    Continue the same residual-derived corrections until exact closure, stalling or a finite cap.

    Every accepted step must reduce the actual globally reprojected residual.
    The original pi/4 angular cap and two step halvings remain. Return an
    unfinished state only after exhausting the cap while still progressing;
    derivative failure or stalling returns None. Only the last step of a resumed
    continuation eliminates positive straight freedom from its angular system;
    earlier steps preserve established fixed-straight behavior. The step count,
    targets, roots and radii stay fixed.
    """
    current, closure = unfinished.chain, unfinished.closure
    for iteration in range(unfinished.iteration, unfinished.iteration + maximum_steps):
        motion = (
            StraightMotion.REALLOCATABLE
            if unfinished.iteration > 0 and iteration == unfinished.iteration + maximum_steps - 1
            else StraightMotion.FIXED
        )
        delta = correction(
            boundary,
            current,
            closure,
            checkpoint,
            straight_motion=motion,
            branch_policy=branch_policy,
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
                changed(current.targets, delta, 0.5**halving),
                branch_policy=branch_policy,
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
            trial = nearest(Model(boundary, probe.topology), checkpoint)
            record(
                {
                    "stage": "feature_reclosure",
                    "roots": current.roots,
                    "iteration": iteration,
                    "halving": halving,
                    "status": "residual_reduced"
                    if trial.error < closure.error - 1e-10
                    else "no_gain",
                    "position_error_diameters": trial.error,
                    "angular_delta": delta,
                    "branch_policy": branch_policy.value,
                    "straight_motion": motion.value,
                }
            )
            if trial.error < closure.error - 1e-10:
                current, closure, progressed = probe, trial, True
                if trial.error <= 1e-7 / boundary.targets.diameter_mm:
                    allocation = fit(boundary, current, threshold_mm, checkpoint, record)
                    if allocation is not None:
                        return allocation
                break
        if not progressed:
            return None
    return (
        Unclosed(current, closure, unfinished.iteration + maximum_steps)
        if closure.error > 1e-7 / boundary.targets.diameter_mm
        else None
    )


def refine_preserving_legacy(
    boundary: Boundary,
    unfinished: Unclosed,
    threshold_mm: float,
    maximum_steps: int,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Allocation | Unclosed | None:
    """
    Keep closed continuous legacy results; correct detected factor jumps without losing fallback.

    Initial reclosure gets at most one additional equally bounded continuation
    attempt, within the caller's unchanged first-pass time/contact limits. Resumed
    work retains the legacy policy. A continuous result replaces a closed legacy
    result only with non-increasing site error and material length. Hard errors
    propagate; unsuccessful continuation retains the original result.
    """
    legacy = refine(boundary, unfinished, threshold_mm, maximum_steps, checkpoint, record)
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
    )
    if not isinstance(continuous, Allocation):
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
