"""
Couple signed material-turn limits and legal straight transfers to one angular closure system.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

from .angular_allocation import Vector


def _face(
    rows: list[list[float]], right: list[float], angular_count: int, straight_count: int
) -> list[float] | None:
    """
    Minimize angular motion on one affine face, then choose minimum straight transfer.

    Eliminate straight freedom before projecting the angular coordinates. This
    preserves the semidefinite objective without an arbitrary straight penalty.
    Dependent inconsistent equations remain unresolved.
    """
    dimension = len(rows)
    directions = [[row[angular_count + i] for row in rows] for i in range(straight_count)]
    columns = [[row[i] for row in rows] for i in range(angular_count)]
    projected = [
        affine_projection(directions, [0.0] * straight_count, column) for column in columns
    ]
    target = affine_projection(directions, [0.0] * straight_count, right)
    if target is None or any(column is None for column in projected):
        return None
    complete = [column for column in projected if column is not None]
    angular = affine_projection(
        [[column[d] for column in complete] for d in range(dimension)],
        target,
        [0.0] * angular_count,
    )
    if angular is None:
        return None
    residual = [
        value - math.fsum(row[i] * angular[i] for i in range(angular_count))
        for row, value in zip(rows, right)
    ]
    straight = affine_projection(
        [row[angular_count:] for row in rows], residual, [0.0] * straight_count
    )
    if straight is None:
        return None
    solution = angular + straight
    if any(
        abs(math.fsum(a * b for a, b in zip(row, solution)) - value) > 1e-8
        for row, value in zip(rows, right)
    ):
        return None
    return solution


def bounded_material_correction(
    columns: list[Vector],
    residual: Vector,
    rays: tuple[Vector, ...],
    lengths: tuple[float, ...],
    maximum_sum: float | None,
    turns: tuple[float, ...],
    turn_columns: tuple[tuple[float, ...], ...],
    checkpoint: Callable[[], None],
    *,
    minimum_length: float = 0.0,
) -> list[float] | None:
    """
    Find one bounded linear correction without aliasing a signed bend through a half turn.

    Share the original at-most16 affine faces between reference and material
    projections, including their initial faces. Violations alone open further faces; no angle
    grid, orientation fit or nonlinear correction runs here. Each face keeps
    exact endpoint equations and minimizes angular motion after eliminating
    straight freedom. The first feasible face is returned; bounded traversal
    does not establish a global constrained minimum or physical feasibility.
    Actual reallocation, finite material continuity and final proofs remain
    the caller's responsibility. Exhaustion or rank failure returns None.
    Preserve the original angular cap: a legal capped reference direction is
    returned unchanged. Otherwise the material projection closes only the
    cap-scaled endpoint residual, using the unspent faces. Full Newton closure
    must not be a prerequisite to a valid partial step. The caller still caps
    the returned direction before its original finite trials.
    """
    count, straight_count = len(columns), len(lengths)
    if (
        not 1 <= count <= 6
        or len(residual) != 3
        or any(len(column) != 3 for column in (*columns, *rays))
        or len(rays) != straight_count
        or straight_count > 3
        or len(turns) != len(turn_columns)
        or len(turns) > 6
        or any(len(row) != count for row in turn_columns)
        or minimum_length < 0
        or any(length < 0 for length in lengths)
        or any(abs(turn) > math.pi for turn in turns)
    ):
        raise ValueError("Use matching local turn derivatives and at most three positive straights")
    values = [*residual, *lengths, *turns, minimum_length]
    values += [value for column in (*columns, *rays, *turn_columns) for value in column]
    if any(not math.isfinite(value) for value in values) or (
        maximum_sum is not None and (not math.isfinite(maximum_sum) or maximum_sum < 0)
    ):
        raise ValueError("Material closure requires finite linear dimensions and bounds")
    rows = [[column[d] for column in columns] + [ray[d] for ray in rays] for d in range(3)]
    right = [-value for value in residual]
    turn_limits: list[tuple[list[float], float]] = []
    for angle, column in zip(turns, turn_columns):
        turn_limits.append((list(column) + [0.0] * straight_count, -math.pi - angle))
        turn_limits.append(([-value for value in column] + [0.0] * straight_count, angle - math.pi))
    limits: list[tuple[list[float], float]] = []
    for i, length in enumerate(lengths):
        limits.append(
            (
                [0.0] * count + [float(i == j) for j in range(straight_count)],
                minimum_length - length,
            )
        )
    if maximum_sum is not None:
        limits.append(([0.0] * count + [-1.0] * straight_count, math.fsum(lengths) - maximum_sum))
    reference, spent = _search(rows, right, limits, count, straight_count, 16, checkpoint)
    if reference is None:
        return None
    norm = math.sqrt(math.fsum(value * value for value in reference[:count]))
    factor = min(1.0, math.pi / (4 * norm)) if norm > 0 else 1.0
    capped = [factor * value for value in reference]
    if all(
        math.fsum(a * b for a, b in zip(row, capped)) >= lower - 1e-8 for row, lower in turn_limits
    ):
        return reference[:count]
    material, _ = _search(
        rows,
        [factor * value for value in right],
        turn_limits + limits,
        count,
        straight_count,
        16 - spent,
        checkpoint,
    )
    return None if material is None else material[:count]


def _search(
    rows: list[list[float]],
    right: list[float],
    limits: list[tuple[list[float], float]],
    angular_count: int,
    straight_count: int,
    maximum_faces: int,
    checkpoint: Callable[[], None],
) -> tuple[list[float] | None, int]:
    """
    Visit only violation-induced affine faces within the caller's unspent linear allocation.
    """
    pending: deque[tuple[int, ...]] = deque([()])
    seen: set[tuple[int, ...]] = {()}
    spent = 0
    for _ in range(maximum_faces):
        checkpoint()
        if not pending:
            return None, spent
        active = pending.popleft()
        spent += 1
        solution = _face(
            rows + [limits[i][0] for i in active],
            right + [limits[i][1] for i in active],
            angular_count,
            straight_count,
        )
        if solution is None:
            continue
        violations: list[tuple[float, int]] = []
        for i, (row, lower) in enumerate(limits):
            slack = math.fsum(a * b for a, b in zip(row, solution)) - lower
            if slack < -1e-8:
                norm = math.sqrt(math.fsum(value * value for value in row))
                violations.append((slack / max(norm, 1e-10), i))
        if not violations:
            return solution, spent
        for _, i in sorted(violations):
            if i in active:
                continue
            child = tuple(sorted((*active, i)))
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return None, spent
