"""
Select ordered contact rows from geometry expressed in one shared frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from ..domain import AttachmentTargetKind

ROW_TOLERANCE_MM = 0.1


class ContactSelectionMode(str, Enum):
    """
    Distinguish manual collection from endpoint-defined rows and rectangles.
    """

    MANUAL = "manual"
    ROW = "row"
    PLANE = "plane"


@dataclass(frozen=True)
class RowTarget:
    """
    Describe a persistent target center and geometry orientation in millimeters.
    """

    token: str
    kind: AttachmentTargetKind
    geometry_type: str
    center_mm: tuple[float, float, float]
    normal: tuple[float, float, float] | None

    def __post_init__(self) -> None:
        """
        Reject incomplete centers and invalid orientation vectors at the boundary.
        """
        if (
            not self.token
            or len(self.center_mm) != 3
            or not all(map(math.isfinite, self.center_mm))
        ):
            raise ValueError("Row targets need a persistent identity and finite center.")
        if self.normal is not None and (
            len(self.normal) != 3
            or not all(map(math.isfinite, self.normal))
            or math.hypot(*self.normal) < 1e-9
        ):
            raise ValueError("Row target orientation is unavailable.")


def _same_geometry(first: RowTarget, candidate: RowTarget) -> bool:
    """
    Match target and surface types plus directed orientation within one degree.
    """
    if first.kind is not candidate.kind or first.geometry_type != candidate.geometry_type:
        return False
    if first.normal is None or candidate.normal is None:
        return first.normal is candidate.normal
    alignment = sum(a * b for a, b in zip(first.normal, candidate.normal))
    alignment /= math.hypot(*first.normal) * math.hypot(*candidate.normal)
    return alignment >= math.cos(math.radians(1))


def select_contact_row(
    first: RowTarget,
    last: RowTarget,
    candidates: Iterable[RowTarget],
    tolerance_mm: float = ROW_TOLERANCE_MM,
) -> tuple[RowTarget, ...]:
    """
    Collect matching centers along the finite first-to-last segment, in pick order.

    The 3D calculation is invariant under translation and rotation of the parent;
    it does not assume global Z is up. Endpoints are always included. Opposite
    facing surfaces, parallel neighboring rows, and targets beyond the ends are
    excluded. Oriented targets additionally require depth agreement within
    0.001 mm so thin adjacent faces do not join the row. The caller restricts
    candidates to one owning sketch or occurrence.
    """
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0:
        raise ValueError("Row tolerance must be positive and finite.")
    if first.token == last.token:
        raise ValueError("Pick two different row endpoints.")
    if not _same_geometry(first, last):
        raise ValueError("Row endpoints must have the same target type and orientation.")
    vector = tuple(b - a for a, b in zip(first.center_mm, last.center_mm))
    length = math.hypot(*vector)
    if length <= 1e-6:
        raise ValueError("Row endpoints must have different centers.")
    direction = tuple(value / length for value in vector)
    chosen = {first.token: (0.0, first), last.token: (length, last)}
    for candidate in candidates:
        if candidate.token in chosen or not _same_geometry(first, candidate):
            continue
        offset = tuple(b - a for a, b in zip(first.center_mm, candidate.center_mm))
        along = sum(a * b for a, b in zip(offset, direction))
        deviation = tuple(value - along * axis for value, axis in zip(offset, direction))
        distance = math.hypot(*deviation)
        depth_error = (
            0.0
            if first.normal is None
            else abs(sum(value * axis for value, axis in zip(deviation, first.normal)))
            / math.hypot(*first.normal)
        )
        if (
            0 <= along <= length
            and distance <= tolerance_mm
            and depth_error <= min(tolerance_mm, 0.001)
        ):
            chosen[candidate.token] = (along, candidate)
    return tuple(
        item for _, item in sorted(chosen.values(), key=lambda pair: (pair[0], pair[1].token))
    )
