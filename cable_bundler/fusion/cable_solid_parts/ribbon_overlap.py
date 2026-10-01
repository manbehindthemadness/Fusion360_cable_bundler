"""
Fit a ribbon root's hidden round overlap against the generated ribbon body.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...routing import RoutePreview, Vector3
from ...routing.geometry import cross, difference, dot, unit
from ..ribbon_geometry import RibbonGuidePlane
from .metadata import fusion_point
from .sweep_geometry import route_tail_axis

_MINIMUM_DIAMETER_MM = 0.01
_DIAMETER_PRECISION_MM = 0.005
_MAXIMUM_BISECTION_STEPS = 10
_AXIAL_STATIONS = 8
_ANGULAR_SAMPLES = 16
_END_PLANE_TOLERANCE_MM = 1e-6
_DIRECTION_TOLERANCE = 1e-6


def _radial_axes(axis: Vector3) -> tuple[Vector3, Vector3]:
    """
    Build a stable perpendicular basis around the straight branch extension.
    """
    reference = Vector3(0.0, 0.0, 1.0) if abs(axis.z) < 0.9 else Vector3(1.0, 0.0, 0.0)
    first = unit(cross(axis, reference))
    return first, unit(cross(axis, first))


def _point_escapes_ribbon(
    ribbon_body: adsk.fusion.BRepBody,
    point: Vector3,
    transform: adsk.core.Matrix3D,
) -> bool:
    """
    Classify one sampled branch-surface point against the stable ribbon body.
    """
    try:
        containment = ribbon_body.pointContainment(fusion_point(point, transform))
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        raise RuntimeError("Fusion could not classify the ribbon connection overlap.") from error
    if containment == adsk.fusion.PointContainment.PointOutsidePointContainment:
        return True
    if containment in (
        adsk.fusion.PointContainment.PointInsidePointContainment,
        adsk.fusion.PointContainment.PointOnPointContainment,
    ):
        return False
    raise RuntimeError("Fusion returned an unknown ribbon connection overlap classification.")


def _overlap_escapes_ribbon(
    ribbon_body: adsk.fusion.BRepBody,
    route: RoutePreview,
    guide_plane: RibbonGuidePlane,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> bool:
    """
    Sample the inward branch surface along the final sweep's straight overlap.
    """
    axis = route_tail_axis(route)
    start = route.curves[-1].end
    inward = unit(guide_plane.normal)
    if dot(inward, axis) < 0.0:
        inward = Vector3(-inward.x, -inward.y, -inward.z)
    if dot(inward, axis) <= _DIRECTION_TOLERANCE:
        raise ValueError("A ribbon connection has no inward overlap direction.")
    first, second = _radial_axes(axis)
    probe_radius_mm = diameter_mm / 2.0 + max(0.01, diameter_mm * 0.01)
    overlap_length_mm = diameter_mm * 0.5
    inspected_points = 0
    for station_index in range(_AXIAL_STATIONS):
        fraction = station_index / (_AXIAL_STATIONS - 1)
        center = start.translated(axis, overlap_length_mm * fraction)
        ring = (center,)
        ring += tuple(
            center.translated(
                first, probe_radius_mm * math.cos(2.0 * math.pi * index / _ANGULAR_SAMPLES)
            ).translated(
                second, probe_radius_mm * math.sin(2.0 * math.pi * index / _ANGULAR_SAMPLES)
            )
            for index in range(_ANGULAR_SAMPLES)
        )
        for point in ring:
            if dot(difference(point, guide_plane.origin), inward) <= _END_PLANE_TOLERANCE_MM:
                continue
            inspected_points += 1
            if _point_escapes_ribbon(ribbon_body, point, transform):
                return True
    if inspected_points == 0:
        raise ValueError("A ribbon connection has no overlap inside its end plane.")
    return False


def fitted_ribbon_overlap_diameter(
    ribbon_body: adsk.fusion.BRepBody,
    route: RoutePreview,
    guide_plane: RibbonGuidePlane,
    cap_diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> float:
    """
    Return the largest constant branch diameter that stays inside the ribbon.

    Read-only surface probes leave the design untouched. The fitted end-face
    size is an upper bound, and an unknown classification stops generation.
    """
    if not math.isfinite(cap_diameter_mm) or cap_diameter_mm <= 0.0:
        raise ValueError("A ribbon connection needs a positive end-face diameter.")
    if not _overlap_escapes_ribbon(ribbon_body, route, guide_plane, cap_diameter_mm, transform):
        return cap_diameter_mm
    if _overlap_escapes_ribbon(ribbon_body, route, guide_plane, _MINIMUM_DIAMETER_MM, transform):
        raise ValueError("A ribbon line has no usable circular connection overlap.")
    lower_mm = _MINIMUM_DIAMETER_MM
    upper_mm = cap_diameter_mm
    for _step in range(_MAXIMUM_BISECTION_STEPS):
        if upper_mm - lower_mm <= _DIAMETER_PRECISION_MM:
            break
        candidate_mm = (lower_mm + upper_mm) / 2.0
        if _overlap_escapes_ribbon(ribbon_body, route, guide_plane, candidate_mm, transform):
            upper_mm = candidate_mm
        else:
            lower_mm = candidate_mm
    return lower_mm
