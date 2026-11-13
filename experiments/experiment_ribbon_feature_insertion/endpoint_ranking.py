"""
Decline only endpoint placements with a strictly dominated affine residual estimate.
"""

from __future__ import annotations

import math

from .allocation_hull import _projection


def dominated(
    columns: tuple[tuple[float, float, float], ...],
    right: tuple[float, float, float],
    values: tuple[float, ...],
    measured_error: float,
    placement_scale: float,
) -> bool:
    """
    Keep ties and uncertain arithmetic eligible for the original actual-placement ranking.

    Outward affine projections enclose column arithmetic. A deliberately generous
    scale allowance covers the different basis subtraction and ordered placement
    rounding paths. This is only a nearest-support workload filter; no endpoint,
    closure, material or contact acceptance is supplied by the estimate.
    """
    lower_components = []
    for axis, target in enumerate(right):
        low, high = _projection(tuple(column[axis] for column in columns), values)
        low = math.nextafter(low - target, -math.inf)
        high = math.nextafter(high - target, math.inf)
        lower_components.append(max(0.0, low, -high))
    norm = math.sqrt(math.fsum(value * value for value in lower_components))
    guard = 1e-7 * placement_scale * (1.0 + math.fsum(abs(value) for value in values))
    return math.isfinite(norm) and math.isfinite(guard) and norm > measured_error + guard
