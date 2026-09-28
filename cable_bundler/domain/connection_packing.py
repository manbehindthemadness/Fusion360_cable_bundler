"""
Pack circular connection branches inside their immediate parent face.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Optional

_LOOSE_SCALE = 0.85
_TOLERANCE_MM = 1e-8
_DIRECTIONS = tuple(
    (math.cos(math.tau * index / 24), math.sin(math.tau * index / 24)) for index in range(24)
)


@dataclass(frozen=True)
class PackedConnection:
    """
    Describe one resolved branch circle in parent-face coordinates.
    """

    x_mm: float
    y_mm: float
    diameter_mm: float


def _hex_positions(diameter_mm: float) -> Iterator[tuple[float, float]]:
    """
    Yield a centered hex lattice in stable, expanding ring order.
    """
    yield 0.0, 0.0
    ring = 1
    while True:
        q, r = ring, 0
        for step_q, step_r in ((-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (0, 1)):
            for _ in range(ring):
                yield (q + r / 2.0) * diameter_mm, r * math.sqrt(3) / 2 * diameter_mm
                q += step_q
                r += step_r
        ring += 1


def _center(circles: tuple[PackedConnection, ...]) -> tuple[PackedConnection, ...]:
    """
    Recenter a nonoverlapping cluster at its bounding-box midpoint.
    """
    left = min(circle.x_mm - circle.diameter_mm / 2 for circle in circles)
    right = max(circle.x_mm + circle.diameter_mm / 2 for circle in circles)
    bottom = min(circle.y_mm - circle.diameter_mm / 2 for circle in circles)
    top = max(circle.y_mm + circle.diameter_mm / 2 for circle in circles)
    center_x = (left + right) / 2
    center_y = (bottom + top) / 2
    return tuple(
        PackedConnection(circle.x_mm - center_x, circle.y_mm - center_y, circle.diameter_mm)
        for circle in circles
    )


def _cluster(diameters_mm: tuple[float, ...]) -> tuple[PackedConnection, ...]:
    """
    Greedily nest disks by tangency, recentering the resulting cluster.

    The stable largest-first order prioritizes large fixed circles while
    equal-size ties retain the saved contact order.
    """
    if len(diameters_mm) >= 4 and len(set(diameters_mm)) == 1:
        diameter = diameters_mm[0]
        positions = _hex_positions(diameter)
        return _center(tuple(PackedConnection(*next(positions), diameter) for _ in diameters_mm))
    if len(diameters_mm) >= 40:
        common = max(set(diameters_mm), key=lambda value: (diameters_mm.count(value), -value))
        exceptional = tuple(
            (index, diameter) for index, diameter in enumerate(diameters_mm) if diameter != common
        )
        if len(exceptional) <= 8:
            fixed = _cluster(tuple(diameter for _, diameter in exceptional)) if exceptional else ()
            placed: dict[int, PackedConnection] = {
                index: circle for (index, _diameter), circle in zip(exceptional, fixed)
            }
            if common == 0.0:
                edge_x = max(
                    (circle.x_mm + circle.diameter_mm / 2 for circle in fixed),
                    default=0.0,
                )
                return _center(
                    tuple(
                        placed.get(index, PackedConnection(edge_x, 0.0, 0.0))
                        for index in range(len(diameters_mm))
                    )
                )
            positions = _hex_positions(common)
            for index, diameter in enumerate(diameters_mm):
                if index in placed:
                    continue
                for x, y in positions:
                    if all(
                        math.hypot(x - circle.x_mm, y - circle.y_mm)
                        >= (diameter + circle.diameter_mm) / 2 - _TOLERANCE_MM
                        for circle in fixed
                    ):
                        placed[index] = PackedConnection(x, y, diameter)
                        break
            return _center(tuple(placed[index] for index in range(len(diameters_mm))))
    placed: list[tuple[int, float, float, float]] = []
    for index in sorted(range(len(diameters_mm)), key=lambda item: (-diameters_mm[item], item)):
        radius = diameters_mm[index] / 2.0
        if not placed:
            placed.append((index, 0.0, 0.0, radius))
            continue
        best: Optional[tuple[float, float, float]] = None
        for _other_index, other_x, other_y, other_radius in placed:
            separation = radius + other_radius
            for direction_x, direction_y in _DIRECTIONS:
                x = other_x + separation * direction_x
                y = other_y + separation * direction_y
                if any(
                    math.hypot(x - item_x, y - item_y) < radius + item_radius - _TOLERANCE_MM
                    for _item_index, item_x, item_y, item_radius in placed
                ):
                    continue
                circles = (*placed, (index, x, y, radius))
                left = min(item_x - item_radius for _, item_x, _, item_radius in circles)
                right = max(item_x + item_radius for _, item_x, _, item_radius in circles)
                bottom = min(item_y - item_radius for _, _, item_y, item_radius in circles)
                top = max(item_y + item_radius for _, _, item_y, item_radius in circles)
                center_x = (left + right) / 2.0
                center_y = (bottom + top) / 2.0
                extent = max(
                    math.hypot(item_x - center_x, item_y - center_y) + item_radius
                    for _, item_x, item_y, item_radius in circles
                )
                candidate = (extent, x, y)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            raise ValueError("Connection circles could not be arranged.")
        placed.append((index, best[1], best[2], radius))
    left = min(x - radius for _, x, _, radius in placed)
    right = max(x + radius for _, x, _, radius in placed)
    bottom = min(y - radius for _, _, y, radius in placed)
    top = max(y + radius for _, _, y, radius in placed)
    center_x = (left + right) / 2.0
    center_y = (bottom + top) / 2.0
    return tuple(
        PackedConnection(x - center_x, y - center_y, radius * 2.0)
        for _index, x, y, radius in sorted(placed)
    )


def required_parent_diameter(diameters_mm: tuple[float, ...]) -> float:
    """
    Return the enclosing diameter of a deterministic nonoverlapping cluster.
    """
    if not diameters_mm:
        return 0.0
    circles = _cluster(diameters_mm)
    return 2.0 * max(
        math.hypot(circle.x_mm, circle.y_mm) + circle.diameter_mm / 2.0 for circle in circles
    )


def pack_connections(
    parent_diameter_mm: float,
    configured_diameters_mm: tuple[Optional[float], ...],
) -> Optional[tuple[PackedConnection, ...]]:
    """
    Resolve automatic diameters with slack and pack all sibling branches.

    Explicit diameters never shrink. A null result means they cannot fit, or
    they leave no positive room for an automatic sibling.
    """
    if not configured_diameters_mm:
        return ()
    if len(configured_diameters_mm) == 1:
        diameter = configured_diameters_mm[0] or parent_diameter_mm
        return (
            (PackedConnection(0.0, 0.0, diameter),)
            if diameter <= parent_diameter_mm + _TOLERANCE_MM
            else None
        )
    fixed = tuple(value or 0.0 for value in configured_diameters_mm)
    if required_parent_diameter(fixed) > parent_diameter_mm + _TOLERANCE_MM:
        return None
    if all(value is not None for value in configured_diameters_mm):
        return _cluster(fixed)
    lower = 0.0
    upper = parent_diameter_mm
    for _ in range(26):
        middle = (lower + upper) / 2.0
        trial = tuple(value if value is not None else middle for value in configured_diameters_mm)
        if required_parent_diameter(trial) <= parent_diameter_mm + _TOLERANCE_MM:
            lower = middle
        else:
            upper = middle
    automatic_diameter = lower * _LOOSE_SCALE
    for _ in range(20):
        if automatic_diameter <= _TOLERANCE_MM:
            return None
        diameters = tuple(
            value if value is not None else automatic_diameter for value in configured_diameters_mm
        )
        if required_parent_diameter(diameters) <= parent_diameter_mm + _TOLERANCE_MM:
            return _cluster(diameters)
        automatic_diameter *= _LOOSE_SCALE
    return None
