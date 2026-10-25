"""
Construct endpoint-flat banking and analytic-jet cubic trace paths once.

A septic retains the previous endpoint speed and curvature while prescribing zero
jerk at both caps. Consequently the normalized binormal has zero first derivative
there, and every offset lane inherits the prescribed tangent. No search, endpoint
movement or continuous interpolation/spacing guarantee is implied.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, difference, lerp, magnitude

from .endpoint_first import SECTIONS, EndpointCase, certify, controls, derivative, evaluate
from .endpoint_trace_paths import TracePath
from .trace_diagnostic import shared_lane_jet


def clamped_controls(case: EndpointCase) -> tuple[Vector3, ...]:
    """
    Map validated poses to a septic with fixed first, second and zero third jets.

    Retain the exact straight branch. Zero jerk is a boundary construction rule,
    not a sampled correction to the interior or an elastic equilibrium condition.
    """
    previous = controls(case)
    chord = difference(case.end, case.start)
    if all(magnitude(cross(difference(p, case.start), chord)) < 1e-8 for p in previous):
        return tuple(lerp(case.start, case.end, i / 7) for i in range(8))
    distance = magnitude(chord)
    ends = []
    for position, tangent, width, sign in (
        (case.start, case.start_tangent, case.start_width, 1),
        (case.end, case.end_tangent, case.end_width, -1),
    ):
        acceleration = cross(width, tangent)
        ends.append(
            (
                position,
                position.translated(tangent, sign * distance / 7),
                position.translated(tangent, sign * 2 * distance / 7).translated(
                    acceleration, distance / 42
                ),
                position.translated(tangent, sign * 3 * distance / 7).translated(
                    acceleration, distance / 14
                ),
            )
        )
    return ends[0] + tuple(reversed(ends[1]))


def analytic_paths(case: EndpointCase) -> tuple[tuple[TracePath, ...], dict[str, float | int]]:
    """
    Certify the shared scaffold, then interpolate each lane with its analytic jets.

    Use33uniform nodes and32cubics, preserving C1 continuity and cap headings.
    The existing scaffold certificate bounds banking regularity, macaroni and the
    five-width sphere; it does not certify the offset cubics' curvature or spacing.
    """
    points = clamped_controls(case)
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    certificate = certify(
        points, reach, lerp(case.start, case.end, 0.5), 2.5 * case.lines * case.diameter_mm
    )
    straight = all(
        magnitude(cross(difference(p, case.start), difference(case.end, case.start))) < 1e-8
        for p in points
    )
    velocity = derivative(points)
    # Offset lanes depend linearly on offset; evaluate the shared jets once/node.
    shared = []
    for index in range(SECTIONS):
        u = index / (SECTIONS - 1)
        origin, tangent = evaluate(points, u), evaluate(velocity, u)
        if straight:
            width, width_derivative = case.start_width, Vector3(0, 0, 0)
        else:
            shifted, shifted_tangent, _acceleration = shared_lane_jet(points, u, 1)
            width = difference(shifted, origin)
            width_derivative = difference(shifted_tangent, tangent)
        shared.append((origin, tangent, width, width_derivative))
    paths = []
    for lane in range(case.lines):
        offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
        nodes, jets = [], []
        for origin, tangent, width, width_derivative in shared:
            nodes.append(origin.translated(width, offset))
            jets.append(tangent.translated(width_derivative, offset))
        step = 1 / (SECTIONS - 1)
        curves = tuple(
            CubicBezier(a, a.translated(ja, step / 3), b.translated(jb, -step / 3), b)
            for a, b, ja, jb in zip(nodes, nodes[1:], jets, jets[1:])
        )
        control_points = (
            curves[0].start,
            *(p for curve in curves for p in (curve.control_a, curve.control_b, curve.end)),
        )
        knots = (
            (0.0,) * 4
            + tuple(i / len(curves) for i in range(1, len(curves)) for _ in range(3))
            + (1.0,) * 4
        )
        paths.append(TracePath(lane + 1, curves, control_points, knots))
    return tuple(paths), certificate
