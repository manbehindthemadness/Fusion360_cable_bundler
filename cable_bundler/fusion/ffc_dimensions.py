"""
Measure FFC layout from persistent, numbered Interface contact targets.
"""

from __future__ import annotations

import math
from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import CableGroupDefinition, HarnessDefinition
from ..domain.ffc import FfcDimensions, resolve_ffc_dimensions
from ..routing import Vector3
from ..routing.geometry import difference, magnitude, unit
from .interface_contact_projection import project_interface_contact
from .route_preview_parts.frames import connection_attachment_frame, connection_profile_frames


def _contact_width_mm(projection: dict[str, object], across: Vector3) -> Optional[float]:
    """
    Measure valid outline points along the ribbon; absent outlines use Auto fallback.
    """
    raw_loops = projection.get("loops")
    if not isinstance(raw_loops, (list, tuple)):
        return None
    coordinates = []
    for loop in raw_loops:
        if not isinstance(loop, (list, tuple)):
            continue
        for point in loop:
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                continue
            try:
                values = tuple(float(value) for value in point)
            except (TypeError, ValueError):
                continue
            if all(math.isfinite(value) for value in values):
                coordinates.append(
                    values[0] * across.x + values[1] * across.y + values[2] * across.z
                )
    extent = max(coordinates) - min(coordinates) if coordinates else 0.0
    return extent if math.isfinite(extent) and extent > 1e-6 else None


def ffc_contact_geometry(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
) -> tuple[float, tuple[Optional[float], ...]]:
    """
    Measure the first end's ordered contact pitch and widths along its width axis.
    """
    if not group.connection_ids:
        raise ValueError("FFC requires a numbered Interface contact.")
    connections = {item.connection_id: item for item in definition.connections}
    connection = connections.get(group.connection_ids[0])
    if connection is None:
        raise ValueError("FFC first connection is unavailable.")
    contacts = {
        (contact.kind, contact.entity_token): contact
        for interface in definition.interfaces
        for contact in interface.contacts
    }
    targeted = tuple(item for item in connection.attachment_children(None) if item.has_target)
    roots = {int(item.pin_number): item for item in targeted if item.pin_number is not None}
    if len(roots) != len(targeted) or set(roots) != set(range(1, group.ribbon_lines + 1)):
        raise ValueError("FFC requires one numbered Interface contact for each trace.")
    guide = connection_profile_frames(design, connection, {})[0]
    centers = []
    ordered_contacts = []
    for index in range(1, group.ribbon_lines + 1):
        root = roots[index]
        contact = contacts.get((root.target_kind, root.entity_token))
        if contact is None:
            raise ValueError("FFC trace targets must belong to saved Interfaces.")
        frame = connection_attachment_frame(design, connection, root, guide, {})
        if frame is None:
            raise ValueError("FFC contact target is unavailable.")
        centers.append(frame.origin)
        ordered_contacts.append(contact)
    if group.ribbon_lines == 1:
        across = unit(guide.u_direction)
    else:
        span = difference(centers[-1], centers[0])
        pitch = magnitude(span) / (group.ribbon_lines - 1)
        if not math.isfinite(pitch) or pitch <= 1e-6:
            raise ValueError("FFC contact centers have no usable pitch.")
        across = unit(span)
    widths: list[Optional[float]] = []
    for contact in ordered_contacts:
        projection = project_interface_contact(design, contact)
        widths.append(_contact_width_mm(projection, across))
    if group.ribbon_lines == 1:
        contact_width = widths[0]
        trace_width = group.trace_width_mm
        spacing = group.trace_spacing_mm
        if trace_width is not None and spacing is not None:
            pitch = trace_width + spacing
        elif trace_width is not None:
            pitch = max(trace_width * 1.25, contact_width or 0.0)
        elif contact_width is not None:
            pitch = contact_width + spacing if spacing is not None else contact_width * 1.25
        else:
            raise ValueError(
                "Single-trace FFC needs an explicit Trace Width or a measurable contact width."
            )
    return pitch, tuple(widths)


def ffc_dimensions(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
) -> FfcDimensions:
    """
    Resolve persisted Auto and explicit settings against live Interface geometry.
    """
    pitch, widths = ffc_contact_geometry(design, definition, group)
    return resolve_ffc_dimensions(pitch, widths, group.trace_width_mm, group.trace_spacing_mm)
