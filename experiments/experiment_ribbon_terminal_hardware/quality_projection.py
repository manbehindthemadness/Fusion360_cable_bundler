"""
Project one joint correction onto caps and at most three scalar quality/clearance inequalities.
"""

from __future__ import annotations

import math
from typing import Callable

from experiments.experiment_ribbon_fold_relaxation.steps import projected

from .feature_plane import SignedJoints


def quality_step(
    model: SignedJoints,
    values: tuple[float, ...],
    jacobian: list[list[float]],
    residual: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> tuple[float, ...] | None:
    """
    Find the least-norm feasible linear correction without forcing cleared bounds to equality.

    The first six rows are ordered cap equalities; the remaining one to three
    rows are signed violations, nonpositive when satisfied. Enumerate at most
    eight scalar active subsets, retaining the shared coordinate-bound projection.
    These are algebraic projections of one Jacobian, not geometry candidates.
    Return None if no projection meets every linearized bound. Final nonlinear
    closure and physical certificates remain the caller's responsibility.
    """
    if (
        not 7 <= len(residual) <= 9
        or len(jacobian) != len(residual)
        or any(len(row) != len(values) for row in jacobian)
    ):
        raise ValueError("Use six cap equations and one to three matching scalar inequalities")
    best, best_cost = None, math.inf
    for mask in range(1 << (len(residual) - 6)):
        checkpoint()
        active = list(range(6)) + [i for i in range(6, len(residual)) if mask & (1 << (i - 6))]
        proposal = projected(
            model,
            values,
            [jacobian[i] for i in active],
            [-residual[i] for i in active],
            [0.0] * len(values),
        )
        if proposal is None or any(
            residual[i] + math.fsum(a * b for a, b in zip(jacobian[i], proposal)) > 1e-12
            for i in range(6, len(residual))
        ):
            continue
        cost = math.fsum(value * value for value in proposal)
        if cost < best_cost:
            best, best_cost = proposal, cost
    return best
