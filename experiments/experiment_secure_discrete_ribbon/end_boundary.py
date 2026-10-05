"""
Author compact cable-end fixtures without confining or shrinking their sweeps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, lerp, magnitude, unit

from .transitions import terminal_turns


@dataclass(frozen=True)
class EndBoundary:
    """
    Retain the explicitly declared shared endpoint sphere for a fixture.

    Only cable-end guides are confined, not interior curves or split connections.
    """

    center: Vector3
    diameter_mm: float

    def require_contains(self, points: tuple[Vector3, ...]) -> float:
        """
        Reject invalid or out-of-sphere endpoints and return their largest radius.
        """
        values = (self.center.x, self.center.y, self.center.z, self.diameter_mm)
        if not all(math.isfinite(value) for value in values) or self.diameter_mm <= 0:
            raise ValueError("Cable-end sphere must be finite and positive.")
        distances = tuple(magnitude(difference(point, self.center)) for point in points)
        if not distances or any(
            not math.isfinite(distance) or distance > self.diameter_mm / 2 + 1e-8
            for distance in distances
        ):
            raise ValueError("Cable-end guide lies outside its declared sphere.")
        return max(distances)


def bounded_terminal_turns(
    curves: tuple[CubicBezier, ...], start_width: Vector3, end_width: Vector3, width_mm: float
) -> tuple[tuple[CubicBezier, ...], EndBoundary]:
    """
    Preserve stress cubics and cap turns while returning to a nearby end guide.

    All families use the same authored two-cubic return, independent of solver
    results. Its scale follows endpoint distance, not a build/audit failure.
    No curvature limit, bank policy, or output audit is changed here. Continuous
    curvature certification still decides whether the input is admissible.
    """
    turned = terminal_turns(curves, start_width, end_width, 8 * width_mm)
    first = turned[0].start
    last = first.translated(start_width, 2 * width_mm)
    displacement = difference(last, turned[-1].end)
    tail = CubicBezier(
        *(
            point.translated(displacement, 1)
            for point in (
                turned[-1].start,
                turned[-1].control_a,
                turned[-1].control_b,
                turned[-1].end,
            )
        )
    )
    start, end = curves[-1].end, tail.start
    tangent = unit(curves[-1].derivative(1))
    scale = magnitude(difference(end, start)) + 20 * width_mm
    middle = lerp(start, end, 0.5).translated(tangent, scale).translated(end_width, scale)
    return_curves = (
        CubicBezier(
            start, start.translated(tangent, scale), middle.translated(tangent, scale), middle
        ),
        CubicBezier(
            middle, middle.translated(tangent, -scale), end.translated(tangent, -scale), end
        ),
    )
    boundary = EndBoundary(lerp(first, last, 0.5), 5 * width_mm)
    return (turned[0], *curves, *return_curves, tail), boundary
