"""
Retain67's width-aware search chart and deterministic cold initialization.

Carrier bounds are search limits,not physical cable lengths. Historical46 starts
keep their original allocator;64Halton starts use the wider sampling domain but
the same allocator. No targets,identity ordering or material rules are modified.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import seed_coordinates
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
    CompatiblePath,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK_WIDTH,
    bounded,
    maximum_length_ratio,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .families import Seed
from .solver import errors_for, screen_seeds


def carrier_maximum(case: EndpointCase) -> float:
    """
    Preserve the frozen wider domain independently of harness sphere measurements.
    """
    return max(6.0, maximum_length_ratio(case, BANK_WIDTH))


def bounds(case: EndpointCase) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Return the ten raw coordinate box bounds used by every bounded subproblem.
    """
    return (
        (-4 * math.pi,) * 5 + (-3.0,) * 4 + (1.0,),
        (4 * math.pi,) * 5 + (3.0,) * 4 + (carrier_maximum(case),),
    )


def integrate(
    case: EndpointCase,
    values: tuple[float, ...],
    steps: int,
    checkpoint: Callable[[], None],
) -> CompatiblePath:
    """
    Transport the unchanged near-limit material chart from the prescribed start.
    """
    if bounded(values, maximum_ratio=carrier_maximum(case)) != values:
        raise ValueError("Raw coordinates exceed the broad search domain.")
    raw = RoutingField(
        case.name,
        magnitude(difference(case.end, case.start)) * values[9],
        values[:4],
        (values[5], -values[5], values[6], values[7]),
        case.lines,
        case.diameter_mm,
        values[4],
        values[8],
    )
    initial = tuple(
        value
        for vector in (case.start, case.start_tangent, case.start_width)
        for value in (vector.x, vector.y, vector.z)
    )
    return integrate_compatible(
        CompatibleField(raw, BendMapping.NEAR_LIMIT), steps, checkpoint, initial=initial
    )


def descriptor(case: EndpointCase, path: CompatiblePath) -> tuple[float, ...]:
    """
    Sample the same17width-normalized A/center/B positions for family separation.
    """
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    return tuple(
        value / (2 * half)
        for i in range(17)
        for offset in (-half, 0.0, half)
        for point in (difference(path.lane(i / 16, offset)[0], case.start),)
        for value in (point.x, point.y, point.z)
    )


def _radical(index: int, base: int) -> float:
    """
    Reverse positive integer digits in one prime basis for a Halton coordinate.
    """
    value, factor = 0.0, 1.0 / base
    while index:
        index, digit = divmod(index, base)
        value += digit * factor
        factor /= base
    return value


def screen(case: EndpointCase, checkpoint: Callable[[], None]) -> tuple[Seed, ...]:
    """
    Screen110cold starts without fitting,contact discovery or cached geometry.
    """
    historical, _, _ = screen_seeds(case, checkpoint)
    seeds = list(historical)
    maximum = carrier_maximum(case)
    for index in range(1, 65):
        unit = [_radical(index, p) for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
        raw = (
            tuple((2 * value - 1) * 2 * math.pi for value in unit[:5])
            + tuple(2 * value - 1 for value in unit[5:9])
            + (1 + (maximum - 1) * unit[9],)
        )
        coordinates = seed_coordinates(case, raw)
        path = integrate(case, coordinates, 64, checkpoint)
        seeds.append(
            Seed(
                45 + index,
                coordinates,
                sum(value * value for value in errors_for(case, path)),
                descriptor(case, path),
            )
        )
    return tuple(seeds)
