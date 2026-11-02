"""
Relax complete fold geometry into available runway with layout-relative trust steps.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_relaxation.flexible_steps import retract, step_limit
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .layout_model import Model
from .model import peak_curvature


def ease(
    source: FoldRoute,
    maximum_length_mm: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, str]:
    """
    Accept at most eight contact-checked curvature improvements with fixed ordered caps.

    Start from the last accepted aesthetic result. The maximum length is the
    original first-pass budget, never another compounded5%allowance. Signed fold
    order stays fixed; banks/radii/angles and all available runway can redistribute.
    """
    if (
        cap_error(source) > 1e-7
        or maximum_length_mm < source.material_length_mm - 1e-8 * source.targets.diameter_mm
    ):
        raise ValueError("Start from an accepted closed route within its original length budget")
    model = Model(source)
    values = model.initial
    current = source
    maximum_length = maximum_length_mm / model.scale
    original_peak = peak_curvature(source)
    contacts = 0
    for iteration in range(8):
        checkpoint()
        gradient = model.gradient(values)
        scale = max((abs(v) for v in gradient), default=0.0)
        if scale <= 1e-14:
            return current, "straight_or_gradient_floor"
        reference = [-v / scale for v in gradient]
        rows = model.jacobian(values)
        delta = projected(model, values, rows, [0.0] * 6, reference)
        if delta is None:
            return current, "no_projected_curvature_descent"
        length_gradient = model.length_gradient(values)
        if (
            model.length(values) >= maximum_length - 1e-9
            and math.fsum(g * d for g, d in zip(length_gradient, delta)) > 0
        ):
            rows.append(length_gradient)
            delta = projected(model, values, rows, [0.0] * 7, reference)
        if delta is None or math.fsum(g * d for g, d in zip(gradient, delta)) >= -1e-10:
            return current, "no_projected_curvature_descent"
        step = step_limit(model, values, delta)
        if not math.isfinite(step) or step <= 1e-10:
            return current, "coordinate_step_floor"
        for backtrack in range(6):
            checkpoint()
            corrected = retract(
                model, advance(model, values, delta, step), maximum_length, checkpoint
            )
            candidate = model.route(corrected) if corrected is not None else None
            event: dict[str, Any] = {
                "iteration": iteration,
                "backtrack": backtrack,
                "status": "closure_unresolved",
                "route": snapshot(candidate) if candidate else None,
            }
            if candidate is not None and corrected is not None:
                score = model.score(corrected)
                event["curvature_score"] = score
                if cap_error(candidate) > 1e-7:
                    event["status"] = "ordered_caps_rejected"
                elif (
                    candidate.material_length_mm
                    > maximum_length_mm + 1e-8 * source.targets.diameter_mm
                ):
                    event["status"] = "length_budget_rejected"
                elif peak_curvature(candidate) > original_peak + 1e-10 / source.targets.diameter_mm:
                    event["status"] = "peak_lane_curvature_rejected"
                elif score >= model.score(values) - 1e-9:
                    event["status"] = "no_curvature_gain"
                elif contacts >= 8:
                    event["status"] = "unattempted_contact_budget"
                    record(event)
                    return current, "contact_proposal_budget"
                else:
                    record({**event, "status": "contact_started"})
                    contact = inspect_contact(candidate, checkpoint=checkpoint)
                    contacts += 1
                    event.update(
                        contact=asdict(contact),
                        status="accepted" if contact.status == "separated" else contact.status,
                    )
            record(event)
            if event["status"] == "accepted" and candidate is not None and corrected is not None:
                current, values = candidate, corrected
                break
            step /= 2
        else:
            return current, "step_halving_budget"
    return current, "iteration_budget"
