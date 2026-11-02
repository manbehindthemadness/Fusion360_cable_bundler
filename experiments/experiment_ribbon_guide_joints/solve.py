"""
Test bounded guide-directed joint motion with coupled closure and conservative contact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Allocation, allocations
from experiments.experiment_ribbon_reduced_joints.kinematics import Joint, moved
from experiments.experiment_ribbon_reduced_joints.solve import (
    CONTACT_PAIRS,
    CONTACTS,
    HALVINGS,
    ITERATIONS,
)

from .direction import direction
from .placement import Placement


@dataclass(frozen=True)
class Result:
    """
    Preserve the last valid route and separate placement/closure work from contact work.
    """

    allocation: Allocation
    frame: Pose
    reason: str
    accepted: int
    contacts: int
    iterations: int
    contact_seconds: float


def solve(
    joint: Joint,
    frame: Pose,
    baseline: Allocation,
    placement: Placement,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Result:
    """
    Improve fixed ordered placement without length growth, extra features or alternate root banks.

    Each changed frame uses global nonnegative affine endpoint closure; composed
    material frames join adjacent features exactly. Four updates/four halvings/
    four contact checks retain403work bounds. Unresolved retains preceding geometry.
    """
    current = baseline
    accepted = contacts = iterations = 0
    contact_seconds = 0.0
    reason = "iteration_budget"
    for iteration in range(ITERATIONS):
        checkpoint()
        iterations = iteration + 1
        if contacts >= CONTACTS:
            reason = "contact_budget"
            break
        descent = direction(joint, frame, current, placement, checkpoint)
        if descent is None:
            reason = "no_certified_placement_direction"
            break
        step = descent.step_radians
        changed = False
        score = placement.score(current.route.pieces)
        for halving in range(HALVINGS):
            checkpoint()
            trial_frame = moved(frame, descent.motion, step)
            model = joint.model(trial_frame)
            event: dict[str, Any] = {
                "stage": "guide_joint",
                "iteration": iteration,
                "halving": halving,
                "descent": asdict(descent),
                "step_radians": step,
                "status": "branch_unresolved",
            }
            if model is not None:

                def allocation_record(
                    row: dict[str, Any],
                    *,
                    step_iteration: int = iteration,
                    step_halving: int = halving,
                ) -> None:
                    """
                    Retain every deterministic algebraic support result for the derived step.
                    """
                    record({**row, "iteration": step_iteration, "halving": step_halving})

                choices = allocations(model, checkpoint, allocation_record)
                eligible = [
                    a
                    for a in choices
                    if a.route.material_length_mm
                    <= current.route.material_length_mm + 1e-8 * joint.boundary.targets.diameter_mm
                ]
                event["status"] = "position_unresolved" if not choices else "length_growth_rejected"
                if eligible:
                    candidate = min(
                        eligible,
                        key=lambda a: (
                            placement.score(a.route.pieces),
                            a.route.material_length_mm,
                            a.support,
                        ),
                    )
                    route = candidate.route
                    trial_score = placement.score(route.pieces)
                    event.update(
                        length_mm=route.material_length_mm,
                        placement_score=trial_score,
                        support=candidate.support,
                    )
                    if trial_score >= score - 1e-10:
                        event["status"] = "no_placement_gain"
                    elif cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                        raise ArithmeticError(
                            "Guide joint lost ordered caps or material compatibility"
                        )
                    else:
                        record({**event, "status": "contact_started"})
                        started = perf_counter()
                        contact = inspect_contact(
                            route, maximum_pairs=CONTACT_PAIRS, checkpoint=checkpoint
                        )
                        contact_seconds += perf_counter() - started
                        event.update(
                            status=contact.status, contact=asdict(contact), route=snapshot(route)
                        )
                        contacts += 1
                        changed = contact.status == "separated"
                        if changed:
                            event["status"] = "accepted"
                            accepted += 1
                            frame = trial_frame
                            current = candidate
            record(event)
            if changed or contacts >= CONTACTS:
                break
            step /= 2
        if not changed:
            reason = "contact_budget" if contacts >= CONTACTS else "halving_budget"
            break
    return Result(current, frame, reason, accepted, contacts, iterations, contact_seconds)
