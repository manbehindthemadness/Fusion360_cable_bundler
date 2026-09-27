"""
Match saved Interface contacts by their orientation-local planar positions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

Vector = tuple[float, float, float]


@dataclass(frozen=True)
class OrientedContact:
    """
    Retain one resolved contact center and its parent-oriented viewing frame.
    """

    contact_id: UUID
    center_mm: Vector
    normal: Vector
    parent_axes: tuple[Vector, Vector, Vector] | None = None


def _dot(first: Vector, second: Vector) -> float:
    """
    Return the scalar projection of one vector onto another.
    """
    return sum(a * b for a, b in zip(first, second))


def _unit(vector: Vector) -> Vector:
    """
    Reject degenerate axes before building a local orientation frame.
    """
    length = math.sqrt(_dot(vector, vector))
    if not math.isfinite(length) or length < 1e-9:
        raise ValueError("An Interface contact has no usable orientation.")
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def _view_axes(contact: OrientedContact) -> tuple[Vector, Vector]:
    """
    Mirror the diagram's parent-forward viewing axes in model coordinates.
    """
    normal = _unit(contact.normal)
    parent = contact.parent_axes or ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    for candidate in (*parent[1:], parent[0], (0, 1, 0), (0, 0, 1), (1, 0, 0)):
        axis = _unit(candidate)
        alignment = _dot(axis, normal)
        projected = tuple(a - alignment * b for a, b in zip(axis, normal))
        magnitude = math.sqrt(_dot(projected, projected))
        if magnitude > 1e-6:
            y_axis = tuple(value / magnitude for value in projected)
            x_axis = (
                y_axis[1] * normal[2] - y_axis[2] * normal[1],
                y_axis[2] * normal[0] - y_axis[0] * normal[2],
                y_axis[0] * normal[1] - y_axis[1] * normal[0],
            )
            return x_axis, y_axis  # type: ignore[return-value]
    raise ValueError("An Interface contact has no planar orientation.")


def _orientation_positions(
    contacts: tuple[OrientedContact, ...],
) -> dict[UUID, tuple[float, float]]:
    """
    Position each orientation independently from its smallest local X and Y.
    """
    groups: list[list[OrientedContact]] = []
    for contact in contacts:
        normal = _unit(contact.normal)
        group = next(
            (items for items in groups if _dot(_unit(items[0].normal), normal) > 0.9999),
            None,
        )
        if group is None:
            groups.append([contact])
        else:
            group.append(contact)
    positions: dict[UUID, tuple[float, float]] = {}
    for group in groups:
        x_axis, y_axis = _view_axes(group[0])
        projected = [
            (_dot(contact.center_mm, x_axis), -_dot(contact.center_mm, y_axis)) for contact in group
        ]
        min_x = min(point[0] for point in projected)
        min_y = min(point[1] for point in projected)
        positions.update(
            (contact.contact_id, (point[0] - min_x, point[1] - min_y))
            for contact, point in zip(group, projected)
        )
    return positions


def match_projected_interface_contacts(
    destinations: tuple[OrientedContact, ...],
    sources: tuple[OrientedContact, ...],
    tolerance_mm: float = 0.1,
) -> dict[UUID, UUID]:
    """
    Return only unique one-to-one matches of orientation-local XY positions.

    Z, assembly placement, and contact shape do not participate. Repeated pads
    or multiple possible source orientations are deliberately left unmatched.
    """
    if tolerance_mm <= 0 or not math.isfinite(tolerance_mm):
        raise ValueError("Projection tolerance must be positive and finite.")
    target_positions = _orientation_positions(destinations)
    source_positions = _orientation_positions(sources)
    candidates = {
        target_id: [
            source_id
            for source_id, source_xy in source_positions.items()
            if math.dist(target_xy, source_xy) <= tolerance_mm
        ]
        for target_id, target_xy in target_positions.items()
    }
    return {
        target_id: source_ids[0]
        for target_id, source_ids in candidates.items()
        if len(source_ids) == 1
        and sum(source_ids[0] in others for others in candidates.values()) == 1
    }
