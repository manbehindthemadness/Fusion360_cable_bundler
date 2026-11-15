"""
Propose strict flat material points inside finite hardware without certifying clearance.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact_flat_geometry import FlatPhase, clip, region
from experiments.experiment_ribbon_fold_route.contact_inverse import profile_height
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight

from .model import Box


@dataclass(frozen=True)
class FlatPoint:
    """
    Retain an actual occupied material coordinate and its strictly interior box point.
    """

    material: tuple[float, float, float]
    point: Vector3
    box_coordinates: tuple[float, float, float]


def find(piece: PlacedPiece, box: Box, lines: int, diameter_mm: float) -> FlatPoint | None:
    """
    Clip affine flat phases at zero thickness and verify the actual material map.

    Misses grant no clearance: curved or thickness-only intersections remain for
    the existing bounded interval checker. Outward polygon clipping proposes
    coordinates only; original strict profile and box guards verify every point.
    No geometry, tolerance, profile or source target is modified.
    """
    geometry = piece.geometry
    if type(geometry) is CylindricalFold:
        phases = (FlatPhase.BEFORE, FlatPhase.AFTER)
    elif type(geometry) is Straight:
        phases = (FlatPhase.STRAIGHT,)
    else:
        return None
    guard = 1e-9 * max(1.0, diameter_mm)
    reach = (lines + 0.2) * diameter_mm / 2
    for phase in phases:
        flat = region(piece, phase, -reach, reach)
        polygon = flat.polygon
        relative = difference(Vector3(*flat.origin), box.pose.origin)
        for axis, bound in zip(box.axes, box.bounds):
            offset = dot(relative, axis)
            along = dot(Vector3(*flat.tangent), axis)
            across = dot(Vector3(*flat.width), axis)
            polygon = clip(polygon, along, across, bound.high - guard - offset)
            polygon = clip(polygon, -along, -across, offset - bound.low - guard)
            if not polygon:
                break
        if not polygon:
            continue
        distance = sum(point[0] for point in polygon) / len(polygon)
        q = sum(point[1] for point in polygon) / len(polygon)
        u = distance / geometry.material_length_mm
        if not 0 <= u <= 1 or profile_height(q, lines, diameter_mm) <= guard:
            continue
        point = piece.surface(u, q)[0]
        relative = difference(point, box.pose.origin)
        first, second, third = box.axes
        coordinates = dot(relative, first), dot(relative, second), dot(relative, third)
        if all(
            bound.low + guard < value < bound.high - guard
            for value, bound in zip(coordinates, box.bounds)
        ):
            return FlatPoint((u, q, 0.0), point, coordinates)
    return None
