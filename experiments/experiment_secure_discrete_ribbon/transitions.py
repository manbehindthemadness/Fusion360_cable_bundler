"""
Author uniform curved cap/connection fixtures, independently of solver output.
"""

from __future__ import annotations

import math
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, unit
from cable_bundler.routing.parallel import RoutePreview

_QUARTER_HANDLE = 4 * (math.sqrt(2) - 1) / 3


def terminal_turns(
    curves: tuple[CubicBezier, ...], start_width: Vector3, end_width: Vector3, radius_mm: float
) -> tuple[CubicBezier, ...]:
    """
    Add tangent-continuous quarter turns terminating at both fitted cap planes.

    Bend in the thickness plane so the prescribed width remains perpendicular
    at the new caps. Original stress curves remain intact, including controls.
    """
    start, end = curves[0].start, curves[-1].end
    a, b = unit(curves[0].derivative(0)), unit(curves[-1].derivative(1))
    side_a, side_b = unit(cross(a, start_width)), unit(cross(b, end_width))
    first = start.translated(a, -radius_mm).translated(side_a, -radius_mm)
    last = end.translated(b, radius_mm).translated(side_b, radius_mm)
    lead = CubicBezier(
        first,
        first.translated(side_a, _QUARTER_HANDLE * radius_mm),
        start.translated(a, -_QUARTER_HANDLE * radius_mm),
        start,
    )
    tail = CubicBezier(
        end,
        end.translated(b, _QUARTER_HANDLE * radius_mm),
        last.translated(side_b, -_QUARTER_HANDLE * radius_mm),
        last,
    )
    return (lead, *curves, tail)


def connection_turn(
    center: Vector3, inward: Vector3, bend: Vector3, radius_mm: float, name: str
) -> RoutePreview:
    """
    Flow from a perpendicular connection profile through a 90-degree exit into a cap.

    Every lane uses the same radius and turn, translated to its fitted center;
    there is no outcome-dependent repair or endpoint relocation.
    """
    target = center.translated(inward, -radius_mm).translated(bend, radius_mm)
    curve = CubicBezier(
        target,
        target.translated(bend, -_QUARTER_HANDLE * radius_mm),
        center.translated(inward, -_QUARTER_HANDLE * radius_mm),
        center,
    )
    return RoutePreview(uuid5(NAMESPACE_URL, name), name, (target, center), (curve,))


def transition_coverage(lines: int) -> list[dict[str, object]]:
    """
    Register every planned end/lane before any guard or construction can fail.
    """
    return [
        {"end": end, "lane": lane + 1, "status": "not_reached"}
        for end in ("A", "B")
        for lane in range(lines)
    ]
