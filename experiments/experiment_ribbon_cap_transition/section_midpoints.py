"""
Give each unchanged section two explicit vertices at its outer width extrema.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import adsk.fusion


def split_outer_edge_midpoints(
    section: adsk.fusion.Sketch, line_count: int
) -> tuple[tuple[float, float, float], ...]:
    """
    Split the two final side-cap arcs at their angular midpoints, in place.

    The existing discrete contour draws numbered lobes first and side caps last.
    Preserve its circular geometry and single closed profile; add contour vertices,
    not detached sketch points or movable controls. Return world coordinates in mm.
    Reject malformed or already-enhanced topology; never retry or repair a split.
    An API failure can leave partial edits for the caller to retain as evidence.
    """
    arcs = section.sketchCurves.sketchArcs
    if line_count < 1 or arcs.count != 2 * line_count + 2 or section.profiles.count != 1:
        raise ValueError("Expected one original discrete section with two outer side caps.")
    caps = (arcs.item(2 * line_count), arcs.item(2 * line_count + 1))
    points = []
    for cap in caps:
        evaluator = cap.geometry.evaluator
        success, start, end = evaluator.getParameterExtents()
        if not success or not all(math.isfinite(value) for value in (start, end)) or end <= start:
            raise RuntimeError("Outer side-cap parameter range is unavailable.")
        success, midpoint = evaluator.getPointAtParameter((start + end) / 2)
        if not success or midpoint is None:
            raise RuntimeError("Outer side-cap midpoint is unavailable.")
        world = section.sketchToModelSpace(midpoint)
        coordinates = (world.x * 10, world.y * 10, world.z * 10)
        if not all(math.isfinite(value) for value in coordinates):
            raise RuntimeError("Outer side-cap midpoint is nonfinite.")
        points.append((cap, midpoint, coordinates))
    for cap, midpoint, _ in points:
        result = cap.split(midpoint)
        if result is None or result.count != 2:
            raise RuntimeError("Outer side-cap split did not return two arcs.")
    if arcs.count != 2 * line_count + 4 or section.profiles.count != 1:
        raise RuntimeError("Midpoint vertices did not preserve one closed section.")
    return tuple(coordinates for _, _, coordinates in points)
