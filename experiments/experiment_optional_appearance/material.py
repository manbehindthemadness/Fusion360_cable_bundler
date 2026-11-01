"""
Invert the frozen physical material map without assigning native renderer UVs.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece


def material_coordinates(
    piece: PlacedPiece, region: str, point: Vector3
) -> tuple[float, float, float]:
    """
    Invert the physical fold or flat section without using a surface's UV inverse.
    """
    geometry = piece.geometry
    if region != "bend":
        pose = piece.end_pose() if region == "after" else piece.pose
        delta = difference(point, pose.origin)
        s = dot(delta, pose.tangent)
        if region == "after":
            s += geometry.material_length_mm
        return s, dot(delta, pose.width), dot(delta, unit(cross(pose.tangent, pose.width)))
    if not isinstance(geometry, CylindricalFold):
        raise TypeError("A bend requires a frozen cylindrical fold")
    delta = difference(point, piece.pose.origin)
    x, y, z = (
        dot(delta, piece.pose.tangent),
        dot(delta, piece.pose.width),
        dot(delta, unit(cross(piece.pose.tangent, piece.pose.width))),
    )
    c, bank_s = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
    sign = math.copysign(1, geometry.angle_radians)
    along = c * (x - geometry.before_mm) + bank_s * y
    axial = -bank_s * (x - geometry.before_mm) + c * y
    phase = math.atan2(along, geometry.radius_mm - sign * z)
    # Choose the periodic branch nearest the prescribed phase interval. A tiny
    # negative phase at entry must not be wrapped to the opposite end of a fold.
    angle = abs(geometry.angle_radians)
    candidates = (phase - 2 * math.pi, phase, phase + 2 * math.pi)
    nearest = min(candidates, key=lambda value: abs(value - min(angle, max(0.0, value))))
    phase = min(angle, max(0.0, nearest))
    q = c * axial + geometry.radius_mm * phase * bank_s
    b = sign * (geometry.radius_mm - math.hypot(along, geometry.radius_mm - sign * z))
    s = geometry.before_mm + geometry.radius_mm * phase / c - q * math.tan(geometry.bank_radians)
    return s, q, b
