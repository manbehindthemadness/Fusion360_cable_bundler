"""
Test carrier search-domain expansion with unchanged compatible ribbon geometry.

This host-independent experiment requires the repository SDK and no Fusion API.
Callers freeze fixed cases, starting coordinates, multiplier ladders and elapsed
limits before fitting. Multipliers change search bounds, not physical bend limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
    CompatiblePath,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_shooting import bounded, endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart
from experiments.experiment_ribbon_route_discovery.solver import errors_for


@dataclass(frozen=True)
class SearchDomain:
    """
    Expand only the upper carrier coordinate and retain all other chart bounds.
    """

    multiplier: float = 1.0

    def __post_init__(self) -> None:
        """
        Restrict this experiment to its declared finite one-to-three ladder.
        """
        if not math.isfinite(self.multiplier) or not 1 <= self.multiplier <= 3:
            raise ValueError("Search expansion must be finite and between one and three.")

    def maximum(self, case: EndpointCase) -> float:
        """
        Scale a dimensionless search limit without consulting the harness sphere.
        """
        return self.multiplier * broad_chart.carrier_maximum(case)

    def bounds(self, case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Preserve the first nine bounds and the original lower carrier bound.
        """
        lower, upper = broad_chart.bounds(case)
        return lower, upper[:9] + (self.maximum(case),)

    def integrate(
        self,
        case: EndpointCase,
        coordinates: tuple[float, ...],
        steps: int,
        checkpoint: Callable[[], None],
    ) -> CompatiblePath:
        """
        Validate the search box before transporting the unchanged near-limit model.
        """
        if (
            len(coordinates) != 10
            or bounded(coordinates, maximum_ratio=self.maximum(case)) != coordinates
        ):
            raise ValueError("Coordinates outside the declared search domain.")
        return transport(case, coordinates, steps, checkpoint)


# Matched experiments deliberately preserve the retained transport arithmetic.
# noinspection DuplicatedCode
def transport(
    case: EndpointCase,
    coordinates: tuple[float, ...],
    steps: int,
    checkpoint: Callable[[], None],
) -> CompatiblePath:
    """
    Transport already validated coordinates without changing their stored values.

    Host replay may call this only after recording a bounded machine-rounding
    discrepancy; raw model dimensions and finite coefficients remain validated.
    """
    raw = RoutingField(
        case.name,
        magnitude(difference(case.end, case.start)) * coordinates[9],
        (coordinates[0], coordinates[1], coordinates[2], coordinates[3]),
        (coordinates[5], -coordinates[5], coordinates[6], coordinates[7]),
        case.lines,
        case.diameter_mm,
        coordinates[4],
        coordinates[8],
    )
    initial = tuple(
        value
        for vector in (case.start, case.start_tangent, case.start_width)
        for value in (vector.x, vector.y, vector.z)
    )
    return integrate_compatible(
        CompatibleField(raw, BendMapping.NEAR_LIMIT), steps, checkpoint, initial=initial
    )


# Keep the baseline QP and line-search arithmetic fixed in this bounded ablation.
# noinspection DuplicatedCode
def refine(
    case: EndpointCase,
    coordinates: tuple[float, ...],
    domain: SearchDomain,
    checkpoint: Callable[[], None],
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Fit ten coarse/three fine rounds with at most158 counted transports per rung.

    Independent rungs must receive identical saved coordinates. These are warm
    sensitivity measurements, not cold solves or a certified feasibility threshold.
    Checkpoint failures propagate; no source, resource or geometry errors are hidden.
    """
    started = perf_counter()
    values = coordinates
    maximum = domain.maximum(case)
    lower, upper = domain.bounds(case)
    evaluations = 0
    history: list[dict[str, Any]] = []

    def observe(
        observed_coordinates: tuple[float, ...], integration_grid: int
    ) -> tuple[CompatiblePath, tuple[float, ...]]:
        """
        Count probes and trials before evaluating unchanged endpoint/rule errors.
        """
        nonlocal evaluations
        checkpoint()
        if evaluations >= 158:
            raise RuntimeError("Search-domain fit transport cap.")
        evaluations += 1
        observed_path = domain.integrate(case, observed_coordinates, integration_grid, checkpoint)
        return observed_path, errors_for(case, observed_path)

    for grid, rounds, tolerance in ((64, 10, 1e-6), (512, 3, 1e-12)):
        path, errors = observe(values, grid)
        score = sum(v * v for v in errors)
        damping = 1e-3 if grid == 64 else 1e-8
        for _ in range(rounds):
            if max(abs(v) for v in errors) < tolerance:
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
            accepted = False
            for fraction in (1.0, 0.5):
                _, proposed = trial_coordinates(values, quadratic.values, fraction, maximum)
                candidate, observed = observe(proposed, grid)
                after = sum(v * v for v in observed)
                if after < score:
                    path, errors, score, values = candidate, observed, after, proposed
                    accepted = True
                    break
            history.append(dict(grid=grid, score=score, accepted=accepted))
            damping = max(1e-12, damping / 3) if accepted else damping * 10
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        coordinates=values,
        score=score,
        evaluations=evaluations,
        seconds=perf_counter() - started,
        history=history,
        multiplier=domain.multiplier,
        carrier_upper=maximum,
    )
    return path, metrics
