"""
Inspect one frozen trace without changing its shape or attempting native solids.

Fixed sampling can exhibit a violation but cannot prove a continuous minimum.
Compare the analytic shared field with the exact sweep-interpolation cubics.
"""

from __future__ import annotations

import math
from time import perf_counter, process_time
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit

from .endpoint_first import EndpointCase, construct, controls, derivative, evaluate
from .endpoint_trace_paths import TracePath, interpolate_trace

INTERVALS_PER_SEGMENT = 32


def curvature_radius(velocity: Vector3, acceleration: Vector3) -> float:
    """
    Measure a regular parametric curve's local radius; a straight point is infinite.
    """
    speed = magnitude(velocity)
    if speed <= 1e-12:
        raise ValueError("Diagnostic curve has zero speed.")
    area = magnitude(cross(velocity, acceleration))
    return speed**3 / area if area > 1e-14 else math.inf


def shared_lane_jet(
    points: tuple[Vector3, ...], fraction: float, offset_mm: float
) -> tuple[Vector3, Vector3, Vector3]:
    """
    Differentiate the binormal-offset lane analytically through second order.

    For C=v cross a, C'=v cross jerk and C''=a cross jerk+v cross snap.
    Reject a singular bend frame. This helper is for nonstraight diagnostic curves.
    """
    first = derivative(points)
    second = derivative(first)
    third = derivative(second)
    fourth = derivative(third)
    v, a, j, s = (evaluate(p, fraction) for p in (first, second, third, fourth))
    c, dc = cross(v, a), cross(v, j)
    ddc = cross(a, j).translated(cross(v, s), 1)
    q = magnitude(c)
    if q <= 1e-12:
        raise ValueError("Shared lane diagnostic has a singular binormal.")
    h = dot(c, dc)
    zero = Vector3(0, 0, 0)
    width = zero.translated(c, 1 / q)
    dwidth = zero.translated(dc, 1 / q).translated(c, -h / q**3)
    ddwidth = (
        zero.translated(ddc, 1 / q)
        .translated(dc, -2 * h / q**3)
        .translated(c, -(dot(dc, dc) + dot(c, ddc)) / q**3 + 3 * h**2 / q**5)
    )
    return (
        evaluate(points, fraction).translated(width, offset_mm),
        v.translated(dwidth, offset_mm),
        a.translated(ddwidth, offset_mm),
    )


def _angle(left: Vector3, right: Vector3) -> float:
    """
    Measure heading mismatch without discarding the ordered tangent direction.
    """
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(left), unit(right))))))


def diagnose_trace(case: EndpointCase, number: int = 1) -> tuple[TracePath, dict[str, Any]]:
    """
    Evaluate exactly one frozen case/trace on a fixed grid, with a ten-second cap.

    Measure33points on each of32 interpolation cubics and1025shared-field points.
    No sample-driven refinement, parameter search, shape repair or native build.
    """
    if not 1 <= number <= case.lines:
        raise ValueError("Diagnostic trace number is outside the ribbon.")
    wall_started, cpu_started = perf_counter(), process_time()
    frames, _numerical = construct(case)
    offset = (number - 1 - (case.lines - 1) / 2) * case.diameter_mm
    nodes = tuple(f.origin.translated(f.width, offset) for f in frames)
    path = interpolate_trace(number, nodes, case.start_tangent, case.end_tangent)
    points = controls(case)
    worst: dict[str, Any] = {"radius_mm": math.inf}
    segment_minima = []
    for index, curve in enumerate(path.curves):
        if perf_counter() - wall_started > 10:
            raise RuntimeError("Fixed diagnostic exceeded ten seconds; stop without refinement.")
        local_minimum = math.inf
        for sample in range(INTERVALS_PER_SEGMENT + 1):
            u = sample / INTERVALS_PER_SEGMENT
            velocity, acceleration = curve.derivative(u), curve.second_derivative(u)
            radius = curvature_radius(velocity, acceleration)
            local_minimum = min(local_minimum, radius)
            if radius < worst["radius_mm"]:
                position = curve.point(u)
                worst = {
                    "radius_mm": radius,
                    "segment": index + 1,
                    "segment_fraction": u,
                    "shared_parameter": (index + u) / len(path.curves),
                    "position_mm": [position.x, position.y, position.z],
                }
        segment_minima.append(local_minimum)
    shared_worst: dict[str, Any] = {"radius_mm": math.inf}
    for sample in range(len(path.curves) * INTERVALS_PER_SEGMENT + 1):
        if sample % 64 == 0 and perf_counter() - wall_started > 10:
            raise RuntimeError("Fixed diagnostic exceeded ten seconds; stop without refinement.")
        u = sample / (len(path.curves) * INTERVALS_PER_SEGMENT)
        position, velocity, acceleration = shared_lane_jet(points, u, offset)
        radius = curvature_radius(velocity, acceleration)
        if radius < shared_worst["radius_mm"]:
            shared_worst = {
                "radius_mm": radius,
                "parameter": u,
                "position_mm": [position.x, position.y, position.z],
            }
    endpoint_comparison = []
    for u, target in ((0.0, case.start_tangent), (1.0, case.end_tangent)):
        _position, velocity, acceleration = shared_lane_jet(points, u, offset)
        curve = path.curves[0] if u == 0 else path.curves[-1]
        endpoint_comparison.append(
            {
                "endpoint": "start" if u == 0 else "end",
                "shared_heading_error_degrees": _angle(velocity, target),
                "shared_radius_mm": curvature_radius(velocity, acceleration),
                "interpolated_heading_error_degrees": _angle(curve.derivative(u), target),
                "interpolated_radius_mm": curvature_radius(
                    curve.derivative(u), curve.second_derivative(u)
                ),
            }
        )
    report = {
        "case_id": case.name,
        "trace_number": number,
        "required_radius_mm": 3 * case.diameter_mm,
        "interpolated_smallest_observed": worst,
        "shared_smallest_observed": shared_worst,
        "segment_minimum_radii_mm": segment_minima,
        "endpoint_comparison": endpoint_comparison,
        "interpolated_evaluations": len(path.curves) * (INTERVALS_PER_SEGMENT + 1),
        "shared_evaluations": len(path.curves) * INTERVALS_PER_SEGMENT + 1,
        "wall_seconds": perf_counter() - wall_started,
        "cpu_seconds": process_time() - cpu_started,
        "scope": "Finite observations, not continuous minima, native outcomes or complete-ribbon compliance.",
    }
    return path, report
