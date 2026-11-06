"""
Find confirmed straight-sheet intersections without subdividing or claiming clearance.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import cross, difference, dot, unit

from .contact import Penetration
from .contact_inverse import occupied_coordinates
from .geometry import FoldRoute, PlacedPiece, Straight


def straight_witness(route: FoldRoute, first: int, second: int) -> Penetration | None:
    """
    Clip the two midplane intersection line to their material rectangles and verify one shared point.

    Return a witness only when both actual joined-profile inverse maps confirm
    strict occupied interiors. Parallel planes, degenerate intervals and missed
    thickness-only contacts return None, which never implies separation.
    """
    pair = straight_pair(route, first, second)
    if pair is None:
        return None
    a, b = pair
    n1, n2 = cross(a.pose.tangent, a.pose.width), cross(b.pose.tangent, b.pose.width)
    line = cross(n1, n2)
    square = dot(line, line)
    if square < 1e-16:
        return None
    offset = difference(b.pose.origin, a.pose.origin)
    point = a.pose.origin.translated(cross(line, n1), dot(n2, offset) / square)
    direction = unit(line)
    low, high = -math.inf, math.inf
    for piece in (a, b):
        relative = difference(point, piece.pose.origin)
        for axis, limits in (
            (piece.pose.tangent, (0.0, piece.geometry.material_length_mm)),
            (piece.pose.width, (-route.half_width_mm, route.half_width_mm)),
        ):
            value, slope = dot(relative, axis), dot(direction, axis)
            if abs(slope) < 1e-12:
                if not limits[0] < value < limits[1]:
                    return None
            else:
                start, end = (limits[0] - value) / slope, (limits[1] - value) / slope
                low, high = max(low, min(start, end)), min(high, max(start, end))
    if not math.isfinite(low + high) or low >= high:
        return None
    point = point.translated(direction, (low + high) / 2)
    left = occupied_coordinates(a, point, route.targets.lines, route.targets.diameter_mm)
    right = occupied_coordinates(b, point, route.targets.lines, route.targets.diameter_mm)
    return Penetration((first, second), left, right, point) if left and right else None


def straight_pair(
    route: FoldRoute, first: int, second: int
) -> tuple[PlacedPiece, PlacedPiece] | None:
    """
    Validate ordered piece identities and return only a pair of straight material regions.

    Invalid indices raise; a fold is unsupported by either analytic straight
    witness and returns None without implying a contact outcome.
    """
    if not 0 <= first < second < len(route.pieces):
        raise ValueError("Supply two distinct ordered route-piece indices")
    a, b = route.pieces[first], route.pieces[second]
    return (a, b) if isinstance(a.geometry, Straight) and isinstance(b.geometry, Straight) else None
