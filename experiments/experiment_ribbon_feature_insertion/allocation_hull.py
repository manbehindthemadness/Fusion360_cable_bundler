"""
Exclude fixed-angle allocations by outward-rounded convex travel support bounds.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross

from .allocation_bounds import StraightReach


@dataclass(frozen=True)
class Separation:
    """
    Retain one separating projection; this certifies no fixed-angle fit, not physical infeasibility.
    """

    direction: tuple[float, ...]
    travel: tuple[float, float]
    target: tuple[float, float]

    @property
    def distance_lower_bound(self) -> float:
        """
        Bound the relaxed affine endpoint distance below using the separating projection.
        """
        gap = math.nextafter(
            max(self.travel[0] - self.target[1], self.target[0] - self.travel[1]), -math.inf
        )
        norm = math.nextafter(math.sqrt(_projection(self.direction, self.direction)[1]), math.inf)
        return max(0.0, math.nextafter(gap / norm, -math.inf))


def _projection(axis: tuple[float, ...], point: tuple[float, ...]) -> tuple[float, float]:
    """
    Enclose the exact real dot product of finite floating operands, rounding each operation outward.
    """
    lower = upper = 0.0
    for a, b in zip(axis, point):
        product = a * b
        lower = math.nextafter(lower + math.nextafter(product, -math.inf), -math.inf)
        upper = math.nextafter(upper + math.nextafter(product, math.inf), math.inf)
    return lower, upper


def separate(reach: StraightReach, checkpoint: Callable[[], None]) -> Separation | None:
    """
    Try at most56triple normals for the origin and seven bounded straight rays.

    Nonnegative travel with bounded sum lies in the scaled convex hull of those
    vertices. Any finite direction is a valid support bound, even if its computed
    normal is approximate. Original component residual and sum allowances remain
    included. Degenerate, overflowing or unbounded data decline acceleration.
    A decline says nothing about feasibility; angular reclosure remains eligible.
    """
    if reach.maximum_sum is None or len(reach.rows) != 3:
        return None
    count = len(reach.rows[0])
    if count > 7:
        return None
    limit = math.nextafter(reach.maximum_sum + 1e-8, math.inf)
    limit = math.nextafter(limit + 8 * math.ulp(reach.maximum_sum), math.inf)
    if not math.isfinite(limit):
        return None
    vertices = ((0.0, 0.0, 0.0),) + tuple(zip(*reach.rows))
    scale = max((abs(value) for vertex in vertices for value in vertex), default=0.0)
    if scale == 0:
        return None
    normalized = tuple(tuple(value / scale for value in vertex) for vertex in vertices)
    for a, b, c in itertools.combinations(normalized, 3):
        checkpoint()
        u = tuple(y - x for x, y in zip(a, b))
        v = tuple(y - x for x, y in zip(a, c))
        product = cross(Vector3(*u), Vector3(*v))
        normal = (product.x, product.y, product.z)
        magnitude = max(abs(value) for value in normal)
        if magnitude == 0:
            continue
        direction = tuple(value / magnitude for value in normal)
        projections = tuple(_projection(direction, vertex) for vertex in vertices)
        low = math.nextafter(min(p[0] for p in projections) * limit, -math.inf)
        high = math.nextafter(max(p[1] for p in projections) * limit, math.inf)
        target_low, target_high = _projection(direction, reach.right)
        # The projection of three component residuals is bounded by their L1 support.
        allowance = 0.0
        for value in direction:
            term = math.nextafter(abs(value) * 1e-8, math.inf)
            allowance = math.nextafter(allowance + term, math.inf)
        target_low = math.nextafter(target_low - allowance, -math.inf)
        target_high = math.nextafter(target_high + allowance, math.inf)
        if not all(math.isfinite(value) for value in (low, high, target_low, target_high)):
            continue
        if target_high < low or target_low > high:
            return Separation(direction, (low, high), (target_low, target_high))
    return None
