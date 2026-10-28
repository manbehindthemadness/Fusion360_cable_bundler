"""
Test width-relative carrier expansion while fitting the remaining shape coordinates.

This warm diagnostic is not an active solver policy. Intermediate fits may collide;
callers must independently check contact, intrinsic rules and terminal closure.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart
from .solver import errors_for


def expanded_ratios(case: EndpointCase, original: float) -> tuple[float, ...]:
    """
    Add half, one and two occupied widths within the existing carrier search bounds.
    """
    chord = magnitude(difference(case.end, case.start))
    width = (case.lines + 0.2) * case.diameter_mm
    maximum = broad_chart.carrier_maximum(case)
    if chord <= 0 or not 1 <= original <= maximum:
        raise ValueError("Expansion needs a nonzero chord and an in-bounds carrier.")
    return tuple(dict.fromkeys(min(maximum, original + n * width / chord) for n in (0.5, 1, 2)))


def refine(
    case: EndpointCase,
    original: tuple[float, ...],
    ratio: float,
    checkpoint: Callable[[], None],
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Hold carrier fixed for twelve coarse and eight fine bounded shape-fitting rounds.

    At most262 transports are used, including derivatives and three step fractions.
    Three stalled rounds stop each grid. Contact remains a final independent gate,
    not an optimization residual or a constraint on the parameter-space journey.
    """
    began = perf_counter()
    values = original[:9] + (ratio,)
    lower, upper = broad_chart.bounds(case)
    maximum = broad_chart.carrier_maximum(case)
    evaluations = 0
    trials: list[dict[str, Any]] = []

    def transport(parameters: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Charge every candidate and derivative against the frozen transport budget.
        """
        nonlocal evaluations
        if evaluations >= 262:
            raise RuntimeError("Expansion transport cap")
        evaluations += 1
        return broad_chart.integrate(case, parameters, grid, checkpoint)

    for grid, rounds in ((64, 12), (512, 8)):
        path = transport(values, grid)
        errors = errors_for(case, path)
        score = sum(v * v for v in errors)
        damping, stalled = 1e-3 if grid == 64 else 1e-8, 0
        for outer in range(rounds):
            if max(abs(v) for v in errors) < (1e-6 if grid == 64 else 1e-9):
                break
            columns = []
            for index in range(9):
                _, parameters = probe_coordinates(values, index, maximum)
                observed = errors_for(case, transport(parameters, grid))
                step = parameters[index] - values[index]
                columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
            result = constrained_step(
                columns, errors, damping, [()] * 9, (), values[:9], lower[:9], upper[:9]
            )
            accepted = False
            for fraction in (1.0, 0.5, 0.25):
                _, proposed = trial_coordinates(values, result.values + (0.0,), fraction, maximum)
                candidate = transport(proposed, grid)
                observed = errors_for(case, candidate)
                after = sum(v * v for v in observed)
                take = after < score
                trials.append(
                    dict(
                        grid=grid,
                        outer=outer,
                        before=score,
                        after=after,
                        accepted=take,
                        coordinates=proposed,
                    )
                )
                if take:
                    values, path, errors, score = proposed, candidate, observed, after
                    accepted = True
                    break
            damping = max(1e-12, damping / 3) if accepted else damping * 10
            stalled = 0 if accepted else stalled + 1
            if stalled >= 3:
                break
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        coordinates=values,
        evaluations=evaluations,
        seconds=perf_counter() - began,
        score=sum(v * v for v in errors_for(case, path)),
        trials=trials,
        fixed_carrier_ratio=ratio,
    )
    return path, metrics
