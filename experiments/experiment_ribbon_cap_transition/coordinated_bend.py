"""
Coordinate the interior bend plane using one procedurally derived midpoint pose.

Elevate the frozen arc-jet scaffold to degree12 and solve its three free controls
for midpoint position/velocity/acceleration. External poses and cap derivatives
remain fixed. This is one direct linear solve, not a shape search or feasibility
promise; certificates must still accept the resulting interior.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit

from .distributed_bend import distributed_controls
from .endpoint_first import EndpointCase, derivative, evaluate


def _elevate(points: tuple[Vector3, ...]) -> tuple[Vector3, ...]:
    """
    Raise a Bernstein polynomial's degree once without changing its curve.
    """
    degree = len(points)
    return (
        points[0],
        *(lerp(points[i], points[i - 1], i / degree) for i in range(1, degree)),
        points[-1],
    )


def coordinated_controls(case: EndpointCase) -> tuple[tuple[Vector3, ...], dict[str, object]]:
    """
    Derive one middle pose and enforce it through three free Bernstein controls.

    Middle position averages the two cap-circle half-turn extrapolations. Middle
    tangent follows the chord; width is the projected ordered width average. Reject
    an undefined middle width rather than invent a half-turn convention. Preserve
    derivatives through order4 at both caps and impose position/first/second
    derivatives at u=1/2. No parameter, target or tolerance is adjusted afterward.
    """
    previous, metadata = distributed_controls(case)
    if metadata["nominal_turn_radians"] == 0:
        return previous, dict(metadata)
    radius, speed = metadata["cap_radius_mm"], metadata["cap_speed_mm"]
    half_turn = metadata["nominal_turn_radians"] / 2
    start_prediction = case.start.translated(
        case.start_tangent, radius * math.sin(half_turn)
    ).translated(cross(case.start_width, case.start_tangent), radius * (1 - math.cos(half_turn)))
    end_prediction = case.end.translated(
        case.end_tangent, -radius * math.sin(half_turn)
    ).translated(cross(case.end_width, case.end_tangent), radius * (1 - math.cos(half_turn)))
    midpoint = lerp(start_prediction, end_prediction, 0.5)
    tangent = unit(difference(case.end, case.start))
    width_sum = case.start_width.translated(case.end_width, 1)
    projected_width = width_sum.translated(tangent, -dot(width_sum, tangent))
    if magnitude(projected_width) <= 1e-8:
        raise ValueError("Derived middle width is undefined; no roll fallback.")
    width = unit(projected_width)
    zero = Vector3(0, 0, 0)
    targets = (
        midpoint,
        zero.translated(tangent, speed),
        zero.translated(cross(width, tangent), speed**2 / radius),
    )
    points = previous
    while len(points) < 13:
        points = _elevate(points)
    known = tuple(zero if i in (5, 6, 7) else p for i, p in enumerate(points))
    known_first = derivative(known)
    known_second = derivative(known_first)
    rhs = tuple(
        difference(target, evaluate(coefficients, 0.5))
        for target, coefficients in zip(targets, (known, known_first, known_second))
    )
    # Symmetry reduces the fixed3x3 midpoint system to sum/difference plus a2x2.
    position_pair, position_middle = 792 / 4096, 924 / 4096
    velocity_difference = 1584 / 2048
    acceleration_pair, acceleration_middle = -6336 / 1024, -11088 / 1024
    determinant = position_pair * acceleration_middle - position_middle * acceleration_pair
    pair_sum = zero.translated(rhs[0], acceleration_middle / determinant).translated(
        rhs[2], -position_middle / determinant
    )
    pair_difference = zero.translated(rhs[1], 1 / velocity_difference)
    middle = zero.translated(rhs[2], position_pair / determinant).translated(
        rhs[0], -acceleration_pair / determinant
    )
    left = zero.translated(pair_sum, 0.5).translated(pair_difference, -0.5)
    right = zero.translated(pair_sum, 0.5).translated(pair_difference, 0.5)
    result = points[:5] + (left, middle, right) + points[8:]
    return result, {
        **metadata,
        "middle_position_mm": midpoint,
        "middle_tangent": tangent,
        "middle_width": width,
        "degree": 12,
    }
