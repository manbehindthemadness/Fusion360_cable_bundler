"""
Prescribe stationary width direction and width acceleration at both ordered caps.

A degree-nine scaffold retains the previous endpoint speed/curvature and sets
third/fourth centerline derivatives to zero. Its binormal first/second derivatives
therefore vanish at the caps. Interior lane curvature is still a separate check.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, difference, lerp, magnitude

from .endpoint_first import SECTIONS, EndpointCase, certify, controls, derivative, evaluate
from .endpoint_trace_paths import TracePath
from .trace_diagnostic import shared_lane_jet


def cap_acceleration_controls(case: EndpointCase) -> tuple[Vector3, ...]:
    """
    Generate ten controls once with unchanged endpoints and zero third/fourth jets.

    The straight control remains exact. No parameters are fitted to measurements,
    no targets move, and no local repair or extra centerline segments are introduced.
    """
    previous = controls(case)
    chord = difference(case.end, case.start)
    if all(magnitude(cross(difference(p, case.start), chord)) < 1e-8 for p in previous):
        return tuple(lerp(case.start, case.end, i / 9) for i in range(10))
    distance = magnitude(chord)
    ends = []
    for position, tangent, width, sign in (
        (case.start, case.start_tangent, case.start_width, 1),
        (case.end, case.end_tangent, case.end_width, -1),
    ):
        normal = cross(width, tangent)
        ends.append(
            tuple(
                position.translated(tangent, sign * i * distance / 9).translated(
                    normal, i * (i - 1) * distance / 144
                )
                for i in range(5)
            )
        )
    return ends[0] + tuple(reversed(ends[1]))


def cap_acceleration_paths(
    case: EndpointCase,
) -> tuple[tuple[TracePath, ...], tuple[Vector3, ...], dict[str, float | int]]:
    """
    Certify the new scaffold, then author the unchanged33node analytic Hermite policy.

    Preserve the same32cubics, circular trace dimensions and five-width sphere.
    Scaffold certification is not an offset-lane or native compliance certificate.
    The previous experimental policy remains untouched for provenance/replay.
    """
    points = cap_acceleration_controls(case)
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
    shared = []
    for index in range(SECTIONS):
        u = index / (SECTIONS - 1)
        origin, tangent = evaluate(points, u), evaluate(velocity, u)
        if straight:
            width, width_derivative = case.start_width, Vector3(0, 0, 0)
        else:
            shifted, shifted_tangent, _acceleration = shared_lane_jet(points, u, 1)
            width, width_derivative = (
                difference(shifted, origin),
                difference(shifted_tangent, tangent),
            )
        shared.append((origin, tangent, width, width_derivative))
    paths = []
    step = 1 / (SECTIONS - 1)
    for lane in range(case.lines):
        offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
        nodes = tuple(origin.translated(width, offset) for origin, _v, width, _dw in shared)
        jets = tuple(v.translated(dw, offset) for _origin, v, _width, dw in shared)
        curves = tuple(
            CubicBezier(a, a.translated(ja, step / 3), b.translated(jb, -step / 3), b)
            for a, b, ja, jb in zip(nodes, nodes[1:], jets, jets[1:])
        )
        path_controls = (
            curves[0].start,
            *(p for c in curves for p in (c.control_a, c.control_b, c.end)),
        )
        knots = (
            (0.0,) * 4
            + tuple(i * step for i in range(1, SECTIONS - 1) for _ in range(3))
            + (1.0,) * 4
        )
        paths.append(TracePath(lane + 1, curves, path_controls, knots))
    return tuple(paths), points, certificate
