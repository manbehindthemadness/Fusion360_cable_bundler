"""
Prepare immutable material boundary points once per cell, independently of projection axes.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import NamedTuple

from devtools.ribbon_analysis.isometric_fold import CylindricalFold

Corners = tuple[tuple[float, float], ...]
Heights = tuple[float, float]
Point = tuple[float, float, float]


class EdgeBoundary(NamedTuple):
    """
    Retain original edge arithmetic and endpoint/join coordinates for both material heights.
    """

    xi: float
    eta: float
    dx: float
    de: float
    low: float
    high: float
    rows: tuple[tuple[Point, ...], ...]


Boundary = tuple[EdgeBoundary, ...]


def prepare_boundary(fold: CylindricalFold, corners: Corners, heights: Heights) -> Boundary:
    """
    Reconstruct original endpoints and G1 joins without projecting or finding stationary roots.

    Keep the original edge traversal and floating arithmetic, including reconstructed
    endpoints rather than substituting their algebraically equivalent corner inputs.
    """
    radius, angle = fold.radius_mm, abs(fold.angle_radians)
    sign = math.copysign(1.0, fold.angle_radians)
    arc = radius * angle
    sine, cosine = math.sin(angle), math.cos(angle)
    edges: list[EdgeBoundary] = []
    for start, end in zip(corners, corners[1:] + corners[:1]):
        xi, eta = start
        dx, de = end[0] - xi, end[1] - eta
        parameters = [0.0, 1.0]
        low, high = 0.0, -1.0
        if dx != 0:
            parameters.extend([t for cut in (0.0, arc) if 0 < (t := (cut - xi) / dx) < 1])
            low, high = max(0.0, min(xi, end[0]) / radius), min(angle, max(xi, end[0]) / radius)
        rows: list[tuple[Point, ...]] = []
        for height in heights:
            points: list[Point] = []
            for t in parameters:
                along, across = xi + dx * t, eta + de * t
                if along <= 0:
                    x, z = along, height
                elif along >= arc:
                    x = radius * sine + (along - arc) * cosine - sign * height * sine
                    z = sign * radius * (1 - cosine) + sign * (along - arc) * sine + height * cosine
                else:
                    phase, rho = along / radius, radius - sign * height
                    x = rho * math.sin(phase)
                    z = sign * (radius - rho * math.cos(phase))
                points.append((x, across, z))
            rows.append(tuple(points))
        edges.append(EdgeBoundary(xi, eta, dx, de, low, high, tuple(rows)))
    return tuple(edges)


class BoundaryCache:
    """
    Retain at most128 immutable cell preparations within one fixed-route proof walk.

    Callers must supply the same immutable material cell as owner for all its
    projections. Retaining that object prevents identity recycling; exact fold
    identity also gates reuse. Numeric equality never conflates signed-zero cells.
    Entries hold geometry only, with no projection, contact or acceptance result.
    """

    def __init__(self) -> None:
        """
        Start an empty bounded walk-local preparation store.
        """
        self._entries: OrderedDict[int, tuple[object, CylindricalFold, Boundary]] = OrderedDict()

    def prepare(
        self, owner: object, fold: CylindricalFold, corners: Corners, heights: Heights
    ) -> Boundary:
        """
        Reuse only this retained immutable owner's geometry under the identical fold object.
        """
        key = id(owner)
        existing = self._entries.get(key)
        if existing is not None and existing[0] is owner and existing[1] is fold:
            self._entries.move_to_end(key)
            return existing[2]
        boundary = prepare_boundary(fold, corners, heights)
        self._entries[key] = (owner, fold, boundary)
        self._entries.move_to_end(key)
        if len(self._entries) > 128:
            self._entries.popitem(last=False)
        return boundary
