"""
Sample and approximate material paths without introducing a native compliance claim.
"""

from __future__ import annotations

import math
from typing import Any

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .endpoint_first import EndpointCase
from .material_allocation import MaterialPlan
from .material_strip import MaterialStrip


def spline_controls(
    strip: MaterialStrip, offset: float
) -> tuple[tuple[Vector3, ...], tuple[float, ...]]:
    """
    Approximate each lane-specific interval by32 cubic Hermite spans.

    Repeated knots use equal span intervals, independently of physical material
    distance. Each endpoint derivative is scaled by that span's material length.
    The cubic display is an approximation and does not inherit exact isometry.
    """
    points = [strip.jet(0, offset)[0]]
    count = 0
    boundaries = strip.boundaries(offset)
    for left, right in zip(boundaries, boundaries[1:]):
        step = (right - left) / 32
        for index in range(32):
            start = left if index == 0 else left + index * step
            end = right if index == 31 else left + (index + 1) * step
            p, v, _ = strip.jet(start, offset)
            q, w, _ = strip.jet(end, offset)
            points.extend((p.translated(v, step / 3), q.translated(w, -step / 3), q))
            count += 1
    knots = (0.0,) * 4 + tuple(i / count for i in range(1, count) for _ in range(3)) + (1.0,) * 4
    return tuple(points), knots


def audit(case: EndpointCase, plan: MaterialPlan) -> dict[str, Any]:
    """
    Audit reference bounds and65samples per span on center and two material edges.

    Analytical isometry gives every material lane unit speed and common length;
    sampled speed and curvature provide independent numerical checks on the three
    displayed references. Sphere coverage is those paths plus conductor thickness,
    not a continuous full-width certificate or a native solid audit. Old normal-
    section lane/spread diagnostics are not replayed against different geometry.
    """
    strip = plan.strip
    center = case.start.translated(difference(case.end, case.start), 0.5)
    reach = math.hypot(strip.half_width_mm, case.diameter_mm / 2)
    maximum_principal = max(s.maximum_principal_curvature() for s in strip.spans)
    maximum_center = max(m.maximum_curvature() for m in plan.motions)
    maximum_distance, maximum_speed_error, minimum_radius = 0.0, 0.0, math.inf
    for offset in (-strip.half_width_mm, 0.0, strip.half_width_mm):
        boundaries = strip.boundaries(offset)
        for left, right in zip(boundaries, boundaries[1:]):
            for index in range(65):
                distance = right if index == 64 else left + (right - left) * index / 64
                point, velocity, acceleration = strip.jet(distance, offset)
                maximum_distance = max(maximum_distance, magnitude(difference(point, center)))
                maximum_speed_error = max(maximum_speed_error, abs(magnitude(velocity) - 1))
                curvature = magnitude(acceleration)
                if curvature > 1e-12:
                    minimum_radius = min(minimum_radius, 1 / curvature)
    findings = []
    if maximum_principal * reach > 0.8:
        findings.append("analytic principal surface curvature limit")
    if maximum_center > 1 / (3 * case.diameter_mm):
        findings.append("analytic material-lane radius")
    occupied = maximum_distance + case.diameter_mm / 2
    if occupied > 2.5 * case.lines * case.diameter_mm:
        findings.append("sampled three-guide sphere limit")
    if not plan.connected:
        findings.append("fixed endpoint not reached; unclosed diagnostic only")
    if maximum_speed_error > 1e-8:
        findings.append("sampled material isometry contradiction")
    end_tangent, end_width = plan.motions[-1].frame(1)
    return {
        "findings": findings,
        "overall": "failed" if findings else "unresolved",
        "analytic_principal_curvature_ratio": maximum_principal * reach,
        "analytic_maximum_curvature_ratio": maximum_center * reach,
        "sampled_minimum_lane_radius_mm": minimum_radius,
        "minimum_material_jacobian": min(
            s.minimum_jacobian(strip.half_width_mm) for s in strip.spans
        ),
        "sampled_occupied_sphere_reach_mm": occupied,
        "sphere_radius_mm": 2.5 * case.lines * case.diameter_mm,
        "sampled_material_speed_error": maximum_speed_error,
        "analytic_common_material_lane_length_mm": strip.length_mm,
        "analytic_material_lane_length_spread": 0.0,
        "endpoint_tangent_error": magnitude(difference(end_tangent, case.end_tangent)),
        "endpoint_width_error": magnitude(difference(end_width, case.end_width)),
        "ruling_slopes": [(s.start_slope, s.end_slope) for s in strip.spans],
        "lengths_mm": [m.length for m in plan.motions],
        "unmeasured": [
            "native cubic interpolation and strain",
            "thick conductor clearance and finite pitch",
            "global full-width containment/self-intersection",
            "elastic equilibrium and complete cable compliance",
        ],
    }
