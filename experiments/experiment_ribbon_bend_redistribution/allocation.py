"""
Move sampled turning demand from tight to loose portions of one signed bend region.

Regions organize a search proposal,not geometric joints or a physical turn-event
certificate. The unchanged compatible field remains authoritative for geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
)
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step


@dataclass(frozen=True)
class Allocation:
    """
    Retain requested turning transfer and its bounded five-coefficient projection.

    Targets conserve sampled signed turning inside one region. Fourier projection
    can spread the change beyond it;neither conservation after projection nor
    endpoint closure is assumed. Both require fresh measurements after transport.
    """

    reason: str
    peak: int
    recipient: int
    region: tuple[int, int]
    fractions: tuple[float, ...]
    turns: tuple[float, ...]
    limits: tuple[float, ...]
    target_turns: tuple[float, ...]
    coordinates: tuple[float, ...]
    proposed: tuple[float, ...]
    quadratic_status: str


def _inverse_turn(turn: float, limit: float) -> float:
    """
    Invert the existing near-limit shoulder for a strictly interior proposal.

    This chooses a raw request;it does not change the physical map or its limit.
    """
    knee, shoulder = 0.9 * limit, 0.1 * limit
    if abs(turn) <= knee:
        return turn
    fraction = (abs(turn) - knee) / shoulder
    if not 0 <= fraction < 1:
        raise ValueError("Proposed turning must stay strictly inside its existing limit.")
    return math.copysign(knee + shoulder * fraction / math.sqrt(1 - fraction**2), turn)


def propose(field: CompatibleField, coordinates: tuple[float, ...]) -> Allocation | None:
    """
    Allocate half the imbalance on33stations,then project within existing bend bounds.

    Call only for an unresolved/stalled route. Require at least60%peak utilization
    and25percentage-point spread within its contiguous signed region. Near90%
    labels saturation;otherwise the trigger is stalled imbalance. Equal/neutral
    regions receive no proposal. Ruling,carrier and terminal inputs remain fixed.
    No integration,contact audit,search-domain expansion or geometry repair occurs.
    """
    if field.bend_mapping is not BendMapping.NEAR_LIMIT:
        raise ValueError("Redistribution requires the retained near-limit geometry map.")
    if len(coordinates) != 10 or not all(math.isfinite(v) for v in coordinates):
        raise ValueError("Redistribution needs ten finite coordinates.")
    raw_coordinates = (*field.raw.bending, field.raw.extra_bending)
    if tuple(coordinates[:5]) != raw_coordinates:
        raise ValueError("Bend coordinates disagree with the observed field.")
    if coordinates[5:9] != (
        field.raw.ruling[0],
        field.raw.ruling[2],
        field.raw.ruling[3],
        field.raw.extra_ruling,
    ):
        raise ValueError("Ruling coordinates disagree with the observed field.")
    fractions = tuple(i / 32 for i in range(33))
    samples = tuple(field.carrier(u) for u in fractions)
    observed_limits = tuple(field.turn_limit(value) for value in samples)
    if any(value is None for value in observed_limits):
        return None
    limits = tuple(value for value in observed_limits if value is not None)
    turns = tuple(value.turn for value in samples)
    utilization = tuple(abs(turn) / limit for turn, limit in zip(turns, limits))
    peak = max(range(33), key=lambda i: utilization[i])
    if utilization[peak] < 0.6:
        return None
    sign = math.copysign(1, turns[peak])
    lower = upper = peak
    while lower > 0 and turns[lower - 1] * sign > 1e-12:
        lower -= 1
    while upper < 32 and turns[upper + 1] * sign > 1e-12:
        upper += 1
    recipient = min(range(lower, upper + 1), key=lambda i: utilization[i])
    if utilization[peak] - utilization[recipient] < 0.25:
        return None
    weights = tuple(0.5 if i in (0, 32) else 1.0 for i in range(33))
    demand = sum(weights[i] * abs(turns[i]) for i in range(lower, upper + 1))
    capacity = sum(weights[i] * limits[i] for i in range(lower, upper + 1))
    balanced = demand / capacity
    targets = tuple(
        0.5 * (turns[i] + sign * balanced * limits[i]) if lower <= i <= upper else turns[i]
        for i in range(33)
    )
    basis = tuple(
        (
            1.0,
            math.cos(2 * math.pi * u),
            math.sin(2 * math.pi * u),
            math.sin(4 * math.pi * u),
            math.cos(4 * math.pi * u),
        )
        for u in fractions
    )
    requested = tuple(
        _inverse_turn(targets[i], limits[i])
        if lower <= i <= upper
        else field.raw.sample(fractions[i])[0] * field.carrier_length_mm
        for i in range(33)
    )
    errors = tuple(
        sum(a * b for a, b in zip(coordinates[:5], row)) - target
        for row, target in zip(basis, requested)
    )
    columns = [tuple(row[i] for row in basis) for i in range(5)]
    step = constrained_step(
        columns,
        errors,
        1e-3,
        [()] * 5,
        (),
        coordinates[:5],
        (-4 * math.pi,) * 5,
        (4 * math.pi,) * 5,
    )
    norm = math.sqrt(sum(v * v for v in step.values))
    scale = min(1.0, 1.5 / norm) if norm else 1.0
    for value, delta in zip(coordinates[:5], step.values):
        if delta:
            boundary = math.copysign(4 * math.pi, delta)
            scale = min(scale, max(0.0, (boundary - value) / delta))
    scale = math.nextafter(scale, 0.0)
    proposed = tuple(a + scale * b for a, b in zip(coordinates[:5], step.values)) + coordinates[5:]
    if any(not -4 * math.pi <= v <= 4 * math.pi for v in proposed[:5]):
        raise ValueError("Redistribution projection exceeded the unchanged bend box.")
    return Allocation(
        "near-limit bend" if utilization[peak] >= 0.9 else "stalled bend imbalance",
        peak,
        recipient,
        (lower, upper),
        fractions,
        turns,
        limits,
        targets,
        coordinates,
        proposed,
        step.status,
    )
