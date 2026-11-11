"""
Eliminate only feasible straight transfers from one linearized angular closure.
"""

from __future__ import annotations

import math
from itertools import product
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

Vector = tuple[float, float, float]


def bounded_correction(
    columns: list[Vector],
    residual: Vector,
    rays: tuple[Vector, ...],
    lengths: tuple[float, ...],
    maximum_sum: float | None,
    checkpoint: Callable[[], None],
    *,
    minimum_length: float = 0.0,
) -> list[float] | None:
    """
    Minimize angular norm subject to the original nonnegative straight domain.

    Nearest-cone closure retains at most three positive straight slots. Enumerate
    their lower-bound faces and the optional total-travel face, at most16 tiny
    affine systems. Zero slots stay fixed; no material geometry is evaluated.
    Eliminate each face's free straight span, then verify that its reconstructed
    transfers obey all bounds and the full linear endpoint equation. Dependent
    or inconsistent systems remain unresolved. The caller retains its original
    angular cap, nonlinear trials and actual geometry acceptance gates.
    A native floor replaces zero as the lower face for already-positive support
    slots. Absent slots stay fixed. This retains the same sixteen face systems.
    """
    if len(rays) != len(lengths) or len(rays) > 3:
        raise ValueError("Use the nearest cone's at most three matching positive straight slots")
    if not math.isfinite(minimum_length) or minimum_length < 0:
        raise ValueError("Use a finite nonnegative straight-coordinate minimum")
    best: list[float] | None = None
    best_score: tuple[float, float] | None = None
    for pinned in product((False, True), repeat=len(rays)):
        for budget_active in (False, True) if maximum_sum is not None else (False,):
            checkpoint()
            transfer = [
                minimum_length - value if fixed else 0.0 for value, fixed in zip(lengths, pinned)
            ]
            free = [i for i, fixed in enumerate(pinned) if not fixed]
            directions = [list(rays[i]) for i in free]
            if budget_active and maximum_sum is not None:
                remaining = maximum_sum - math.fsum(lengths) - math.fsum(transfer)
                if not free:
                    if abs(remaining) > 1e-8:
                        continue
                else:
                    anchor = free[0]
                    transfer[anchor] = remaining
                    directions = [[a - b for a, b in zip(rays[i], rays[anchor])] for i in free[1:]]
            right = [
                -residual[a] - math.fsum(ray[a] * value for ray, value in zip(rays, transfer))
                for a in range(3)
            ]
            projected: list[list[float]] = []
            for column in columns:
                value = affine_projection(directions, [0.0] * len(directions), list(column))
                if value is None:
                    break
                projected.append(value)
            target = affine_projection(directions, [0.0] * len(directions), right)
            if target is None or len(projected) != len(columns):
                continue
            delta = affine_projection(
                [[column[a] for column in projected] for a in range(3)],
                target,
                [0.0] * len(columns),
            )
            if delta is None:
                continue
            remainder = [
                right[a] - math.fsum(column[a] * value for column, value in zip(columns, delta))
                for a in range(3)
            ]
            coefficients = affine_projection(
                [[direction[a] for direction in directions] for a in range(3)],
                remainder,
                [0.0] * len(directions),
            )
            if coefficients is None:
                continue
            for i, value in zip(free[1:] if budget_active else free, coefficients):
                transfer[i] += value
                if budget_active:
                    transfer[free[0]] -= value
            final = [length + value for length, value in zip(lengths, transfer)]
            if min(final, default=minimum_length) < minimum_length - 1e-9 or (
                maximum_sum is not None and math.fsum(final) > maximum_sum + 1e-8
            ):
                continue
            if any(
                abs(
                    residual[a]
                    + math.fsum(column[a] * value for column, value in zip(columns, delta))
                    + math.fsum(ray[a] * value for ray, value in zip(rays, transfer))
                )
                > 1e-8
                for a in range(3)
            ):
                continue
            score = (
                math.fsum(value * value for value in delta),
                math.fsum(value * value for value in transfer),
            )
            if best_score is None or score < best_score:
                best, best_score = delta, score
            if not any(pinned) and not budget_active:
                return delta
    return best
