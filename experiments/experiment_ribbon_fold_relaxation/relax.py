"""
Accept coupled straight/fold contraction only after complete closure and contact checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.rewrite import fold_count
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .model import Model
from .steps import advance, projected, retract, step_limit


@dataclass(frozen=True)
class Trial:
    """
    Preserve each contraction/retraction proposal and its explicit disposition.
    """

    iteration: int
    backtrack: int
    status: str
    values: tuple[float, ...]
    route: FoldRoute | None
    contact: ContactResult | None


def relax(
    route: FoldRoute,
    *,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[Trial], None] | None = None,
) -> tuple[FoldRoute, str]:
    """
    Drive down straight travel with compensating fixed-crease fold-angle changes.

    At most eight accepted iterations/six proposals each. Radii/banks/leads remain
    fixed. Retraction may redistribute straight lengths; both their combined total
    and complete material length must decrease. Bend count cannot increase.
    Contact, complete ordered cap vectors and physical compatibility remain hard
    gates. The caller must establish baseline acceptance. No global minimum or
    continuous collision-free deformation path is certified.
    """
    if cap_error(route) > 1e-7:
        raise ValueError("Start from a closed accepted material route.")
    model = Model(route)
    values = model.initial
    current = route
    for iteration in range(8):
        if checkpoint is not None:
            checkpoint()
        gradient = [-1.0 if i in model.straight_indices else 0.0 for i in range(len(values))]
        delta = projected(model, values, model.jacobian(values), [0.0] * 6, gradient)
        if delta is None or math.fsum(delta[i] for i in model.straight_indices) >= -1e-9:
            return current, "no_projected_straight_descent"
        step = step_limit(model, values, delta)
        if not math.isfinite(step) or step <= 1e-10:
            return current, "parameter_step_floor"
        for backtrack in range(6):
            if checkpoint is not None:
                checkpoint()
            initial = advance(model, values, delta, step)
            corrected = retract(model, initial, checkpoint)
            candidate = model.route(corrected) if corrected is not None else None
            contact = None
            status = "closure_unresolved"
            if candidate is not None:
                if cap_error(candidate) > 1e-7:
                    status = "ordered_frame_rejected"
                elif fold_count(candidate) > fold_count(current):
                    status = "bend_count_increased"
                elif (
                    candidate.material_length_mm
                    >= current.material_length_mm - 1e-8 * route.targets.diameter_mm
                    or model.straight_length(corrected)
                    >= model.straight_length(values) - 1e-8 * route.targets.diameter_mm
                ):
                    status = "no_joint_length_gain"
                else:
                    contact = inspect_contact(candidate, checkpoint=checkpoint)
                    status = "accepted" if contact.status == "separated" else contact.status
            if record is not None:
                record(
                    Trial(
                        iteration,
                        backtrack,
                        status,
                        corrected if corrected is not None else initial,
                        candidate,
                        contact,
                    )
                )
            if status == "accepted":
                if candidate is None or corrected is None:
                    raise ArithmeticError("Accepted relaxation has no closed geometry.")
                current, values = candidate, corrected
                break
            step /= 2
        else:
            return current, "proposal_step_budget"
    return current, "iteration_budget"
