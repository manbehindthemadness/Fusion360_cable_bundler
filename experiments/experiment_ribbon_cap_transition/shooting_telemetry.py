"""
Describe existing fit evaluations without adding probes or changing acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .director_route_objective import ObjectiveScope


def components(errors: tuple[float, ...], scope: ObjectiveScope) -> dict[str, float]:
    """
    Split the registered objective into squared component sums without reordering it.
    """
    stride = 4 if scope is ObjectiveScope.LEGACY_SPHERE else 3
    if len(errors) != 9 + 33 * stride:
        raise ValueError("Unexpected compatible objective layout.")
    names = ("material", "center", "lane", "sphere")[:stride]
    parts = {
        name: sum(v * v for v in errors[start : start + 3])
        for name, start in (("position", 0), ("tangent", 3), ("width", 6))
    }
    parts.update({name: sum(v * v for v in errors[9 + i :: stride]) for i, name in enumerate(names)})
    return parts


@dataclass(frozen=True)
class Trial:
    """
    Retain actual clipping and component tradeoffs for a scored full/half trial.
    """

    grid: int
    round_index: int
    fraction: float
    coordinates_before: tuple[float, ...]
    requested: tuple[float, ...]
    proposed: tuple[float, ...]
    before: dict[str, float]
    after: dict[str, float]
    accepted: bool

    @property
    def clipped(self) -> tuple[int, ...]:
        """
        Identify coordinates whose requested value exceeded a domain boundary.
        """
        return tuple(i for i, (a, b) in enumerate(zip(self.requested, self.proposed)) if a != b)


def coordinate_scales(values: tuple[float, ...], maximum_ratio: float) -> tuple[dict[str, float], ...]:
    """
    Show each raw coordinate relative to its own domain, not a physical percentage.
    """
    return tuple(
        {
            "value": value,
            "lower": -4 * math.pi if i < 5 else -3.0 if i < 9 else 1.0,
            "upper": 4 * math.pi if i < 5 else 3.0 if i < 9 else maximum_ratio,
            "domain_fraction": (value + 4 * math.pi) / (8 * math.pi)
            if i < 5
            else (value + 3) / 6
            if i < 9
            else (value - 1) / (maximum_ratio - 1),
        }
        for i, value in enumerate(values)
    )
