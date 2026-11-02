"""
Construct a shorter closed route through one bounded reduced-joint descent, without refinement passes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.allocation import Allocation, allocations
from experiments.experiment_ribbon_spline_guide.guide import Guide, agreement

from .kinematics import Joint, moved
from .sensitivity import direction

ITERATIONS = 4
HALVINGS = 4
CONTACTS = 4
CONTACT_PAIRS = 1024


@dataclass(frozen=True)
class Result:
    """
    Preserve the preceding validated allocation when finite work cannot establish an improvement.
    """

    allocation: Allocation
    frame: Pose
    reason: str
    iterations: int
    accepted: int
    contacts: int


def solve(
    joint: Joint,
    initial_frame: Pose,
    baseline: Allocation,
    guide: Guide,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Result:
    """
    Follow a derived joint direction, reclose the linear allocation and accept only shorter separated routes.

    No alternate frame/angle bank, first-pass optimizer or aesthetic pass runs.
    At most four updates/four halvings/four contact proposals are allowed. Guide
    agreement breaks minimum-length ties; it is not a new physical rejection rule.
    Conservative unresolved contact rejects. Source/resource exceptions propagate.
    """
    current, frame = baseline, initial_frame
    contacts = accepted = iterations = 0
    reason = "iteration_budget"
    for iteration in range(ITERATIONS):
        checkpoint()
        if contacts >= CONTACTS:
            reason = "contact_budget"
            break
        iterations = iteration + 1
        descent = direction(joint, frame, current, checkpoint)
        if descent is None:
            reason = "no_certified_reduced_direction"
            break
        step = descent.step_radians
        changed = False
        for halving in range(HALVINGS):
            checkpoint()
            trial_frame = moved(frame, descent.direction, step)
            model = joint.model(trial_frame)
            event: dict[str, Any] = {
                "stage": "reduced_joint",
                "iteration": iteration,
                "halving": halving,
                "descent": asdict(descent),
                "step_radians": step,
                "frame": asdict(trial_frame),
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
                    Preserve every algebraic support outcome for this one derived joint step.
                    """
                    record({**row, "iteration": step_iteration, "halving": step_halving})

                choices = allocations(model, checkpoint, allocation_record)
                candidate = (
                    min(
                        choices,
                        key=lambda a: (
                            round(a.route.material_length_mm, 10),
                            agreement(a.route, guide).rms_mm,
                            a.support,
                        ),
                    )
                    if choices
                    else None
                )
                event["status"] = "position_unresolved"
                if candidate is not None:
                    route = candidate.route
                    event.update(length_mm=route.material_length_mm, support=candidate.support)
                    if (
                        route.material_length_mm
                        >= current.route.material_length_mm
                        - 1e-8 * joint.boundary.targets.diameter_mm
                    ):
                        event["status"] = "no_length_gain"
                    elif cap_error(route) > 1e-7 or material_error(route) > 1e-10:
                        raise ArithmeticError(
                            "Reduced joint lost ordered caps or material compatibility"
                        )
                    elif contacts >= CONTACTS:
                        event["status"] = "contact_budget"
                    else:
                        record({**event, "status": "contact_started"})
                        contact = inspect_contact(
                            route, maximum_pairs=CONTACT_PAIRS, checkpoint=checkpoint
                        )
                        contacts += 1
                        event.update(
                            status=contact.status, contact=asdict(contact), route=snapshot(route)
                        )
                        if contact.status == "separated":
                            current, frame = candidate, trial_frame
                            accepted += 1
                            changed = True
                            event["status"] = "accepted"
            record(event)
            if changed:
                break
            if contacts >= CONTACTS:
                break
            step /= 2
        if not changed:
            reason = "contact_budget" if contacts >= CONTACTS else "halving_budget"
            break
    return Result(current, frame, reason, iterations, accepted, contacts)
