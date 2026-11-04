"""
Select separated gym cubicles without changing historical layout replay.
"""

from __future__ import annotations

import random
from functools import lru_cache

from .scene import ZONES, Config, Goal, Scene, generate


def adjacent(first: int, second: int) -> bool:
    """
    Identify cubicles sharing a face, edge or corner, including coincident cells.

    Indices use the existing zero-based gym order. Separation requires a
    difference of two cells along at least one axis, independent of dimensions.
    """
    if any(type(zone) is not int or not 0 <= zone < len(ZONES) for zone in (first, second)):
        raise ValueError("Supply cubicle indices in 0..25.")
    return max(abs(a - b) for a, b in zip(ZONES[first], ZONES[second])) <= 1


def allowed_pairs(
    a_zones: tuple[int, ...], b_zones: tuple[int, ...], *, avoid_adjacent_zones: bool
) -> tuple[tuple[int, int], ...]:
    """
    Filter ordered pairs before scheduling; never retry or consult solver results.
    """
    if type(avoid_adjacent_zones) is not bool:
        raise ValueError("Choose explicitly whether to avoid adjacent cubicles.")
    for zone in (*a_zones, *b_zones):
        adjacent(zone, zone)
    return tuple(
        (a, b)
        for a in a_zones
        for b in b_zones
        if a != b and (not avoid_adjacent_zones or not adjacent(a, b))
    )


@lru_cache(maxsize=1)
def _separated_pairs() -> tuple[tuple[int, int], ...]:
    """
    Cache the dimension-independent choices for new interactive layouts.
    """
    zones = tuple(range(len(ZONES)))
    return allowed_pairs(zones, zones, avoid_adjacent_zones=True)


def generate_layout(config: Config | None = None, *, avoid_adjacent_zones: bool = True) -> Scene:
    """
    Choose directly from allowed pairs; disabling preserves the legacy seed mapping.

    This placement policy does not certify cable reachability or collision freedom.
    Explicit historical scene goals remain authoritative and need no migration.
    """
    if type(avoid_adjacent_zones) is not bool:
        raise ValueError("Choose explicitly whether to avoid adjacent cubicles.")
    if not avoid_adjacent_zones:
        return generate(config)
    config = config or Config()
    rng = random.Random(f"ribbon-gym-separated-v1:{config.seed}")
    a, b = rng.choice(_separated_pairs())
    return Scene(
        config,
        Goal(a, rng.randrange(12), rng.randrange(4)),
        Goal(b, rng.randrange(12), rng.randrange(4)),
    )
