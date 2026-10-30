"""
Share compatible-shooting seed budgets and bounded finite-difference/trial steps.
"""

from __future__ import annotations

import math
from typing import Sequence

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.pinch import BendModel, PinchLimit

from .constraint_policy import current
from .director_shooting import BANK_WIDTH, bounded, maximum_length_ratio
from .endpoint_first import EndpointCase


def seed_coordinates(case: EndpointCase, raw: tuple[float, ...]) -> tuple[float, ...]:
    """
    Allocate the historical carrier budget from raw bend/ruling magnitudes only.
    """
    maximum = maximum_length_ratio(case, BANK_WIDTH)
    chord = magnitude(difference(case.end, case.start))
    half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half, case.diameter_mm / 2)
    bend_bound = sum(abs(v) for v in raw[:5])
    policy = current()
    if policy.bend_model is BendModel.PINCH:
        required = (
            1.05 * bend_bound * (case.diameter_mm / 2) / PinchLimit(policy.pinch_percent).fraction
        )
        ratio = min(maximum, max(1.0, raw[9], required / chord))
        return raw[:9] + (ratio,)
    ruling_bound = 2 * math.pi * (abs(raw[5]) + abs(raw[6]) + 2 * abs(raw[7]) + 2 * abs(raw[8]))
    required = 1.2 * (bend_bound * reach / 0.78 + 2 * half * ruling_bound)
    ratio = min(maximum, max(1.0, raw[9], required / chord))
    return raw[:9] + (ratio,)


def probe_coordinates(
    values: tuple[float, ...], index: int, maximum: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Request the same signed1e-5probe and retain both requested and bounded values.
    """
    limit = 4 * math.pi if index < 5 else 3.0 if index < 9 else maximum
    probe = list(values)
    probe[index] += -1e-5 if values[index] >= limit else 1e-5
    requested = tuple(probe)
    return requested, bounded(requested, maximum_ratio=maximum)


def trial_coordinates(
    values: tuple[float, ...], delta: Sequence[float], fraction: float, maximum: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """
    Apply the historical1.5raw-coordinate step norm before bounding a trial.
    """
    norm = math.sqrt(sum(v * v for v in delta))
    scale = min(1.0, 1.5 / norm) if norm else 1.0
    requested = tuple(a + fraction * scale * b for a, b in zip(values, delta))
    return requested, bounded(requested, maximum_ratio=maximum)
