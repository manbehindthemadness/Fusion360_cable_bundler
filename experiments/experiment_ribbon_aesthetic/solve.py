"""
Accept bounded aesthetic curvature descent only after exact-cap and thick-contact checks.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
from experiments.experiment_ribbon_fold_route.contact import inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .model import Model, curvature_score, peak_curvature


def direction(model: Model, values: tuple[float, ...]) -> tuple[float, ...] | None:
    """
    Project curvature descent onto affine closure and active nonnegative/length bounds.
    """
    gradient = model.gradient(values)
    scale = max((abs(v) for v in gradient), default=0.0)
    if scale <= 1e-14:
        return None
    free = list(range(len(values)))
    rows = [[column[a] for column in model.columns] for a in range(3)]
    length_active = False
    for _ in range(len(values) + 2):
        active = rows + ([list(model.costs)] if length_active else [])
        delta = affine_projection(
            [[row[i] for i in free] for row in active],
            [0.0] * len(active),
            [-gradient[i] / scale for i in free],
        )
        if delta is None:
            return None
        blocked = [i for i, d in zip(free, delta) if values[i] <= 1e-10 and d < -1e-10]
        if blocked:
            free = [i for i in free if i not in blocked]
            continue
        output = [0.0] * len(values)
        for i, d in zip(free, delta):
            output[i] = d
        growth = math.fsum(c * d for c, d in zip(model.costs, output))
        used = math.fsum(c * v for c, v in zip(model.costs, values))
        if not length_active and used >= model.budget - 1e-9 and growth > 1e-10:
            length_active = True
            continue
        return tuple(output)
    return None


def ease(
    source: FoldRoute,
    length_growth: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[FoldRoute, str]:
    """
    Reduce integrated lane curvature within a fixed length allowance and contact budget.

    At most eight iterations, six step halvings per iteration and eight total
    contact proposals. Each variable changes by at most0.5D per iteration. No
    randomness, native repair, new fold, altered crease direction or global optimum
    claim. The caller establishes baseline material/contact acceptance first.
    """
    if cap_error(source) > 1e-7:
        raise ValueError("Aesthetic input must retain the complete ordered caps.")
    model = Model.create(source, length_growth)
    current, values = source, model.initial
    contacts = 0
    peak = peak_curvature(source)
    for iteration in range(8):
        checkpoint()
        delta = direction(model, values)
        gradient = model.gradient(values)
        if delta is None or math.fsum(g * d for g, d in zip(gradient, delta)) >= -1e-10:
            return current, "no_projected_curvature_descent"
        largest = max(abs(d) for d in delta)
        if largest <= 1e-12:
            return current, "direction_floor"
        step = 0.5 / largest
        for value, change in zip(values, delta):
            if change < -1e-12:
                step = min(step, value / -change)
        cost_delta = math.fsum(c * d for c, d in zip(model.costs, delta))
        if cost_delta > 1e-12:
            remaining = model.budget - math.fsum(c * v for c, v in zip(model.costs, values))
            step = min(step, max(0.0, remaining / cost_delta))
        if step <= 1e-10:
            return current, "length_or_coordinate_step_floor"
        for backtrack in range(6):
            checkpoint()
            trial = tuple(max(0.0, v + step * d) for v, d in zip(values, delta))
            candidate = model.route(trial)
            score = curvature_score(candidate)
            event: dict[str, Any] = {
                "iteration": iteration,
                "backtrack": backtrack,
                "route": snapshot(candidate),
                "curvature_score": score,
            }
            if (
                cap_error(candidate) > 1e-7
                or candidate.material_length_mm
                > source.material_length_mm * (1 + length_growth)
                + 1e-8 * source.targets.diameter_mm
                or peak_curvature(candidate) > peak + 1e-10 / source.targets.diameter_mm
            ):
                raise ArithmeticError(
                    "Affine aesthetic trial lost closure, length or curvature bound."
                )
            if score >= curvature_score(current) - 1e-9:
                event["status"] = "no_curvature_gain"
            elif contacts >= 8:
                event["status"] = "unattempted_contact_budget"
                record(event)
                return current, "contact_proposal_budget"
            else:
                record({**event, "status": "contact_started"})
                contact = inspect_contact(candidate, checkpoint=checkpoint)
                contacts += 1
                event.update(contact=asdict(contact), status=contact.status)
                if contact.status == "separated":
                    event["status"] = "accepted"
            record(event)
            if event["status"] == "accepted":
                current, values = candidate, trial
                break
            step /= 2
        else:
            return current, "step_halving_budget"
    return current, "iteration_budget"
