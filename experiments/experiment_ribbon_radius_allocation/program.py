"""
Solve the bounded four-equation linear allocation without iterative route fitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection


@dataclass(frozen=True)
class Solution:
    """
    Retain the chosen allocation and all finite linear-solver work counts.
    """

    values: tuple[float, ...]
    bases_evaluated: int
    feasible_bases: int
    straight_length: float
    variable_material_length: float


def allocate(
    columns: tuple[tuple[float, float, float], ...],
    displacement: tuple[float, float, float],
    costs: tuple[float, ...],
    straights: tuple[int, ...],
    budget: float,
    checkpoint: Callable[[], None] | None = None,
) -> Solution | None:
    """
    Minimize straight travel, then material length, with nonnegative coordinates.

    Three position equations and one material-budget/slack equation imply a
    basic optimum with at most four positive coordinates. Enumerate supports
    of size0..4, including degenerate supports; bounded by2517supports for at most
    sixteen coordinates including slack. Extra dependent-support projections are
    feasible points, never accepted as evidence of physical contact compliance.
    Scores rounded to1e-10 only break numerical ties before fixed coordinate order.
    """
    if len(columns) != len(costs) or len(columns) > 15 or budget < 0 or not math.isfinite(budget):
        raise ValueError("Use matching finite allocation dimensions, at most fifteen variables.")
    if any(not math.isfinite(value) or value <= 0 for value in costs) or any(
        i < 0 or i >= len(costs) for i in straights
    ):
        raise ValueError("Positive material costs and valid straight indices required.")
    full_columns = tuple(tuple(column) + (cost,) for column, cost in zip(columns, costs)) + (
        (0.0, 0.0, 0.0, 1.0),
    )
    right = list(displacement) + ([budget])
    best: tuple[float, ...] | None = None
    best_score: tuple[float, float, tuple[float, ...]] | None = None
    evaluated = 0
    feasible = 0
    for count in range(min(4, len(full_columns)) + 1):
        for support in combinations(range(len(full_columns)), count):
            if checkpoint is not None and evaluated % 64 == 0:
                checkpoint()
            evaluated += 1
            rows = [[full_columns[index][axis] for index in support] for axis in range(4)]
            projected = affine_projection(rows, right, [0.0] * len(support))
            if projected is None or min(projected, default=0) < -1e-9:
                continue
            values = [0.0] * len(full_columns)
            for index, value in zip(support, projected):
                values[index] = max(0.0, value)
            if any(
                abs(
                    math.fsum(column[axis] * value for column, value in zip(full_columns, values))
                    - right[axis]
                )
                > 1e-8
                for axis in range(4)
            ):
                continue
            feasible += 1
            straight = math.fsum(values[i] for i in straights)
            material = math.fsum(value * cost for value, cost in zip(values, costs))
            score = (
                round(straight, 10),
                round(material, 10),
                tuple(round(value, 10) for value in values[:-1]),
            )
            if best_score is None or score < best_score:
                best, best_score = tuple(values[:-1]), score
    if best is None:
        return None
    return Solution(
        best,
        evaluated,
        feasible,
        math.fsum(best[i] for i in straights),
        math.fsum(value * cost for value, cost in zip(best, costs)),
    )
