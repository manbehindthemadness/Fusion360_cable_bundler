"""
Select an occupied thickness point without mistaking an interval overlap for intrusion.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, difference, dot
from experiments.experiment_ribbon_fold_route.contact_bounds import Span
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height

from .model import Box


def occupied_height(
    point: Vector3,
    normal: Vector3,
    q: float,
    heights: Span,
    box: Box,
    lines: int,
    diameter_mm: float,
) -> float | None:
    """
    Clip one material-normal line to the actual profile and strict finite-box interior.

    Prefer the original height midpoint when it is eligible. Otherwise choose
    one midpoint of the clipped interval, then verify its actual occupied point
    with the unchanged strict guards. Floating clipping only selects a candidate;
    it never certifies clearance or makes interval overlap an intrusion witness.
    Empty, nonfinite or boundary-only candidates supply no evidence.
    """
    guard = 1e-9 * max(1.0, diameter_mm)
    profile = profile_height(q, lines, diameter_mm)
    midpoint = (heights.low + heights.high) / 2
    original = difference(point.translated(normal, midpoint), box.pose.origin)
    if profile - abs(midpoint) > guard and all(
        limit.low + guard < dot(original, axis) < limit.high - guard
        for axis, limit in zip(box.axes, box.bounds)
    ):
        return midpoint
    reach = profile - guard
    low, high = max(heights.low, -reach), min(heights.high, reach)
    relative = difference(point, box.pose.origin)
    for axis, limit in zip(box.axes, box.bounds):
        center, slope = dot(relative, axis), dot(normal, axis)
        if not math.isfinite(center) or not math.isfinite(slope):
            return None
        if slope == 0.0:
            if not limit.low + guard < center < limit.high - guard:
                return None
        else:
            first = (limit.low + guard - center) / slope
            second = (limit.high - guard - center) / slope
            low, high = max(low, min(first, second)), min(high, max(first, second))
        if low > high:
            return None
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        return None
    height = midpoint if low <= midpoint <= high else (low + high) / 2
    occupied = point.translated(normal, height)
    coordinates = difference(occupied, box.pose.origin)
    if profile - abs(height) <= guard or not all(
        limit.low + guard < dot(coordinates, axis) < limit.high - guard
        for axis, limit in zip(box.axes, box.bounds)
    ):
        return None
    return height
