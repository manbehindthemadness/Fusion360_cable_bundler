"""
Allocate travel and radius together, then check a bounded exact-closure segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult, inspect_contact
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .model import Model
from .program import Solution, allocate


@dataclass(frozen=True)
class Trial:
    """
    Retain the exact-closure interpolation and its full-volume contact disposition.
    """

    fraction: float
    values: tuple[float, ...]
    route: FoldRoute
    contact: ContactResult


def solve(
    route: FoldRoute,
    *,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[Trial], None] | None = None,
) -> tuple[FoldRoute, Solution | None, float, str]:
    """
    Minimize straight travel with larger radii and a nonincreasing material budget.

    Solve one linear program, then test fractions1,1/2,...,1/128 from the existing
    valid allocation toward that optimum. Every fraction closes algebraically;
    contact alone may force a smaller step or preserve the original route. No
    nonlinear cap fitting, radius tightening, seed guesses or further iterations.
    The caller must establish initial material/contact acceptance.
    """
    if cap_error(route) > 1e-7:
        raise ValueError("Start from a closed accepted material plan.")
    model = Model(route)
    columns, right, budget = model.equations()
    optimum = allocate(columns, right, model.costs, model.straight_indices, budget, checkpoint)
    if optimum is None:
        return route, None, 0.0, "linear_program_unresolved"
    original = model.initial
    if optimum.straight_length >= sum(original[i] for i in model.straight_indices) - 1e-8:
        return route, optimum, 0.0, "no_straight_reduction"
    for index in range(8):
        if checkpoint is not None:
            checkpoint()
        fraction = 2.0 ** (-index)
        values = tuple(max(0.0, a + fraction * (b - a)) for a, b in zip(original, optimum.values))
        if (
            model.straight_length(values)
            >= model.straight_length(original) - 1e-8 * route.targets.diameter_mm
        ):
            return route, optimum, 0.0, "numerical_straight_gain_floor"
        candidate = model.route(values)
        if (
            candidate is None
            or cap_error(candidate) > 1e-7
            or candidate.material_length_mm
            > route.material_length_mm + 1e-8 * route.targets.diameter_mm
        ):
            raise ArithmeticError("Affine allocation lost cap closure or material budget.")
        contact = inspect_contact(candidate, checkpoint=checkpoint)
        if record is not None:
            record(Trial(fraction, values, candidate, contact))
        if contact.status == "separated":
            return (
                candidate,
                optimum,
                fraction,
                "allocated" if index == 0 else "contact_limited_fraction",
            )
    return route, optimum, 0.0, "contact_fraction_budget"
