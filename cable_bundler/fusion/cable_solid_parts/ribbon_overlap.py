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
_ESCAPED_VOLUME_TOLERANCE_CM3 = 1e-12
_ESCAPED_VOLUME_FRACTION = 1e-5


def _local_direction(
    origin: Vector3, direction: Vector3, transform: adsk.core.Matrix3D
) -> adsk.core.Vector3D:
    """
    Transform a world-space direction into the generated component's coordinates.
    """
    start = fusion_point(origin, transform)
    end = fusion_point(origin.translated(direction, 1.0), transform)
    local = adsk.core.Vector3D.create(end.x - start.x, end.y - start.y, end.z - start.z)
    if not local.normalize():
        raise ValueError("A ribbon end plane has no usable local direction.")
    return local


def _inside_end_box(
    manager: adsk.fusion.TemporaryBRepManager,
    guide_plane: RibbonGuidePlane,
    route_end: Vector3,
    axis: Vector3,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> adsk.fusion.BRepBody:
    """
    Bound the inward half-space so an external connection is not called a bulge.
    """
    inward = unit(guide_plane.normal)
    if dot(inward, axis) < 0.0:
        inward = Vector3(-inward.x, -inward.y, -inward.z)
    sideways = cross(inward, Vector3(0.0, 0.0, 1.0))
    if abs(sideways.x) + abs(sideways.y) + abs(sideways.z) < 1e-8:
        sideways = cross(inward, Vector3(1.0, 0.0, 0.0))
    extent_mm = max(10.0, diameter_mm * 8.0)
    plane_offset_mm = dot(difference(route_end, guide_plane.origin), inward)
    end_on_plane = route_end.translated(inward, -plane_offset_mm)
    center = end_on_plane.translated(inward, extent_mm / 2.0)
    box = adsk.core.OrientedBoundingBox3D.create(
        fusion_point(center, transform),
        _local_direction(guide_plane.origin, inward, transform),
        _local_direction(guide_plane.origin, unit(sideways), transform),
        extent_mm / 10.0,
        extent_mm * 2.0 / 10.0,
        extent_mm * 2.0 / 10.0,
    )
    half_space = manager.createBox(box)
    if half_space is None:
        raise RuntimeError("Fusion could not define the ribbon's inward overlap boundary.")
    return half_space


def _overlap_escapes_ribbon(
    manager: adsk.fusion.TemporaryBRepManager,
    ribbon_body: adsk.fusion.BRepBody,
    route: RoutePreview,
    guide_plane: RibbonGuidePlane,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> bool:
    """
    Test the same half-diameter straight extension used by the final sweep.
    """
    axis = route_tail_axis(route)
    start = route.curves[-1].end
    end = start.translated(axis, diameter_mm * 0.5)
    radius_cm = diameter_mm / 20.0
    overlap = manager.createCylinderOrCone(
        fusion_point(start, transform),
        radius_cm,
        fusion_point(end, transform),
        radius_cm,
    )
    if overlap is None:
        raise RuntimeError("Fusion could not measure the ribbon connection overlap.")
    inward_box = _inside_end_box(manager, guide_plane, start, axis, diameter_mm, transform)
    if not manager.booleanOperation(
        overlap, inward_box, adsk.fusion.BooleanTypes.IntersectionBooleanType
    ):
        raise RuntimeError("Fusion could not clip the ribbon connection to its inward side.")
    if not overlap.isValid or overlap.volume <= 0.0:
        raise ValueError("A ribbon connection has no overlap inside its end plane.")
    clipped_volume_cm3 = overlap.volume
    if not manager.booleanOperation(
        overlap, ribbon_body, adsk.fusion.BooleanTypes.DifferenceBooleanType
    ):
        raise RuntimeError("Fusion could not compare the connection with the ribbon surface.")
    tolerance_cm3 = max(
        _ESCAPED_VOLUME_TOLERANCE_CM3,
        clipped_volume_cm3 * _ESCAPED_VOLUME_FRACTION,
    )
    return overlap.isValid and overlap.volume > tolerance_cm3


def fitted_ribbon_overlap_diameter(
    ribbon_body: adsk.fusion.BRepBody,
    route: RoutePreview,
    guide_plane: RibbonGuidePlane,
    cap_diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> float:
    """
    Return the largest constant branch diameter that stays inside the ribbon.

    Temporary BRep probes leave the design untouched. The fitted end-face size
    is an upper bound, and a failed containment operation stops generation.
    """
    if not math.isfinite(cap_diameter_mm) or cap_diameter_mm <= 0.0:
        raise ValueError("A ribbon connection needs a positive end-face diameter.")
    manager = adsk.fusion.TemporaryBRepManager.get()
    if manager is None:
        raise RuntimeError("Fusion could not access temporary ribbon geometry.")
    if not _overlap_escapes_ribbon(
        manager, ribbon_body, route, guide_plane, cap_diameter_mm, transform
    ):
        return cap_diameter_mm
    if _overlap_escapes_ribbon(
        manager, ribbon_body, route, guide_plane, _MINIMUM_DIAMETER_MM, transform
    ):
        raise ValueError("A ribbon line has no usable circular connection overlap.")
    lower_mm = _MINIMUM_DIAMETER_MM
    upper_mm = cap_diameter_mm
    while upper_mm - lower_mm > _DIAMETER_PRECISION_MM:
        candidate_mm = (lower_mm + upper_mm) / 2.0
        if _overlap_escapes_ribbon(
            manager, ribbon_body, route, guide_plane, candidate_mm, transform
        ):
            upper_mm = candidate_mm
        else:
            lower_mm = candidate_mm
    return lower_mm
