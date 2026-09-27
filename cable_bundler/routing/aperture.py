"""
Planar polygon aperture checks shared by gate packing and route conditioning.
"""

from __future__ import annotations

import math
from functools import lru_cache

PlanarLoops = tuple[tuple[tuple[float, float], ...], ...]


@lru_cache(maxsize=64)
def _segments(loops: PlanarLoops) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """
    Return every closed boundary segment, including the boundaries of holes.
    """
    return tuple(
        (point, loop[(index + 1) % len(loop)]) for loop in loops for index, point in enumerate(loop)
    )


def _distance_sq_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """
    Return squared distance to one finite boundary segment.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-18:
        return (point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2
    fraction = max(
        0.0,
        min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq),
    )
    return (point[0] - start[0] - fraction * dx) ** 2 + (point[1] - start[1] - fraction * dy) ** 2


def _inside_loop(point: tuple[float, float], loop: tuple[tuple[float, float], ...]) -> bool:
    """
    Test one closed outline using an orientation-independent ray crossing.
    """
    inside = False
    x, y = point
    for index, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(index + 1) % len(loop)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def boundary_clearance_mm(point: tuple[float, float], loops: PlanarLoops) -> float:
    """
    Return signed distance from a point to the closest outline or hole edge.
    """
    if not loops:
        return -math.inf
    distance = math.sqrt(min(_distance_sq_to_segment(point, a, b) for a, b in _segments(loops)))
    inside = sum(_inside_loop(point, loop) for loop in loops) % 2 == 1
    return distance if inside else -distance


def contains_disk(point: tuple[float, float], radius_mm: float, loops: PlanarLoops) -> bool:
    """
    Require the full cable cross-section to remain in the filled profile.
    """
    return boundary_clearance_mm(point, loops) + 1e-9 >= radius_mm


def interior_center(loops: PlanarLoops) -> tuple[float, float]:
    """
    Find a deterministic interior point with broad boundary clearance.

    A bounded grid refinement handles concave profiles and holes whose area
    centroid may lie outside the usable aperture.
    """
    coordinates = [point for loop in loops for point in loop]
    if not coordinates:
        raise ValueError("A routing gate requires a closed planar profile.")
    min_u = min(point[0] for point in coordinates)
    max_u = max(point[0] for point in coordinates)
    min_v = min(point[1] for point in coordinates)
    max_v = max(point[1] for point in coordinates)
    step_u = (max_u - min_u) / 12.0
    step_v = (max_v - min_v) / 12.0
    if step_u <= 0.0 or step_v <= 0.0:
        raise ValueError("A routing gate requires a profile with positive area.")
    best = ((min_u + max_u) / 2.0, (min_v + max_v) / 2.0)
    best_clearance = -math.inf
    for level in range(4):
        if level == 0:
            candidates = (
                (min_u + column * step_u, min_v + row * step_v)
                for row in range(13)
                for column in range(13)
            )
        else:
            center_u, center_v = best
            candidates = (
                (center_u + column * step_u, center_v + row * step_v)
                for row in range(-2, 3)
                for column in range(-2, 3)
            )
        for candidate in candidates:
            clearance = boundary_clearance_mm(candidate, loops)
            if clearance > best_clearance:
                best, best_clearance = candidate, clearance
        step_u /= 2.0
        step_v /= 2.0
    if best_clearance <= 0.0:
        raise ValueError("A routing gate requires a closed planar region with positive area.")
    return best


def first_contained_fraction(
    points: tuple[tuple[float, float, float], ...],
    translation: tuple[float, float],
    loops: PlanarLoops,
) -> float:
    """
    Bound one rigid cluster's motion at its first profile-boundary crossing.
    """
    if not all(contains_disk((u, v), radius, loops) for u, v, radius in points):
        return 0.0
    previous = 0.0
    steps = min(1024, max(32, math.ceil(math.hypot(*translation) / 0.1)))
    for index in range(1, steps + 1):
        fraction = index / steps
        if all(
            contains_disk(
                (u + translation[0] * fraction, v + translation[1] * fraction), radius, loops
            )
            for u, v, radius in points
        ):
            previous = fraction
            continue
        lower, upper = previous, fraction
        for _ in range(24):
            midpoint = (lower + upper) / 2.0
            if all(
                contains_disk(
                    (u + translation[0] * midpoint, v + translation[1] * midpoint), radius, loops
                )
                for u, v, radius in points
            ):
                lower = midpoint
            else:
                upper = midpoint
        return lower
    return 1.0
