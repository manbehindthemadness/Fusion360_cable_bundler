"""
Describe exact circular-extrusion supports for flat material regions before native authoring.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import Vector3, cross, unit

from .geometry import PlacedPiece, Straight
from .material_profile import MaterialArc
from .material_surfaces import MaterialPatch


class FlatSurfaces(Enum):
    """
    Select equivalent native supports without changing planned material geometry or trims.
    """

    NURBS = "original_nurbs"
    CYLINDERS = "exact_circular_extrusions"


@dataclass(frozen=True)
class CylinderSupport:
    """
    Retain a circular profile's exact extrusion axis, radius and point on the axis in mm.
    """

    origin: Vector3
    axis: Vector3
    radius_mm: float


def circle(arc: MaterialArc) -> tuple[float, float, float]:
    """
    Recover the supplied circular profile's center and radius without fitting a new contour.

    Three exact rational-arc points determine the circle in profile coordinates.
    Normalize by chord length for scale covariance; malformed/degenerate segments
    reject. This operation does not approximate a noncircular input as a circle.
    Quarter-point checks independently reject such inputs at1e-10relative error.
    """
    a, middle, end = (arc.point(v) for v in (0.0, 0.5, 1.0))
    scale = math.hypot(end[0] - a[0], end[1] - a[1])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("An exact circular profile needs distinct finite endpoints")
    x, y = (middle[0] - a[0]) / scale, (middle[1] - a[1]) / scale
    u, v = (end[0] - a[0]) / scale, (end[1] - a[1]) / scale
    determinant = 2 * (x * v - y * u)
    if abs(determinant) <= 1e-12:
        raise ValueError("A circular profile must have a noncollinear midpoint")
    center_x = ((x * x + y * y) * v - (u * u + v * v) * y) / determinant
    center_y = (x * (u * u + v * v) - u * (x * x + y * y)) / determinant
    radius = math.hypot(center_x, center_y)
    q, b = a[0] + scale * center_x, a[1] + scale * center_y
    radius *= scale
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("A circular profile must have a positive finite radius")
    if any(
        abs(math.hypot(p[0] - q, p[1] - b) / radius - 1) > 1e-10
        for p in (arc.point(0.25), arc.point(0.75))
    ):
        raise ValueError("Supplied rational profile is not a circular arc")
    return q, b, radius


def cylinder(piece: PlacedPiece, patch: MaterialPatch) -> CylinderSupport:
    """
    Return the existing flat patch's cylinder; bends retain their prescribed NURBS support.

    Oblique material leads have slanted trim boundaries, but their support remains
    a circular extrusion along the constant terminal tangent. Use the actual flat
    start or end frame, retaining the ordered profile and supplied material map.
    """
    if patch.region not in ("straight", "before", "after") or patch.degree_u != 1:
        raise ValueError("Only flat material regions have circular-extrusion supports")
    if (patch.region == "straight") != isinstance(piece.geometry, Straight):
        raise ValueError("Flat support region disagrees with its material piece")
    q, height, radius = circle(patch.profile)
    point, velocity, width, _ = piece.surface(1.0 if patch.region == "after" else 0.0, 0.0)
    axis = unit(velocity)
    origin = point.translated(width, q).translated(unit(cross(velocity, width)), height)
    return CylinderSupport(origin, axis, radius)
