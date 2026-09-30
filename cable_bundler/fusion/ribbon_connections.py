"""
Number ribbon root connections against their physical open-end guide positions.
"""

from __future__ import annotations

from dataclasses import replace

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import CableGroupType, HarnessDefinition, RibbonGeometryType
from ..domain.ribbon_connections import assign_ribbon_pins
from ..routing import RibbonFrame
from ..routing.geometry import cross, unit
from .ribbon_geometry import _guide_fit
from .route_preview_parts.frames import connection_attachment_frame, connection_profile_frames


def number_ribbon_connections(
    design: adsk.fusion.Design, definition: HarnessDefinition
) -> HarnessDefinition:
    """
    Assign each newly targeted, unnumbered ribbon root one permanent line pin.

    Already numbered roots remain fixed. A missing Fusion target or guide fails
    the edit instead of persisting a guessed connection-to-line relationship.
    """
    groups = tuple(
        group
        for group in definition.cable_groups
        if group.group_type is CableGroupType.RIBBON
        and group.ribbon_geometry is RibbonGeometryType.DISCRETE
    )
    if not groups:
        return definition
    group_by_connection = {
        connection_id: group for group in groups for connection_id in group.connection_ids
    }
    updated = []
    for connection in definition.connections:
        group = group_by_connection.get(connection.connection_id)
        if group is None or not connection.attachments:
            updated.append(connection)
            continue
        roots = connection.attachment_children(None)
        if not roots:
            updated.append(connection)
            continue
        if all(root.pin_number is not None or not root.has_target for root in roots):
            updated.append(connection)
            continue
        guide = connection_profile_frames(design, connection, {})[0]
        width = unit(guide.u_direction)
        tangent = unit(guide.normal)
        frame = RibbonFrame(guide.origin, tangent, width, unit(cross(tangent, width)))
        fit, _plane = _guide_fit(
            design,
            connection.member_tokens[0],
            connection.resolved_member_alignments[0],
            frame,
            group.ribbon_lines,
            group.diameter_mm,
        )
        line_centers = tuple((point.x, point.y, point.z) for point in fit.centers)
        target_centers = {}
        for root in roots:
            if not root.has_target:
                continue
            target = connection_attachment_frame(design, connection, root, guide, {})
            if target is None:
                raise ValueError(f"Connection {root.display_name} no longer has a usable target.")
            target_centers[root.attachment_id] = (
                target.origin.x,
                target.origin.y,
                target.origin.z,
            )
        assigned = assign_ribbon_pins(roots, line_centers, target_centers)
        if not assigned:
            updated.append(connection)
            continue
        attachments = tuple(
            replace(item, pin_number=assigned[item.attachment_id])
            if item.attachment_id in assigned
            else item
            for item in connection.attachments
        )
        updated.append(
            replace(connection, attachment=attachments[0], additional_attachments=attachments[1:])
        )
    return replace(definition, connections=tuple(updated))
