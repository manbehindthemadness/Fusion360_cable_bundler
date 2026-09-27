"""
Match saved Interface contacts by their actual projected assembly positions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

Vector = tuple[float, float, float]


@dataclass(frozen=True)
class OrientedContact:
    """
    Retain one resolved contact center and viewing-plane normal.
    """

    contact_id: UUID
    center_mm: Vector
    normal: Vector


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


def _planar_distance(first: Vector, second: Vector, normal: Vector) -> float:
    """
    Measure assembly-space separation after projecting onto the source plane.
    """
    offset = tuple(a - b for a, b in zip(first, second))
    depth = _dot(offset, normal)
    planar = tuple(value - depth * axis for value, axis in zip(offset, normal))
    return math.sqrt(_dot(planar, planar))


def _source_tolerance(
    source: OrientedContact,
    sources: tuple[OrientedContact, ...],
    maximum_mm: float,
) -> float:
    """
    Bound each pad's search region by its neighboring source-pad pitch.
    """
    normal = _unit(source.normal)
    distances = [
        _planar_distance(source.center_mm, other.center_mm, normal)
        for other in sources
        if other.contact_id != source.contact_id and _dot(normal, _unit(other.normal)) > 0.9999
    ]
    return min(maximum_mm, max(0.1, min(distances) * 0.75)) if distances else maximum_mm


def projected_interface_candidates(
    destinations: tuple[OrientedContact, ...],
    sources: tuple[OrientedContact, ...],
    tolerance_mm: float = 0.5,
) -> dict[UUID, tuple[UUID, ...]]:
    """
    Find source contacts close to each target in the source's actual plane.

    Each candidate preserves source identity so ambiguous metadata can be
    reviewed separately from the geometric lookup.
    """
    if tolerance_mm <= 0 or not math.isfinite(tolerance_mm):
        raise ValueError("Projection tolerance must be positive and finite.")
    source_radii = {
        source.contact_id: _source_tolerance(source, sources, tolerance_mm) for source in sources
    }
    return {
        target.contact_id: tuple(
            source.contact_id
            for source in sources
            if _planar_distance(target.center_mm, source.center_mm, _unit(source.normal))
            <= source_radii[source.contact_id]
        )
        for target in destinations
    }


def match_projected_interface_contacts(
    destinations: tuple[OrientedContact, ...],
    sources: tuple[OrientedContact, ...],
    tolerance_mm: float = 0.5,
) -> dict[UUID, UUID]:
    """
    Return unique one-to-one matches in each source contact's actual plane.

    Plane-normal displacement does not participate. A pitch-aware radius limits
    near misses; repeated pads or multiple candidates remain unmatched.
    """
    candidates = projected_interface_candidates(destinations, sources, tolerance_mm)
    return {
        target_id: source_ids[0]
        for target_id, source_ids in candidates.items()
        if len(source_ids) == 1
        and sum(source_ids[0] in others for others in candidates.values()) == 1
    }
