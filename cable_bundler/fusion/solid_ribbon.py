"""
Plan one contact-to-contact ribbon loft without creating branch solids.
"""

from __future__ import annotations

from dataclasses import dataclass

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import CableGroupRouteLeg
from ..domain import CableGroupDefinition, HarnessDefinition
from ..routing import RibbonShape, RoutePreview, Vector3
from ..routing.geometry import difference, dot, magnitude, unit
from .route_preview_parts.frames import connection_attachment_frame, connection_profile_frames

SOLID_RIBBON_LEAD_FRACTIONS = (0.0, 0.25, 0.5, 0.75)


@dataclass(frozen=True)
class SolidRibbonSection:
    """
    Describe a joined cross-section in world millimeters.
    """

    centers: tuple[Vector3, ...]
    normal: Vector3
    width: Vector3
    lobe_width_mm: float


@dataclass(frozen=True)
class SolidRibbonPlan:
    """
    Retain all loft stations, preview lanes, and persistent contact identities.
    """

    sections: tuple[SolidRibbonSection, ...]
    lanes: tuple[tuple[Vector3, ...], ...]
    contact_ids: tuple[tuple[str, ...], tuple[str, ...]]
    attachment_ids: tuple[tuple[str, ...], tuple[str, ...]]
    contact_signature: tuple[tuple[float, ...], ...]


def _branch_point(route: RoutePreview, fraction: float) -> Vector3:
    """
    Sample a contact-to-guide branch in its saved curve order.
    """
    scaled = fraction * len(route.curves)
    index = min(len(route.curves) - 1, int(scaled))
    return route.curves[index].point(min(1.0, scaled - index))


def _project(point: Vector3, origin: Vector3, normal: Vector3) -> Vector3:
    """
    Place a contact onto the common plane without checking other target locations.
    """
    return point.translated(normal, -dot(difference(point, origin), normal))


def _section(
    centers: tuple[Vector3, ...], normal: Vector3, guide_width: Vector3, diameter_mm: float
) -> SolidRibbonSection:
    """
    Flatten lanes onto the section plane and fit lobe width to their pitch.
    """
    plane_normal = unit(normal)
    planar_centers = tuple(_project(center, centers[0], plane_normal) for center in centers)
    width_delta = difference(planar_centers[-1], planar_centers[0])
    if magnitude(width_delta) > 1e-8:
        width = unit(width_delta)
    else:
        planar_guide_width = guide_width.translated(plane_normal, -dot(guide_width, plane_normal))
        width = unit(planar_guide_width)
    pitches = tuple(
        dot(difference(right, left), width)
        for left, right in zip(planar_centers, planar_centers[1:])
    )
    if any(pitch <= 1e-6 for pitch in pitches):
        raise ValueError("Solid ribbon contacts are not ordered across the ribbon width.")
    lobe_width = min(diameter_mm, *(pitch * 0.98 for pitch in pitches))
    return SolidRibbonSection(planar_centers, plane_normal, width, lobe_width)


def _uniform_sections(
    sections: tuple[SolidRibbonSection, ...], diameter_mm: float
) -> tuple[SolidRibbonSection, ...]:
    """
    Carry the first contact bank's pitch and lobe size through the entire ribbon.
    """
    line_count = len(sections[0].centers)
    pitch = (
        magnitude(difference(sections[0].centers[-1], sections[0].centers[0])) / (line_count - 1)
        if line_count > 1
        else diameter_mm
    )
    lobe_width = min(diameter_mm, pitch * 0.98) if line_count > 1 else diameter_mm
    half_index = (line_count - 1) / 2.0
    uniform: list[SolidRibbonSection] = []
    for section in sections:
        first, last = section.centers[0], section.centers[-1]
        midpoint = Vector3(
            (first.x + last.x) / 2.0,
            (first.y + last.y) / 2.0,
            (first.z + last.z) / 2.0,
        )
        centers = tuple(
            midpoint.translated(section.width, (index - half_index) * pitch)
            for index in range(line_count)
        )
        uniform.append(SolidRibbonSection(centers, section.normal, section.width, lobe_width))
    return tuple(uniform)


def solid_ribbon_plan(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    group: CableGroupDefinition,
    leg: CableGroupRouteLeg,
    branches: tuple[tuple[CableGroupRouteLeg, RoutePreview], ...],
    shape: RibbonShape,
) -> SolidRibbonPlan:
    """
    Resolve complete numbered Interface contacts and loft stations at both ends.

    Branch curves are consumed only as lane paths; they never become separate bodies.
    """
    contact_tokens = {
        (contact.kind, contact.entity_token): str(contact.contact_id)
        for interface in definition.interfaces
        for contact in interface.contacts
    }
    connections = {connection.connection_id: connection for connection in definition.connections}
    ends: list[tuple[SolidRibbonSection, ...]] = []
    identities: list[tuple[str, ...]] = []
    attachment_identities: list[tuple[str, ...]] = []
    for connection_id, at_start in (
        (leg.start_connection_id, True),
        (leg.end_connection_id, False),
    ):
        if connection_id is None or connection_id not in connections:
            raise ValueError("Solid ribbon requires a saved Interface connection at both ends.")
        connection = connections[connection_id]
        roots = connection.attachment_children(None)
        by_pin = {}
        for root in roots:
            if any(
                item.parent_attachment_id == root.attachment_id and item.has_target
                for item in connection.attachments
            ):
                raise ValueError(
                    "Solid ribbon does not support child connection targets; use Split."
                )
            if not root.has_target:
                continue
            if (root.target_kind, root.entity_token) not in contact_tokens:
                raise ValueError(
                    "Solid ribbon requires every target to remain linked to an Interface contact."
                )
            if root.pin_number is None:
                raise ValueError(
                    "Solid ribbon requires a numbered contact for every line at both ends."
                )
            pin = int(root.pin_number)
            if pin in by_pin or not 1 <= pin <= group.ribbon_lines:
                raise ValueError("Solid ribbon has duplicate or out-of-range contact pins.")
            by_pin[pin] = root
        if set(by_pin) != set(range(1, group.ribbon_lines + 1)):
            raise ValueError(
                "Solid ribbon requires one target contact for every line at both ends."
            )
        routes_by_attachment = {
            branch_leg.attachment_id: route
            for branch_leg, route in branches
            if branch_leg.start_connection_id == connection_id
        }
        if set(routes_by_attachment) != {root.attachment_id for root in by_pin.values()}:
            raise ValueError("Solid ribbon needs one routed contact lead for each numbered line.")
        ordered = tuple(by_pin[pin] for pin in range(1, group.ribbon_lines + 1))
        guide = connection_profile_frames(design, connection, {})[0]
        first_frame = connection_attachment_frame(design, connection, ordered[0], guide, {})
        if first_frame is None:
            raise ValueError("Solid ribbon's first numbered contact is unavailable.")
        normal = unit(first_frame.normal)
        guide_frame = shape.frames[0 if at_start else -1]
        if dot(normal, guide_frame.tangent) < 0.0:
            normal = Vector3(-normal.x, -normal.y, -normal.z)
        routes = tuple(routes_by_attachment[root.attachment_id] for root in ordered)
        stations: list[SolidRibbonSection] = []
        for fraction in SOLID_RIBBON_LEAD_FRACTIONS:
            raw = tuple(_branch_point(route, fraction) for route in routes)
            if fraction == 0.0:
                centers = tuple(_project(point, first_frame.origin, normal) for point in raw)
                section_normal = normal
            else:
                near = tuple(_branch_point(route, min(1.0, fraction + 0.01)) for route in routes)
                far = tuple(_branch_point(route, max(0.0, fraction - 0.01)) for route in routes)
                tangent = difference(
                    Vector3(
                        *(sum(getattr(point, axis) for point in near) / len(near) for axis in "xyz")
                    ),
                    Vector3(
                        *(sum(getattr(point, axis) for point in far) / len(far) for axis in "xyz")
                    ),
                )
                section_normal = unit(tangent) if magnitude(tangent) > 1e-8 else guide_frame.tangent
                if not at_start:
                    section_normal = Vector3(
                        -section_normal.x, -section_normal.y, -section_normal.z
                    )
                centers = tuple(_project(point, raw[0], section_normal) for point in raw)
            stations.append(_section(centers, section_normal, guide_frame.width, group.diameter_mm))
        ends.append(tuple(stations))
        identities.append(
            tuple(contact_tokens[(root.target_kind, root.entity_token)] for root in ordered)
        )
        attachment_identities.append(tuple(str(root.attachment_id) for root in ordered))
    middle = tuple(
        _section(
            tuple(lane[index] for lane in shape.lanes),
            frame.tangent,
            frame.width,
            group.diameter_mm,
        )
        for index, frame in enumerate(shape.frames)
    )
    sections = _uniform_sections(ends[0] + middle + tuple(reversed(ends[1])), group.diameter_mm)
    lanes = tuple(
        tuple(section.centers[index] for section in sections) for index in range(group.ribbon_lines)
    )
    signatures = [
        tuple(coordinate for point in section.centers for coordinate in (point.x, point.y, point.z))
        + (section.normal.x, section.normal.y, section.normal.z)
        for section in (sections[0], sections[-1])
    ]
    return SolidRibbonPlan(
        sections,
        lanes,
        (identities[0], identities[1]),
        (attachment_identities[0], attachment_identities[1]),
        tuple(signatures),
    )
