"""
Fit fixed endpoint poses inside the compatible-edge coordinate chart.

Every raw coordinate generates a locally regular strip before endpoint scoring.
This bounded experiment supplies no elastic energy,contact repair or native build.
"""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import difference, magnitude

from .compatible_strip import CompatibleField, CompatiblePath, integrate_compatible
from .director_route_objective import free_penalties
from .director_routing_field import RoutingField
from .director_seed_bank import candidates
from .director_shooting import (
    BANK_WIDTH,
    SeedMethod,
    bounded,
    damped_step,
    endpoint_metrics,
    maximum_length_ratio,
    residual,
    seed,
)
from .endpoint_first import EndpointCase, controls


def field_for(case: EndpointCase, values: tuple[float, ...]) -> CompatibleField:
    """
    Interpret bounded raw coordinates with the same dimensions and fixed targets.
    """
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    if bounded(values, maximum_ratio=maximum) != values:
        raise ValueError("Compatible shooting coordinates exceed the frozen domain.")
    length = magnitude(difference(case.end, case.start)) * values[9]
    raw = RoutingField(
        case.name,
        length,
        (values[0], values[1], values[2], values[3]),
        (values[5], -values[5], values[6], values[7]),
        case.lines,
        case.diameter_mm,
        values[4],
        values[8],
    )
    return CompatibleField(raw)


def solve(
    case: EndpointCase,
    checkpoint: Callable[[], None],
    *,
    stage_observer: Callable[[int, CompatiblePath], None] | None = None,
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Screen46direct seeds and refine one with18coarse/3fine rounds,max254fit probes.

    Each seed integrates once at64steps. Its carrier budget comes from endpoint
    distance and generic Fourier bend/ruling magnitudes;no algebraic rescaling of
    an already integrated path,stored solutions or witness lengths enter ranking.
    Persistent endpoint/policy objectives decrease under full/half steps,norm<=1.5.
    Strict actual endpoint gates remain1e-8;final geometry audits are independent.
    """
    controls(case)
    started = perf_counter()
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    chord = magnitude(difference(case.end, case.start))
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half, case.diameter_mm / 2)
    initial = (
        case.start.x,
        case.start.y,
        case.start.z,
        case.start_tangent.x,
        case.start_tangent.y,
        case.start_tangent.z,
        case.start_width.x,
        case.start_width.y,
        case.start_width.z,
    )

    def integrate_values(parameters: tuple[float, ...], steps: int) -> CompatiblePath:
        """
        Transport exactly the field that will be scored or returned.
        """
        checkpoint()
        return integrate_compatible(field_for(case, parameters), steps, checkpoint, initial=initial)

    def errors_for(candidate_path: CompatiblePath) -> tuple[float, ...]:
        """
        Keep containment and existing search margins active at both grids.
        """
        return residual(case, candidate_path) + free_penalties(case, candidate_path)

    best_values: tuple[float, ...] | None = None
    best = math.inf
    rankings = []
    seed_started = perf_counter()
    for index, raw in enumerate(candidates() + (seed(case), seed(case, SeedMethod.CORKSCREW))):
        bend_bound = sum(abs(v) for v in raw[:5])
        ruling_bound = 2 * math.pi * (abs(raw[5]) + abs(raw[6]) + 2 * abs(raw[7]) + 2 * abs(raw[8]))
        required_budget = 1.2 * (bend_bound * reach / 0.78 + 2 * half * ruling_bound)
        ratio = min(maximum, max(1.0, raw[9], required_budget / chord))
        coordinates = raw[:9] + (ratio,)
        path = integrate_values(coordinates, 64)
        errors = errors_for(path)
        error = sum(v * v for v in errors)
        rankings.append({"index": index, "score": error, "carrier_ratio": ratio})
        if error < best:
            best_values, best = coordinates, error
    if best_values is None:
        raise RuntimeError("No finite compatible seed in the fixed bank.")
    values: tuple[float, ...] = best_values
    seed_seconds = perf_counter() - seed_started
    evaluations = 0
    stages = []

    def observe(
        parameters: tuple[float, ...], steps: int
    ) -> tuple[CompatiblePath, tuple[float, ...]]:
        """
        Count every fit evaluation without adding a feasibility audit or repair loop.
        """
        nonlocal evaluations
        evaluations += 1
        evaluated_path = integrate_values(parameters, steps)
        return evaluated_path, errors_for(evaluated_path)

    for grid, rounds, tolerance in ((64, 18, 1e-6), (512, 3, 1e-12)):
        stage_started = perf_counter()
        path, errors = observe(values, grid)
        error = sum(v * v for v in errors)
        history = [error]
        damping = 1e-3 if grid == 64 else 1e-8
        for _ in range(rounds):
            if max(abs(v) for v in errors) < tolerance:
                break
            if (
                grid == 512
                and max(endpoint_metrics(case, path).values()) <= 1e-8
                and not any(errors[9:])
            ):
                break
            columns = []
            for i in range(10):
                limit = 4 * math.pi if i < 5 else 3.0 if i < 9 else maximum
                probe = list(values)
                probe[i] += -1e-5 if values[i] >= limit else 1e-5
                probe_values = bounded(tuple(probe), maximum_ratio=maximum)
                _, probe_errors = observe(probe_values, grid)
                difference_step = probe_values[i] - values[i]
                column = tuple((a - b) / difference_step for a, b in zip(probe_errors, errors))
                columns.append(column)
            delta = damped_step(columns, errors, damping)
            norm = math.sqrt(sum(v * v for v in delta))
            scale = min(1.0, 1.5 / norm) if norm else 1.0
            accepted = False
            for fraction in (1.0, 0.5):
                proposed = bounded(
                    tuple(a + fraction * scale * b for a, b in zip(values, delta)),
                    maximum_ratio=maximum,
                )
                candidate, observed = observe(proposed, grid)
                candidate_error = sum(v * v for v in observed)
                if candidate_error < error:
                    values, path, errors, error = proposed, candidate, observed, candidate_error
                    accepted = True
                    break
            history.append(error)
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append({"grid": grid, "history": history, "seconds": perf_counter() - stage_started})
        if stage_observer is not None:
            stage_observer(grid, path)
    if evaluations > 254 or len(rankings) != 46:
        raise RuntimeError("Compatible shooting work bound exceeded.")
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        endpoint_gate_passed=max(metrics.values()) <= 1e-8,
        evaluations=evaluations,
        seed_screenings=len(rankings),
        seed_ranking=rankings,
        seed_seconds=seed_seconds,
        stages=stages,
        coordinates=values,
        carrier_budget_mm=path.field.carrier_length_mm,
        seconds=perf_counter() - started,
    )
    return path, metrics
