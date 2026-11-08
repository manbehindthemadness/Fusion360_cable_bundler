"""
Minimize total runway length within one fixed-bend linear clearance problem.
"""

from __future__ import annotations

import math
from typing import Callable

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

from .active_projection import active_step
from .feature_plane import SignedJoints

Vertex = tuple[tuple[float, float], set[int]]


def _orthogonal(raw: list[float], prior: list[list[float]]) -> list[float]:
    """
    Remove existing orthonormal components twice using the established dense arithmetic convention.
    """
    for _ in range(2):
        for unit in prior:
            amount = math.fsum(a * b for a, b in zip(raw, unit))
            raw = [a - amount * b for a, b in zip(raw, unit)]
    return raw


def _nullspace(rows: list[list[float]], size: int) -> list[list[float]]:
    """
    Derive cap-preserving runway motion without testing geometric candidates.
    """
    basis: list[list[float]] = []
    for row in rows:
        vector = _orthogonal(list(row), basis)
        norm = math.sqrt(math.fsum(x * x for x in vector))
        if norm > 1e-10:
            basis.append([x / norm for x in vector])
    null: list[list[float]] = []
    for j in range(size):
        vector = _orthogonal([float(i == j) for i in range(size)], basis + null)
        norm = math.sqrt(math.fsum(x * x for x in vector))
        if norm > 1e-10:
            null.append([x / norm for x in vector])
    return null


def _clip(polygon: list[Vertex], axis: list[float], bound: float, number: int) -> list[Vertex]:
    """
    Clip one convex polygon and retain the exact active constraint identities at its vertices.
    """
    clipped: list[Vertex] = []
    for j, (start, active_start) in enumerate(polygon):
        end, active_end = polygon[(j + 1) % len(polygon)]
        ds = math.fsum(x * y for x, y in zip(axis, start)) - bound
        de = math.fsum(x * y for x, y in zip(axis, end)) - bound
        if ds <= 0:
            clipped.append((start, active_start | ({number} if ds == 0 else set())))
        if (ds < 0 < de) or (de < 0 < ds):
            fraction = ds / (ds - de)
            point = (
                start[0] + fraction * (end[0] - start[0]),
                start[1] + fraction * (end[1] - start[1]),
            )
            clipped.append((point, (active_start & active_end) | {number}))
        elif ds > 0 and de == 0:
            clipped.append((end, active_end | {number}))
    return clipped


def shortest_run_step(
    model: SignedJoints,
    values: tuple[float, ...],
    rows: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> tuple[float, ...] | None:
    """
    Project once, then minimize summed runways over a two-dimensional cap nullspace if available.

    Only straight coordinates may be free. Start with the existing bounded
    sixteen-step projector; unsupported nullity or failed vertex arithmetic keeps
    that vector. In two dimensions, clip member planes and nonnegative runways
    against a dominating length bound. The finite starting box follows from the
    known feasible nonnegative sum, so it cannot exclude a shorter solution.
    Active zero slots are solved as model equations, never welded or clamped.
    This algebra selects one vector before any route or physical certificate;
    the caller owns all clocks, logical updates and strict output checks.
    """
    if any(index % 4 for index in model.indices):
        raise ValueError("Runway minimization requires fixed bend coordinates")
    feasible = active_step(model, values, rows, residual, checkpoint)
    if feasible is None:
        return None
    size, caps = len(values), rows[:6]
    base = affine_projection(caps, [-r for r in residual[:6]], [0.0] * size)
    if base is None:
        return None
    null = _nullspace(caps, size)
    if len(null) != 2:
        return feasible
    inequalities = [(list(row), r) for row, r in zip(rows[6:], residual[6:])]
    feature_count = len(inequalities)
    inequalities += [
        ([-float(i == j) for i in range(size)], -value) for j, value in enumerate(values)
    ]
    feasible_length = math.fsum(a + b for a, b in zip(values, feasible))
    inequalities.append(([1.0] * size, math.fsum(values) - feasible_length))
    objective = [math.fsum(n) for n in null]
    if math.hypot(*objective) < 1e-12:
        return feasible
    radius = (
        feasible_length
        + math.sqrt(math.fsum(v * v for v in values))
        + math.sqrt(math.fsum(v * v for v in base))
    )
    polygon: list[Vertex] = [
        ((-radius, -radius), {-1, -3}),
        ((radius, -radius), {-2, -3}),
        ((radius, radius), {-2, -4}),
        ((-radius, radius), {-1, -4}),
    ]
    for number, (row, r) in enumerate(inequalities):
        checkpoint()
        axis = [math.fsum(x * y for x, y in zip(row, n)) for n in null]
        bound = -r - math.fsum(x * y for x, y in zip(row, base))
        polygon = _clip(polygon, axis, bound, number)
        if not polygon:
            return feasible
    point, active = min(
        polygon,
        key=lambda item: (
            math.fsum(a * b for a, b in zip(objective, item[0])),
            math.fsum(x * x for x in item[0]),
        ),
    )
    proposed = [
        v + b + math.fsum(n[j] * z for n, z in zip(null, point))
        for j, (v, b) in enumerate(zip(values, base))
    ]
    zeros = {
        number - feature_count
        for number in active
        if feature_count <= number < feature_count + size
    }
    free = [j for j in range(size) if j not in zeros]
    equations = caps + [inequalities[j][0] for j in sorted(active) if j >= 0]
    rr = list(residual[:6]) + [inequalities[j][1] for j in sorted(active) if j >= 0]
    right = [-r + math.fsum(a * v for a, v in zip(row, values)) for row, r in zip(equations, rr)]
    solved = affine_projection(
        [[row[j] for j in free] for row in equations], right, [proposed[j] for j in free]
    )
    if solved is None:
        return feasible
    trial = [0.0] * size
    for j, value in zip(free, solved):
        trial[j] = value
    if any(value < 0 for value in trial):
        return feasible
    return tuple(a - b for a, b in zip(trial, values))
