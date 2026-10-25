"""
Translate a certified analytic scaffold into ordered circular-trace cubic paths.

Use one shared33node field and analytic derivatives, without searching or changing
geometry. Historical experiment adapters remain untouched for exact provenance.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import CubicBezier, Vector3, cross, difference, lerp, magnitude

from .endpoint_first import SECTIONS, EndpointCase, certify, derivative, evaluate
from .endpoint_trace_paths import TracePath
from .trace_diagnostic import shared_lane_jet


def scaffold_paths(
    case: EndpointCase, points: tuple[Vector3, ...]
) -> tuple[tuple[TracePath, ...], dict[str, float | int]]:
    """
    Certify the shared curve and generate the fixed32cubic interpolation per lane.

    The shared certificate covers envelope curvature/containment and bend-frame
    regularity; lane interpolation curvature, spacing and native geometry require
    separate evidence. Straight paths use the prescribed constant width direction.
    """
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
        controls = (
            curves[0].start,
            *(p for c in curves for p in (c.control_a, c.control_b, c.end)),
        )
        knots = (
            (0.0,) * 4
            + tuple(i * step for i in range(1, SECTIONS - 1) for _ in range(3))
            + (1.0,) * 4
        )
        paths.append(TracePath(lane + 1, curves, controls, knots))
    return tuple(paths), certificate
