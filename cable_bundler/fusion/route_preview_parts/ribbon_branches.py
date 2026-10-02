"""
Locate numbered ribbon connection roots on their fitted line end faces.
"""

from __future__ import annotations

import math
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg
from ...domain import CableGroupType, HarnessDefinition, RibbonGeometryType
from ...routing import (
    CubicBezier,
    RoutePreview,
    Vector3,
    minimum_circular_bend_radius,
    tightest_bend,
)
from ...routing.geometry import difference, dot, magnitude, unit
from ..ffc_dimensions import ffc_dimensions
from ..ribbon_geometry import ribbon_route_shape
from .frames import ProfileFrame, connection_profile_frames

_FACE_DIAMETER_CLEARANCE = 0.90


def _fitted_connection_diameter(
    center: Vector3, left_edge: Vector3, right_edge: Vector3, nominal_mm: float
) -> float:
    """
    Keep a round connection within its line's fitted end-face lobe.
    """
    available_mm = min(
        nominal_mm,
        2.0 * magnitude(difference(center, left_edge)),
        2.0 * magnitude(difference(right_edge, center)),
    )
    if not math.isfinite(available_mm) or available_mm <= 0.0:
        raise ValueError("A ribbon line has no usable connection face width.")
    return available_mm * _FACE_DIAMETER_CLEARANCE


def _terminal_lane_tangent(lane: tuple[Vector3, ...], *, at_start: bool) -> Vector3:
    """
    Extrapolate the loft's end direction from its nearest three line sections.

    The immediate chord is retained when a short or sharply folded lane gives
    an unusable one-sided quadratic estimate.
    """
    ordered = lane if at_start else tuple(reversed(lane))
    first = difference(ordered[1], ordered[0])
    if len(ordered) < 3:
        return unit(first)
    second = difference(ordered[2], ordered[1])
    first_length = magnitude(first)
    second_length = magnitude(second)
    if first_length <= 1e-9 or second_length <= 1e-9:
        return unit(first)
    span = first_length + second_length
    first_weight = (2.0 * first_length + second_length) / (first_length * span)
    second_weight = -first_length / (second_length * span)
    estimate = Vector3(
        first.x * first_weight + second.x * second_weight,
        first.y * first_weight + second.y * second_weight,
        first.z * first_weight + second.z * second_weight,
    )
    if magnitude(estimate) <= 1e-9 or dot(estimate, first) <= 0.0:
        return unit(first)
    return unit(estimate)


def align_ribbon_branch_end(
    route: RoutePreview, ribbon_tangent: Vector3, diameter_mm: float
) -> tuple[RoutePreview, bool]:
    """
    Match only the final cubic to the lofted line without refairing the branch.

    Return the original route when the terminal direction cannot meet the sweep
    bend guard; the caller can then report the uncorrected junction.
    """
    if not route.curves:
        return route, False
    last = route.curves[-1]
    previous = difference(last.end, last.control_b)
    if magnitude(previous) <= 1e-9:
        previous = difference(last.end, last.start)
    if magnitude(previous) <= 1e-9:
        return route, False
    direction = unit(ribbon_tangent)
    if dot(direction, previous) < 0.0:
        direction = Vector3(-direction.x, -direction.y, -direction.z)
    if dot(unit(previous), direction) >= 1.0 - 1e-6:
        return route, True
    handle_mm = magnitude(difference(last.end, last.control_b))
    if handle_mm <= 1e-9:
        handle_mm = magnitude(difference(last.end, last.start)) / 3.0
    adjusted = CubicBezier(
        last.start,
        last.control_a,
        last.end.translated(direction, -handle_mm),
        last.end,
    )
    candidate = RoutePreview(
        route.cable_id, route.cable_number, route.points, (*route.curves[:-1], adjusted)
    )
    bend = tightest_bend(
        RoutePreview(route.cable_id, route.cable_number, (last.start, last.end), (adjusted,)), 64
    )
    if bend is None or bend.radius_mm < minimum_circular_bend_radius(diameter_mm):
        return route, False
    return candidate, True


def ribbon_branch_guides(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    legs: tuple[CableGroupRouteLeg, ...],
    routes: tuple[RoutePreview, ...],
) -> dict[tuple[UUID, UUID, UUID], ProfileFrame]:
    """
    Return exact one-based line anchors for connected top-level nodes only.
    """
    groups = {group.cable_group_id: group for group in definition.cable_groups}
    connections = {item.connection_id: item for item in definition.connections}
    guides: dict[tuple[UUID, UUID, UUID], ProfileFrame] = {}
    for leg, route in zip(legs, routes):
        group = groups[leg.cable_group_id]
        if group.group_type is not CableGroupType.RIBBON:
            continue
        attached_ends = tuple(
            (connection_id, at_start)
            for connection_id, at_start in (
                (leg.start_connection_id, True),
                (leg.end_connection_id, False),
            )
            if connection_id is not None
            and any(
                item.has_target for item in connections[connection_id].attachment_children(None)
            )
        )
        if not attached_ends:
            continue
        ffc = (
            ffc_dimensions(design, definition, group)
            if group.ribbon_geometry is RibbonGeometryType.FFC
            else None
        )
        pitch = ffc.pitch_mm if ffc is not None else group.diameter_mm
        fitted = ribbon_route_shape(design, definition, leg, route, group.ribbon_lines, pitch)
        for connection_id, at_start in attached_ends:
            connection = connections[connection_id]
            end_fit = fitted.shape.start_fit if at_start else fitted.shape.end_fit
            if end_fit is None:
                raise ValueError("A connected ribbon end needs a usable fitted open guide.")
            if len(end_fit.edges) != group.ribbon_lines + 1:
                raise ValueError("A connected ribbon end needs complete fitted lobe edges.")
            profile = connection_profile_frames(design, connection, {})[0]
            for attachment in connection.attachment_children(None):
                if not attachment.has_target:
                    continue
                if attachment.pin_number is None:
                    raise ValueError("A connected ribbon root needs an assigned line pin.")
                line_index = int(attachment.pin_number) - 1
                if not 0 <= line_index < group.ribbon_lines:
                    raise ValueError("A ribbon root pin is outside its line count.")
                lane = fitted.shape.lanes[line_index]
                if len(lane) < 2:
                    raise ValueError("A connected ribbon line needs two fitted route samples.")
                center = lane[0 if at_start else -1]
                inside = lane[1 if at_start else -2]
                inward = difference(inside, center)
                if magnitude(inward) <= 1e-9:
                    raise ValueError("A connected ribbon line has no usable end tangent.")
                guides[group.cable_group_id, connection_id, attachment.attachment_id] = (
                    ProfileFrame(
                        center,
                        unit(inward),
                        profile.u_direction,
                        profile.v_direction,
                        ribbon_connection_diameter_mm=_fitted_connection_diameter(
                            center,
                            end_fit.edges[line_index],
                            end_fit.edges[line_index + 1],
                            ffc.trace_width_mm if ffc is not None else group.diameter_mm,
                        ),
                        ribbon_terminal_tangent=_terminal_lane_tangent(lane, at_start=at_start),
                    )
                )
    return guides
