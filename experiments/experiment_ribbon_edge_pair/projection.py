"""
Apply bounded minimum-change corrections driven by the two active edge limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

from .geometry import EdgeChart
from .measure import PairMeasure, measure


def _solve(matrix: list[list[float]], right: list[float]) -> tuple[float, ...]:
    """
    Solve one damped positive system with partial pivoting; singularity stops work.
    """
    rows = [row[:] + [value] for row, value in zip(matrix, right)]
    size = len(rows)
    for i in range(size):
        pivot = max(range(i, size), key=lambda k: abs(rows[k][i]))
        rows[i], rows[pivot] = rows[pivot], rows[i]
        divisor = rows[i][i]
        if abs(divisor) <= 1e-18:
            raise ValueError("Singular paired-edge correction system.")
        rows[i] = [value / divisor for value in rows[i]]
        for j in range(size):
            if j == i:
                continue
            factor = rows[j][i]
            rows[j] = [a - factor * b for a, b in zip(rows[j], rows[i])]
    return tuple(row[-1] for row in rows)


@dataclass(frozen=True)
class Correction:
    """
    Retain the original curve, every evaluation and accepted deviations without retries.
    """

    curve: BoundaryCurve
    values: tuple[float, ...]
    measured: PairMeasure
    evaluations: int
    accepted: int
    disposition: str


def correct(
    chart: EdgeChart,
    checkpoint: Callable[[], None],
    observe: Callable[[BoundaryCurve, PairMeasure, str], None],
    *,
    rounds: int = 24,
) -> Correction:
    """
    Follow local constraint gradients from supplied geometry, never another route family.

    Endpoint conditions are encoded in the chart. Each update solves a damped
    minimum-change system using the two pinch violations only. Backtracking tests
    shorter versions of that correction, not seed/path guesses. A separate513station
    measurement is returned; exhaustion is unresolved, not impossible.
    Caller checkpoints supply time/RSS/source limits and interrupt before further work.
    """
    if not 0 <= rounds <= 96:
        raise ValueError("Paired-edge correction supports at most96bounded rounds.")
    limit = PinchLimit(99.6)
    values = (0.0,) * 16
    evaluations, accepted, damping = 0, 0, 0.01

    def evaluate(
        candidate: tuple[float, ...], stations: int, stage: str
    ) -> tuple[BoundaryCurve, PairMeasure]:
        """
        Retain each measured proposal before scheduling another local correction.
        """
        nonlocal evaluations
        checkpoint()
        shape = chart.curve(candidate)
        measured = measure(chart, shape, stations, limit)
        evaluations += 1
        observe(shape, measured, stage)
        return shape, measured

    curve, current = evaluate(values, 129, "original")
    for iteration in range(rounds):
        if current.failed == 0:
            break
        columns = []
        for i in range(16):
            probe = list(values)
            probe[i] += 1e-5
            _, measured = evaluate(tuple(probe), 129, f"gradient:{iteration}:{i}")
            columns.append(
                tuple((b - a) / 1e-5 for a, b in zip(current.residual, measured.residual))
            )
        matrix = [
            [
                sum(a * b for a, b in zip(left, right)) + (damping if i == j else 0)
                for j, right in enumerate(columns)
            ]
            for i, left in enumerate(columns)
        ]
        right = [-sum(a * b for a, b in zip(column, current.residual)) for column in columns]
        step = _solve(matrix, right)
        norm = math.sqrt(sum(value * value for value in step))
        factor = min(1.0, 0.5 / norm) if norm else 1.0
        changed = False
        for division in range(8):
            proposed = tuple(a + factor * b / 2**division for a, b in zip(values, step))
            shape, measured = evaluate(proposed, 129, f"deviation:{iteration}:{division}")
            if measured.score < current.score:
                values, curve, current = proposed, shape, measured
                changed = True
                accepted += 1
                damping = max(1e-8, damping / 2)
                break
        if not changed:
            damping *= 10
    curve, checked = evaluate(values, 513, "denser-check")
    return Correction(
        curve,
        values,
        checked,
        evaluations,
        accepted,
        "sampled limits satisfied" if checked.failed == 0 else "unresolved",
    )
