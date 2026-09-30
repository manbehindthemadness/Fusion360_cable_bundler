"""
Locate numbered ribbon connection roots on their fitted line end faces.
"""

from __future__ import annotations

from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg
from ...domain import CableGroupType, HarnessDefinition
from ...routing import RoutePreview
from ...routing.geometry import difference, magnitude, unit
from ..ribbon_geometry import ribbon_route_shape
from .frames import ProfileFrame, connection_profile_frames


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
        fitted = ribbon_route_shape(
            design, definition, leg, route, group.ribbon_lines, group.diameter_mm
        )
        for connection_id, at_start in attached_ends:
            connection = connections[connection_id]
            end_fit = fitted.shape.start_fit if at_start else fitted.shape.end_fit
            if end_fit is None:
                raise ValueError("A connected ribbon end needs a usable fitted open guide.")
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
                    )
                )
    return guides
