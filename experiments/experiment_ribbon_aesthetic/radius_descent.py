"""
Generate bounded affine radius proposals independently of contact scheduling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Generator

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import snapshot
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


@dataclass(frozen=True)
class Proposal:
    """
    Retain one material-valid curvature improvement pending a caller's acceptance decision.
    """

    route: FoldRoute
    event: dict[str, Any]


def proposals(
    source: FoldRoute,
    length_growth: float,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> Generator[Proposal, bool, str]:
    """
    Yield improvements over eight iterations with six halvings and unchanged affine bounds.

    Sending true advances the mathematical descent; it does not certify contact.
    Sending false halves the step from the last accepted mathematical state.
    A stationary direction or exhausted coordinate/length allowance returns before
    any contact work. Caps, length and peak curvature are checked before yielding.
    """
    model = Model.create(source, length_growth)
    current, values = source, model.initial
    peak = peak_curvature(source)
    for iteration in range(8):
        checkpoint()
        delta = direction(model, values)
        gradient = model.gradient(values)
        if delta is None or math.fsum(g * d for g, d in zip(gradient, delta)) >= -1e-10:
            return "no_projected_curvature_descent"
        largest = max(abs(d) for d in delta)
        if largest <= 1e-12:
            return "direction_floor"
        step = 0.5 / largest
        for value, change in zip(values, delta):
            if change < -1e-12:
                step = min(step, value / -change)
        cost_delta = math.fsum(c * d for c, d in zip(model.costs, delta))
        if cost_delta > 1e-12:
            remaining = model.budget - math.fsum(c * v for c, v in zip(model.costs, values))
            step = min(step, max(0.0, remaining / cost_delta))
        if step <= 1e-10:
            return "length_or_coordinate_step_floor"
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
                record({**event, "status": "no_curvature_gain"})
            elif (yield Proposal(candidate, event)):
                current, values = candidate, trial
                break
            step /= 2
        else:
            return "step_halving_budget"
    return "iteration_budget"
