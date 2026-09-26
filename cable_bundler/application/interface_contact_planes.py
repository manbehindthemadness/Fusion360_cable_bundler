"""
Select compatible contact centers inside a locally oriented planar rectangle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from .interface_contact_rows import RowTarget, _same_geometry


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    """
    Measure a vector's component along an axis.
    """
    return sum(x * y for x, y in zip(a, b))


@dataclass(frozen=True)
class ContactRectangle:
    """
    Retain diagonal targets and an orthonormal frame fixed to their local plane.
    """

    first: RowTarget
    last: RowTarget
    x_axis: tuple[float, ...]
    y_axis: tuple[float, ...]
    normal: tuple[float, ...]

    def coordinates(self, target: RowTarget) -> tuple[float, float, float]:
        """
        Express a center relative to the first pick in rectangle coordinates.
        """
        delta = tuple(b - a for a, b in zip(self.first.center_mm, target.center_mm))
        return _dot(delta, self.x_axis), _dot(delta, self.y_axis), _dot(delta, self.normal)

    def bounds(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """
        Return assembly-space bounds enclosing all four corners for cheap rejection.
        """
        x, y, _ = self.coordinates(self.last)
        corners = [
            tuple(
                p + u * a + v * b for p, a, b in zip(self.first.center_mm, self.x_axis, self.y_axis)
            )
            for u, v in ((0, 0), (x, 0), (0, y), (x, y))
        ]
        return tuple(map(min, zip(*corners))), tuple(map(max, zip(*corners)))


def contact_rectangle(
    first: RowTarget, last: RowTarget, parent_axes: Sequence[Sequence[float]]
) -> ContactRectangle:
    """
    Resolve two diagonal picks using the target normal and projected parent axes.

    Unoriented points use the parent's XY plane. Reject noncoplanar or degenerate
    diagonals rather than guessing an arbitrary plane from only two points.
    """
    if first.token == last.token or not _same_geometry(first, last):
        raise ValueError("Pick different plane corners with the same target type and orientation.")
    if len(parent_axes) != 3 or any(
        len(axis) != 3 or not all(map(math.isfinite, axis)) or math.hypot(*axis) < 1e-9
        for axis in parent_axes
    ):
        raise ValueError("The target's local frame is unavailable.")
    normal = first.normal or parent_axes[2]
    normal = tuple(value / math.hypot(*normal) for value in normal)
    projected = [
        tuple(value - _dot(axis, normal) * n for value, n in zip(axis, normal))
        for axis in parent_axes
    ]
    axis = next((axis for axis in projected if math.hypot(*axis) > 1e-6), None)
    if axis is None:
        raise ValueError("The target's local plane is unavailable.")
    x_axis = tuple(value / math.hypot(*axis) for value in axis)
    y_axis = (
        normal[1] * x_axis[2] - normal[2] * x_axis[1],
        normal[2] * x_axis[0] - normal[0] * x_axis[2],
        normal[0] * x_axis[1] - normal[1] * x_axis[0],
    )
    rectangle = ContactRectangle(first, last, x_axis, y_axis, normal)
    x, y, depth = rectangle.coordinates(last)
    if abs(depth) > 0.001:
        raise ValueError("Plane corners must lie on the same plane.")
    if abs(x) <= 1e-6 or abs(y) <= 1e-6:
        raise ValueError("Pick diagonal corners spanning both local directions, not one row.")
    return rectangle


def select_contact_plane(
    rectangle: ContactRectangle, candidates: Iterable[RowTarget]
) -> tuple[RowTarget, ...]:
    """
    Include compatible coplanar centers inside the closed rectangle in stable row order.
    """
    first, last = rectangle.first, rectangle.last
    width, height, _ = rectangle.coordinates(last)
    chosen = {first.token: first, last.token: last}
    for candidate in candidates:
        if candidate.token in chosen or not _same_geometry(first, candidate):
            continue
        x, y, depth = rectangle.coordinates(candidate)
        if (
            min(0, width) - 1e-6 <= x <= max(0, width) + 1e-6
            and min(0, height) - 1e-6 <= y <= max(0, height) + 1e-6
            and abs(depth) <= 0.001
        ):
            chosen[candidate.token] = candidate

    def order(target: RowTarget) -> tuple[float, float, str]:
        """
        Traverse rows from the first picked corner toward the opposite corner.
        """
        x, y, _ = rectangle.coordinates(target)
        return round(y / height, 8), round(x / width, 8), target.token

    return tuple(sorted(chosen.values(), key=order))
