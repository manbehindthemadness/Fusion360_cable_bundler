"""
Fit fixed endpoints with67's bounded quadratic steps and actual trial scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .broad_chart import bounds, carrier_maximum, integrate
from .families import Seed
from .solver import errors_for


@dataclass(frozen=True)
class FitWork:
    """
    Freeze per-grid rounds and the inclusive derivative/trial transport ceiling.
    """

    coarse: int
    fine: int
    transports: int


SHORT = FitWork(5, 1, 74)
DEEP = FitWork(36, 6, 506)
POLISH = FitWork(0, 4, 50)


def refine(
    case: EndpointCase,
    seed: Seed,
    checkpoint: Callable[[], None],
    work: FitWork,
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Preserve cold-family fitting arithmetic while solving box bounds inside the QP.

    Return unresolved fits unchanged. Every probe/trial counts;actual objective
    decrease controls acceptance. No endpoint snapping or collision exemption.
    """
    if min(work.coarse, work.fine) < 0 or work.transports < 2:
        raise ValueError("Fit work requires nonnegative rounds and two final transports.")
    started = perf_counter()
    values = seed.coordinates
    maximum = carrier_maximum(case)
    lower, upper = bounds(case)
    evaluations = 0
    stages: list[dict[str, Any]] = []
    qps: list[dict[str, Any]] = []

    def observe(
        parameters: tuple[float, ...], grid: int
    ) -> tuple[CompatiblePath, tuple[float, ...]]:
        """
        Count each required transport before computing endpoint/local-rule errors.
        """
        nonlocal evaluations
        if evaluations >= work.transports:
            raise RuntimeError("Box fit transport cap.")
        evaluations += 1
        path = integrate(case, parameters, grid, checkpoint)
        return path, errors_for(case, path)

    for grid, rounds, tolerance in ((64, work.coarse, 1e-6), (512, work.fine, 1e-12)):
        path, errors = observe(values, grid)
        score = sum(value * value for value in errors)
        damping = 1e-3 if grid == 64 else 1e-8
        history = [score]
        trials: list[dict[str, Any]] = []
        for _ in range(rounds):
            if max(abs(value) for value in errors) < tolerance:
                break
            columns = []
            for index in range(10):
                _, parameters = probe_coordinates(values, index, maximum)
                _, observed = observe(parameters, grid)
                step = parameters[index] - values[index]
                columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
            quadratic = constrained_step(
                columns, errors, damping, [()] * 10, (), values, lower, upper
            )
            qps.append(dict(grid=grid, iterations=quadratic.iterations, status=quadratic.status))
            accepted = False
            for fraction in (1.0, 0.5):
                _, proposed = trial_coordinates(values, quadratic.values, fraction, maximum)
                candidate, observed = observe(proposed, grid)
                after = sum(value * value for value in observed)
                trials.append(
                    dict(before=score, after=after, accepted=after < score, proposed=proposed)
                )
                if after < score:
                    path, errors, score, values = candidate, observed, after, proposed
                    accepted = True
                    break
            history.append(score)
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append(dict(grid=grid, history=history, trials=trials))
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        strict_endpoint_gate=max(metrics.values()) <= 1e-8,
        coordinates=values,
        score=score,
        evaluations=evaluations,
        seconds=perf_counter() - started,
        stages=stages,
        qp_steps=qps,
    )
    return path, metrics
