"""
Distribute bending with circular cap jets and a ribbon-width-aware nominal radius.

The rule is a deterministic pose interpolant, not elastic equilibrium or a promise
of feasibility. Degree-nine Hermite controls are authored once; no tuning/search.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit

from .endpoint_first import EndpointCase, controls


def _angle(left: Vector3, right: Vector3) -> float:
    """
    Return the principal angle between validated unit directions in radians.
    """
    return math.acos(max(-1.0, min(1.0, dot(left, right))))


def distributed_controls(case: EndpointCase) -> tuple[tuple[Vector3, ...], dict[str, float]]:
    """
    Derive one shared speed/radius and circular endpoint derivatives through order4.

    Nominal turn is the larger of ordered frame rotation and the summed chord
    approach angles. Radius is the larger of the corresponding circular chord radius
    and the unchanged macaroni envelope requirement. Speed=radius*turn. End jets
    follow local circular motion, allowing curvature at caps while keeping both
    binormal derivatives zero. Interior invariants must still be checked.
    """
    previous = controls(case)
    chord = difference(case.end, case.start)
    distance = magnitude(chord)
    if all(magnitude(cross(difference(p, case.start), chord)) < 1e-8 for p in previous):
        return tuple(lerp(case.start, case.end, i / 9) for i in range(10)), {
            "nominal_turn_radians": 0.0,
            "cap_speed_mm": distance,
            "cap_radius_mm": math.inf,
            "minimum_envelope_radius_mm": math.hypot(
                case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
            )
            / 0.8,
        }
    frame_trace = (
        dot(case.start_tangent, case.end_tangent)
        + dot(case.start_width, case.end_width)
        + dot(cross(case.start_tangent, case.start_width), cross(case.end_tangent, case.end_width))
    )
    frame_turn = math.acos(max(-1.0, min(1.0, (frame_trace - 1) / 2)))
    chord_heading = unit(chord)
    turn = max(
        frame_turn,
        _angle(case.start_tangent, chord_heading) + _angle(chord_heading, case.end_tangent),
    )
    if turn <= 1e-8 or turn >= 2 * math.pi - 1e-8:
        raise ValueError("Distributed circular chord rule has a singular nominal turn.")
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    minimum_radius = reach / 0.8
    radius = max(distance / (2 * math.sin(turn / 2)), minimum_radius)
    speed = radius * turn
    zero = Vector3(0, 0, 0)
    ends = []
    for position, tangent, width, sign in (
        (case.start, case.start_tangent, case.start_width, 1),
        (case.end, case.end_tangent, case.end_width, -1),
    ):
        normal = cross(width, tangent)
        jets = (
            zero.translated(tangent, speed),
            zero.translated(normal, speed**2 / radius),
            zero.translated(tangent, -(speed**3) / radius**2),
            zero.translated(normal, -(speed**4) / radius**3),
        )
        endpoint_controls = []
        for index in range(5):
            point = position
            falling = 1
            for order in range(1, index + 1):
                falling *= 10 - order
                point = point.translated(
                    jets[order - 1], math.comb(index, order) * sign**order / falling
                )
            endpoint_controls.append(point)
        ends.append(tuple(endpoint_controls))
    return ends[0] + tuple(reversed(ends[1])), {
        "nominal_turn_radians": turn,
        "cap_speed_mm": speed,
        "cap_radius_mm": radius,
        "minimum_envelope_radius_mm": minimum_radius,
    }
