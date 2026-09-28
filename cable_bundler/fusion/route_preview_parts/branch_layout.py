"""
Arrange packed connection branches against live contact geometry.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Optional

from ...domain.connection_packing import PackedConnection
from ...routing import Vector3, assign_route_crossings
from ...routing.geometry import cross, difference, dot, magnitude, unit
from .frames import ProfileFrame


def assign_connection_packing(
    guide: ProfileFrame,
    packing: tuple[PackedConnection, ...],
    targets: tuple[Optional[ProfileFrame], ...],
) -> tuple[PackedConnection, ...]:
    """
    Match equal-size packed circles to contacts without changing their fit.

    Unresolved targets retain their slots; connection identity never changes.
    """
    assigned = list(packing)
    for diameter_mm in sorted({circle.diameter_mm for circle in packing}):
        indices = tuple(
            index
            for index, (circle, target) in enumerate(zip(packing, targets))
            if circle.diameter_mm == diameter_mm and target is not None
        )
        if len(indices) < 2:
            continue
        slots = tuple(
            guide.origin.translated(guide.u_direction, packing[index].x_mm).translated(
                guide.v_direction, packing[index].y_mm
            )
            for index in indices
        )
        preferred = tuple(
            target.origin for index in indices if (target := targets[index]) is not None
        )
        matched = assign_route_crossings(slots, preferred)
        for index, point in zip(indices, matched):
            offset = difference(point, guide.origin)
            assigned[index] = PackedConnection(
                dot(offset, guide.u_direction),
                dot(offset, guide.v_direction),
                diameter_mm,
            )
    return tuple(assigned)


def connection_fan_axis(
    guide: ProfileFrame,
    targets: tuple[Optional[ProfileFrame], ...],
) -> Optional[Vector3]:
    """
    Find the shared in-plane direction of a nearly straight contact row.
    """
    points = tuple(target.origin for target in targets if target is not None)
    if len(points) < 2:
        return None
    normal = unit(guide.normal)
    best_span = 0.0
    axis: Optional[Vector3] = None
    first_point = points[0]
    for left_index, left in enumerate(points):
        for right in points[left_index + 1 :]:
            delta = difference(right, left)
            normal_offset = dot(delta, normal)
            projected = Vector3(
                delta.x - normal.x * normal_offset,
                delta.y - normal.y * normal_offset,
                delta.z - normal.z * normal_offset,
            )
            span = magnitude(projected)
            if span > best_span:
                best_span = span
                axis = unit(projected)
                first_point = left
    if axis is None or best_span <= 1e-9:
        return None
    transverse = cross(normal, axis)
    if any(
        abs(dot(difference(point, first_point), transverse)) > best_span * 0.15 for point in points
    ):
        return None
    return axis


def expand_connection_packing(
    packing: tuple[PackedConnection, ...], parent_diameter_mm: float
) -> tuple[PackedConnection, ...]:
    """
    Use spare parent-face radius to give fanning branches initial clearance.
    """
    if len(packing) < 2:
        return packing
    maximum_center = max(math.hypot(circle.x_mm, circle.y_mm) for circle in packing)
    if maximum_center <= 1e-9:
        return packing
    maximum_radius = max(circle.diameter_mm for circle in packing) / 2.0
    scale = min(1.25, (parent_diameter_mm / 2.0 - maximum_radius) / maximum_center)
    if scale <= 1.0 + 1e-9:
        return packing
    return tuple(
        PackedConnection(circle.x_mm * scale, circle.y_mm * scale, circle.diameter_mm)
        for circle in packing
    )


def parallel_branch_lead(
    branch_frames: tuple[ProfileFrame, ...],
    guide: ProfileFrame,
    parent_side_point: Optional[Vector3],
    parent_diameter_mm: float,
    branch_diameter_mm: float,
    fan_axis: Optional[Vector3],
    fan_extent_mm: float,
) -> tuple[ProfileFrame, ...]:
    """
    Keep packed siblings parallel before they spread toward their contacts.

    Supports stay inside the last authored span. Distant row contacts start
    spreading earlier, leaving room for inner branches to follow.
    """
    if len(branch_frames) < 2:
        return branch_frames
    normal = unit(guide.normal)
    if (
        parent_side_point is not None
        and dot(difference(parent_side_point, guide.origin), normal) > 0.0
    ):
        normal = Vector3(-normal.x, -normal.y, -normal.z)
    cap = branch_frames[-1]
    if (
        parent_side_point is None
        and dot(difference(branch_frames[-2].origin, cap.origin), normal) < 0.0
    ):
        normal = Vector3(-normal.x, -normal.y, -normal.z)
    available_mm = dot(difference(branch_frames[-2].origin, cap.origin), normal)
    if available_mm <= 1e-6:
        return branch_frames
    lead_mm = min(max(parent_diameter_mm * 1.5, branch_diameter_mm * 2.0), available_mm * 0.35)
    if fan_axis is not None and fan_extent_mm > 1e-9:
        target_offset = abs(dot(difference(branch_frames[0].origin, guide.origin), fan_axis))
        lead_mm *= 1.0 - 0.8 * min(1.0, target_offset / fan_extent_mm)
    if lead_mm <= 1e-6:
        return branch_frames
    support = replace(cap, origin=cap.origin.translated(normal, lead_mm))
    if fan_axis is None:
        return (*branch_frames[:-1], support, cap)
    fan_mm = min(
        available_mm * 0.65,
        max(lead_mm + branch_diameter_mm * 2.0, parent_diameter_mm * 3.0),
    )
    if fan_mm <= lead_mm + 1e-6:
        return (*branch_frames[:-1], support, cap)
    target_shift = dot(difference(branch_frames[0].origin, cap.origin), fan_axis) * 0.5
    fan_origin = cap.origin.translated(normal, fan_mm).translated(fan_axis, target_shift)
    fan_support = replace(cap, origin=fan_origin)
    return (*branch_frames[:-1], fan_support, support, cap)
