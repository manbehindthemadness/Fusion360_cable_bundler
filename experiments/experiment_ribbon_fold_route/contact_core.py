"""
Confirm straight-volume penetration through the intersection of inscribed material cores.
"""

from __future__ import annotations

import math
from itertools import product

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit

from .contact import Penetration
from .contact_inverse import occupied_coordinates
from .geometry import FoldRoute, PlacedPiece
from .straight_witness import straight_pair


def core_witness(route: FoldRoute, first: int, second: int) -> Penetration | None:
    """
    Verify the intersection centroid of two straight joined-profile cores in both actual inverse maps.

    The nominal width and valley height enclose a uniform rectangular core inside
    the preserved joined-lobe profile. Clip all twelve edges of each core against
    the other, then average their intersection vertices. Strict inverse checks
    remain authoritative, including numerical and material boundaries. A miss,
    tangency or empty core intersection never implies clearance. No route motion,
    subdivision or clearance acceptance occurs here.
    """
    pieces = straight_pair(route, first, second)
    if pieces is None:
        return None
    half_width = route.targets.lines * route.targets.diameter_mm / 2
    half_height = 0.3 * route.targets.diameter_mm
    vertices = _vertices(*pieces, half_width, half_height)
    vertices.extend(_vertices(*reversed(pieces), half_width, half_height))
    if not vertices:
        return None
    count = len(vertices)
    point = Vector3(
        math.fsum(p.x for p in vertices) / count,
        math.fsum(p.y for p in vertices) / count,
        math.fsum(p.z for p in vertices) / count,
    )
    left = occupied_coordinates(pieces[0], point, route.targets.lines, route.targets.diameter_mm)
    right = occupied_coordinates(pieces[1], point, route.targets.lines, route.targets.diameter_mm)
    if left is None or right is None:
        return None
    return Penetration((first, second), left, right, point)


def _vertices(
    piece: PlacedPiece, other: PlacedPiece, half_width: float, half_height: float
) -> list[Vector3]:
    """
    Return endpoints of all twelve core edges clipped to the opposing oriented core box.

    Near-parallel slab clipping may miss a witness; the final actual inverse
    checks prevent approximate clipping from claiming a false penetration.
    """
    axes = (piece.pose.tangent, piece.pose.width, unit(cross(piece.pose.tangent, piece.pose.width)))
    other_axes = (
        other.pose.tangent,
        other.pose.width,
        unit(cross(other.pose.tangent, other.pose.width)),
    )
    limits = (
        (0.0, piece.geometry.material_length_mm),
        (-half_width, half_width),
        (-half_height, half_height),
    )
    other_limits = ((0.0, other.geometry.material_length_mm), limits[1], limits[2])
    vertices: list[Vector3] = []
    for moving in range(3):
        fixed = tuple(i for i in range(3) if i != moving)
        for ends in product((0, 1), repeat=2):
            origin = piece.pose.origin
            for index, end in zip(fixed, ends):
                origin = origin.translated(axes[index], limits[index][end])
            low, high = limits[moving]
            offset = difference(origin, other.pose.origin)
            for axis, (start, stop) in zip(other_axes, other_limits):
                value, slope = dot(offset, axis), dot(axes[moving], axis)
                if abs(slope) < 1e-14:
                    if value < start or value > stop:
                        low, high = 1.0, 0.0
                        break
                else:
                    a, b = (start - value) / slope, (stop - value) / slope
                    low, high = max(low, min(a, b)), min(high, max(a, b))
            if low <= high:
                vertices.extend(
                    (origin.translated(axes[moving], low), origin.translated(axes[moving], high))
                )
    return vertices
