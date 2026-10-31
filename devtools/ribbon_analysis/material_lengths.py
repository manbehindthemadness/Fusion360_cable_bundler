"""
Measure three corresponding material paths without inferring inextensibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Protocol

from cable_bundler.routing.geometry import Vector3, magnitude


class MaterialPaths(Protocol):
    """
    Supply path positions and derivatives in one shared material parameter.
    """

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return a material point and its actual derivative with respect to u.
        """
        ...


@dataclass(frozen=True)
class MaterialLengths:
    """
    Retain integrated lengths and sampled local mismatches, never a proof flag.
    """

    lengths_mm: tuple[float, float, float]
    spread_mm: float
    quadrature_difference_mm: float
    maximum_sampled_relative_speed_spread: float
    intervals: int


def measure_lengths(
    path: MaterialPaths,
    half_width_mm: float,
    *,
    intervals: int = 1024,
    checkpoint: Callable[[], None] | None = None,
) -> MaterialLengths:
    """
    Integrate left, center, right speeds with nested composite Simpson grids.

    The coarse/fine difference is a convergence observation, not an error bound
    or a physical tolerance. Sampled agreement alone cannot certify equal length.
    """
    if (
        isinstance(half_width_mm, bool)
        or not math.isfinite(half_width_mm)
        or half_width_mm <= 0
        or isinstance(intervals, bool)
        or not isinstance(intervals, int)
        or intervals % 4 != 0
        or not 4 <= intervals <= 8192
    ):
        raise ValueError("Positive finite width and4..8192intervals divisible by four required.")
    rows: list[tuple[float, float, float]] = []
    for i in range(intervals + 1):
        if checkpoint is not None and i % 64 == 0:
            checkpoint()
        left = magnitude(path.lane(i / intervals, half_width_mm)[1])
        center = magnitude(path.lane(i / intervals, 0)[1])
        right = magnitude(path.lane(i / intervals, -half_width_mm)[1])
        if not all(math.isfinite(value) and value > 0 for value in (left, center, right)):
            raise ValueError("Material paths must have finite positive speed.")
        rows.append((left, center, right))

    def integral(column: int, stride: int) -> float:
        """
        Integrate one speed column using only the selected nested grid.
        """
        values = [row[column] for row in rows[::stride]]
        return (
            (values[0] + values[-1] + 4 * math.fsum(values[1:-1:2]) + 2 * math.fsum(values[2:-1:2]))
            * stride
            / (3 * intervals)
        )

    lengths = (integral(0, 1), integral(1, 1), integral(2, 1))
    return MaterialLengths(
        lengths,
        max(lengths) - min(lengths),
        max(abs(lengths[i] - integral(i, 2)) for i in range(3)),
        max((max(row) - min(row)) / row[1] for row in rows),
        intervals,
    )
