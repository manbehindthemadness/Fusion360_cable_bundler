"""
Collect plane contacts within one Fusion sketch or component occurrence.
"""

from __future__ import annotations

from typing import Any

from ..application.interface_contact_planes import (
    ContactRectangle,
    contact_rectangle,
    select_contact_plane,
)
from ..application.interface_contact_rows import RowTarget
from ..domain import AttachmentTargetKind
from .interface_contact_projection import _parent_axes
from .interface_contact_rows import (
    _candidates,
    _near_segment_bounds,
    _scope,
    describe_row_target,
)


def validate_plane_corners(first: Any, last: Any) -> ContactRectangle:
    """
    Validate the diagonal in its local frame without scanning neighboring geometry.
    """
    if _scope(first).key != _scope(last).key:
        raise ValueError("Pick plane corners in the same sketch or component occurrence.")
    axes = _parent_axes(first)
    if axes is None:
        if _scope(first).occurrence is not None or getattr(first, "parentSketch", None) is not None:
            raise ValueError("The target's local frame is unavailable.")
        axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    return contact_rectangle(describe_row_target(first), describe_row_target(last), axes)


def collect_contact_plane(first: Any, last: Any) -> tuple[RowTarget, ...]:
    """
    Collect matching centers inside the rectangle, skipping unavailable neighbors.
    """
    rectangle = validate_plane_corners(first, last)
    lower, upper = rectangle.bounds()
    candidates = []
    for entity in _candidates(_scope(first), rectangle.first.kind):
        try:
            if not _near_segment_bounds(entity, lower, upper):
                continue
            if rectangle.first.kind is AttachmentTargetKind.FACE and (
                entity.geometry.objectType != rectangle.first.geometry_type
            ):
                continue
            candidates.append(describe_row_target(entity))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    return select_contact_plane(rectangle, candidates)
