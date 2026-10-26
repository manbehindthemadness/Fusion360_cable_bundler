"""
Separate transport accuracy from existing geometric policies for forward ribbons.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude

from .director_transport import DirectorPath


def measure(
    path: DirectorPath, reference: DirectorPath, checkpoint: Callable[[], None]
) -> dict[str, Any]:
    """
    Compare two fixed grids at off-node samples and retain policy findings separately.

    Position convergence<=.005mm,frame drift<=1e-6,metric error<=1e-5 are numerical
    benchmark tolerances,not fixed-target closure tolerances. The older.8macaroni,
    three-diameter radius and5xwidth sphere policies remain measured independently.
    No complete self-contact,elasticity,split caps or native compliance certificate.
    """
    field = path.field
    half = field.half_width_mm
    reach = math.hypot(half, field.diameter_mm / 2)
    midpoint = reference.lane(0, 0)[0].translated(
        difference(reference.lane(1, 0)[0], reference.lane(0, 0)[0]), 0.5
    )
    position_error = frame_error = metric_error = wide_bend = occupied = center_ratio = 0.0
    minimum_j = 1.0
    radius = math.inf
    zero_bends = 0
    parameters = (0.0, 1.0) + tuple((i + 0.5) / 257 for i in range(257))
    for i, u in enumerate(parameters):
        if i % 32 == 0:
            checkpoint()
        state, derivative = path.pose(u)
        tangent, width = Vector3(*state[3:6]), Vector3(*state[6:9])
        bend = Vector3(*derivative[3:6])
        frame_error = max(
            frame_error,
            abs(dot(tangent, tangent) - 1),
            abs(dot(width, width) - 1),
            abs(dot(tangent, width)),
        )
        wide_bend = max(wide_bend, abs(dot(bend, width)) / field.length_mm)
        k, eta, eta_s = field.sample(u)
        if abs(k) < 1e-12:
            zero_bends += 1
        material_width = width.translated(tangent, eta)
        for q in (-half, 0.0, half):
            point, velocity = path.lane(u, q)
            jac = 1 + q * eta_s
            minimum_j = min(minimum_j, jac)
            position_error = max(
                position_error, magnitude(difference(point, reference.lane(u, q)[0]))
            )
            per_length = Vector3(
                velocity.x / field.length_mm,
                velocity.y / field.length_mm,
                velocity.z / field.length_mm,
            )
            metric_error = max(
                metric_error,
                abs(dot(per_length, per_length) - jac * jac),
                abs(dot(per_length, material_width) - jac * eta),
                abs(dot(material_width, material_width) - (1 + eta * eta)),
            )
            occupied = max(occupied, magnitude(difference(point, midpoint)) + field.diameter_mm / 2)
            if q == 0:
                center_ratio = max(center_ratio, abs(k) * reach)
            if jac > 0 and abs(k) > 1e-15:
                radius = min(radius, jac / abs(k))
    numerical = []
    if position_error > 0.005 or frame_error > 1e-6 or metric_error > 1e-5 or wide_bend > 1e-6:
        numerical.append("transport accuracy tolerance exceeded")
    findings = []
    if minimum_j <= 0:
        findings.append("sampled material map folds")
    if center_ratio > 0.8 or radius < 3 * field.diameter_mm:
        findings.append("current curvature policy rejected")
    sphere = 2.5 * field.lines * field.diameter_mm
    if occupied > sphere:
        findings.append("current sphere policy rejected")
    return {
        "numerical_findings": numerical,
        "policy_findings": findings,
        "position_convergence_mm": position_error,
        "frame_squared_norm_or_dot_error": frame_error,
        "maximum_metric_error": metric_error,
        "maximum_wide_bend_per_mm": wide_bend,
        "minimum_material_jacobian": minimum_j,
        "minimum_lane_radius_mm": radius,
        "center_ratio": center_ratio,
        "occupied_sphere_reach_mm": occupied,
        "sphere_radius_mm": sphere,
        "sampled_zero_bending_points": zero_bends,
        "samples": len(parameters),
    }
