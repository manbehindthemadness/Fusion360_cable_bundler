"""
Solve tiny equality-constrained least-squares systems through orthogonal nullspace projection.
"""

from __future__ import annotations

import math

from experiments.experiment_ribbon_bend_reduction.closure import affine_projection


def least_squares(
    hard: list[list[float]],
    right: list[float],
    objective: list[list[float]],
    wanted: list[float],
    size: int,
) -> list[float] | None:
    """
    Minimize squared objective residual subject to exact affine equalities on at most seven slots.

    Build an orthonormal equality nullspace with two-pass Gram-Schmidt. The
    remaining normal system has at most four dimensions for full XYZ closure.
    Rank ambiguity/inconsistency returns unresolved; physical residual gates remain
    independent. Nonnegative active masks are owned by the allocation caller.
    """
    if size > 7 or any(len(row) != size for row in (*hard, *objective)):
        raise ValueError("Use at most seven matching straight-slot coordinates")
    base = affine_projection(hard, right, [0.0] * size)
    if base is None:
        return None
    nullspace: list[list[float]] = []
    for index in range(size):
        reference = [float(i == index) for i in range(size)]
        vector = affine_projection(hard, [0.0] * len(hard), reference)
        if vector is None:
            return None
        for _ in range(2):
            for previous in nullspace:
                coefficient = math.fsum(a * b for a, b in zip(vector, previous))
                vector = [a - coefficient * b for a, b in zip(vector, previous)]
        norm = math.sqrt(math.fsum(v * v for v in vector))
        if norm > 1e-10:
            nullspace.append([v / norm for v in vector])
    reduced = [[math.fsum(a * b for a, b in zip(row, v)) for v in nullspace] for row in objective]
    residual = [
        target - math.fsum(a * b for a, b in zip(row, base))
        for row, target in zip(objective, wanted)
    ]
    normal = [
        [math.fsum(row[i] * row[j] for row in reduced) for j in range(len(nullspace))]
        for i in range(len(nullspace))
    ]
    target = [
        math.fsum(row[i] * value for row, value in zip(reduced, residual))
        for i in range(len(nullspace))
    ]
    coefficients = affine_projection(normal, target, [0.0] * len(nullspace))
    if coefficients is None:
        return None
    return [
        value + math.fsum(v[i] * c for v, c in zip(nullspace, coefficients))
        for i, value in enumerate(base)
    ]
