"""
Resolve solid Discrete loft lands from ordered contact-plane geometry.
"""

from __future__ import annotations

import math

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...routing.geometry import difference
from ..solid_ribbon import SolidRibbonPlan, SolidRibbonSection
from .metadata import fusion_point

CONTACT_PLANE_TOLERANCE_MM = 0.025
TRACE_CENTER_TOLERANCE_MM = 0.03
TRACE_WIDTH_TOLERANCE_MM = 0.05
CONTACT_TRACE_FACE_REVISION = 1


def _contact_frame(
    station: SolidRibbonSection,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.core.Point3D, adsk.core.Vector3D, adsk.core.Vector3D, tuple[float, ...]]:
    """
    Project the ordered contact centers into one local contact-plane frame.
    """
    first = station.centers[0]
    last = station.centers[-1]
    midpoint = first.translated(difference(last, first), 0.5)
    origin = fusion_point(midpoint, transform)
    width_tip = fusion_point(midpoint.translated(station.width, 10.0), transform)
    normal_tip = fusion_point(midpoint.translated(station.normal, 10.0), transform)
    width = adsk.core.Vector3D.create(
        width_tip.x - origin.x, width_tip.y - origin.y, width_tip.z - origin.z
    )
    normal = adsk.core.Vector3D.create(
        normal_tip.x - origin.x, normal_tip.y - origin.y, normal_tip.z - origin.z
    )
    if not width.normalize() or not normal.normalize():
        raise RuntimeError("A ribbon contact plane has no usable width or normal axis.")
    centers: list[float] = []
    for center in station.centers:
        point = fusion_point(center, transform)
        delta = adsk.core.Vector3D.create(
            point.x - origin.x, point.y - origin.y, point.z - origin.z
        )
        centers.append(delta.dotProduct(width) * 10.0)
    if any(right - left <= 0.0 for left, right in zip(centers, centers[1:])):
        raise RuntimeError("The ordered ribbon contact centers are not increasing across width.")
    return origin, width, normal, tuple(centers)


def _face_interval_mm(
    face: adsk.fusion.BRepFace,
    origin: adsk.core.Point3D,
    width: adsk.core.Vector3D,
    normal: adsk.core.Vector3D,
) -> tuple[float, float]:
    """
    Measure one face's width interval where it meets a contact plane.

    Calculated mesh positions are sufficient here; texture UVs are not used.
    """
    calculator = face.meshManager.createMeshCalculator()
    mesh = calculator.calculate()
    if mesh is None:
        raise RuntimeError("Fusion could not measure a ribbon loft face.")
    across: list[float] = []
    for point in mesh.nodeCoordinates:
        delta = adsk.core.Vector3D.create(
            point.x - origin.x, point.y - origin.y, point.z - origin.z
        )
        if abs(delta.dotProduct(normal)) * 10.0 <= CONTACT_PLANE_TOLERANCE_MM:
            across.append(delta.dotProduct(width) * 10.0)
    if len(across) < 2:
        raise RuntimeError("A ribbon loft face does not reach its contact plane.")
    return min(across), max(across)


def _matching_lane(
    start_interval: tuple[float, float],
    end_interval: tuple[float, float],
    start_centers: tuple[float, ...],
    end_centers: tuple[float, ...],
    start_width_mm: float,
    end_width_mm: float,
) -> int | None:
    """
    Identify a broad trace land only if its width and identity match both ends.
    """
    start_low, start_high = start_interval
    end_low, end_high = end_interval
    start_width = start_high - start_low
    if abs(start_width - start_width_mm) > TRACE_WIDTH_TOLERANCE_MM:
        return None
    if abs(end_high - end_low - end_width_mm) > TRACE_WIDTH_TOLERANCE_MM:
        raise RuntimeError("A ribbon trace land changes width before its far contact.")
    start_mid = (start_low + start_high) / 2.0
    end_mid = (end_low + end_high) / 2.0
    lane = min(range(len(start_centers)), key=lambda index: abs(start_mid - start_centers[index]))
    if (
        abs(start_mid - start_centers[lane]) > TRACE_CENTER_TOLERANCE_MM
        or abs(end_mid - end_centers[lane]) > TRACE_CENTER_TOLERANCE_MM
    ):
        raise RuntimeError("A ribbon trace land does not preserve its contact identity.")
    return lane


def contact_trace_face_lanes(
    feature: adsk.fusion.LoftFeature,
    plan: SolidRibbonPlan,
    transform: adsk.core.Matrix3D,
) -> tuple[tuple[adsk.fusion.BRepFace, int], ...]:
    """
    Return exactly one upper and lower land per persistent contact lane.

    The two contact-plane frames, not world-axis positions or face order,
    establish correspondence. Web, edge, and groove faces remain uncolored.
    """
    if len(plan.sections) < 2 or not plan.sections[0].centers:
        raise ValueError("Contact trace mapping requires two populated end stations.")
    start_width_mm = plan.sections[0].lobe_width_mm
    end_width_mm = plan.sections[-1].lobe_width_mm
    if any(
        not math.isfinite(width_mm) or width_mm <= 0.0
        for width_mm in (start_width_mm, end_width_mm)
    ):
        raise ValueError("Contact trace mapping requires positive end lobe widths.")
    first = _contact_frame(plan.sections[0], transform)
    last = _contact_frame(plan.sections[-1], transform)
    if len(first[3]) != len(last[3]):
        raise ValueError("Ribbon ends have different contact counts.")
    selected: list[tuple[adsk.fusion.BRepFace, int]] = []
    counts = [0] * len(first[3])
    for face_index in range(feature.sideFaces.count):
        face = feature.sideFaces.item(face_index)
        start_interval = _face_interval_mm(face, first[0], first[1], first[2])
        end_interval = _face_interval_mm(face, last[0], last[1], last[2])
        lane = _matching_lane(
            start_interval,
            end_interval,
            first[3],
            last[3],
            start_width_mm,
            end_width_mm,
        )
        if lane is not None:
            counts[lane] += 1
            selected.append((face, lane))
    if any(count != 2 for count in counts):
        raise RuntimeError(f"Ribbon loft has incorrect top/bottom contact trace faces: {counts}.")
    return tuple(selected)
