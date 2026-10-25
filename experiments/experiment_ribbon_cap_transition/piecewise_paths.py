"""
Generate and compare cubic sweep paths against the complete piecewise analytic field.

Keep33shared nodes/32cubics and9observations per cubic, matching prior diagnostic
sampling. Observations are not continuous trace/spacing/physical certificates.
"""

from __future__ import annotations

import math
from typing import Any

from cable_bundler.routing.geometry import (
    CubicBezier,
    difference,
    dot,
    lerp,
    magnitude,
    unit,
)

from .endpoint_first import EndpointCase
from .endpoint_trace_paths import TracePath
from .native_budget import NativeBudget
from .piecewise_bend import PiecewiseBend
from .trace_diagnostic import curvature_radius


def trace_paths(case: EndpointCase, scaffold: PiecewiseBend) -> tuple[TracePath, ...]:
    """
    Interpolate the same uniform global nodes using shared analytic position/velocity.
    """
    shared = []
    for index in range(33):
        u = index / 32
        base, shifted = scaffold.jet(u, 0), scaffold.jet(u, 1)
        shared.append((base, tuple(difference(a, b) for a, b in zip(shifted, base))))
    paths = []
    for lane in range(case.lines):
        offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
        nodes = tuple(base[0].translated(delta[0], offset) for base, delta in shared)
        jets = tuple(base[1].translated(delta[1], offset) for base, delta in shared)
        curves = tuple(
            CubicBezier(a, a.translated(ja, 1 / 96), b.translated(jb, -1 / 96), b)
            for a, b, ja, jb in zip(nodes, nodes[1:], jets, jets[1:])
        )
        controls = (
            curves[0].start,
            *(p for c in curves for p in (c.control_a, c.control_b, c.end)),
        )
        knots = (0.0,) * 4 + tuple(i / 32 for i in range(1, 32) for _ in range(3)) + (1.0,) * 4
        paths.append(TracePath(lane + 1, curves, controls, knots))
    return tuple(paths)


def compare_paths(
    case: EndpointCase, scaffold: PiecewiseBend, paths: tuple[TracePath, ...], budget: NativeBudget
) -> dict[str, Any]:
    """
    Compare all ordered lanes at paired analytic/cubic observations and fixed caps.
    """
    shared = []
    for index in range(257):
        if index % 32 == 0:
            budget.check(f"sample_shared_{index}")
        base, shifted = scaffold.jet(index / 256, 0), scaffold.jet(index / 256, 1)
        shared.append((base, tuple(difference(a, b) for a, b in zip(shifted, base))))
    worst = {"analytic": {"radius_mm": math.inf}, "cubic": {"radius_mm": math.inf}}
    position_error, heading_error, cap_error = 0.0, 0.0, 0.0
    lengths = []
    for lane, path in enumerate(paths):
        budget.check(f"sample_lane_{lane + 1}")
        offset, length = (lane - (case.lines - 1) / 2) * case.diameter_mm, 0.0
        for segment, curve in enumerate(path.curves):
            previous = curve.start
            for sample in range(9):
                u = sample / 8
                base, delta = shared[segment * 8 + sample]
                position, velocity, acceleration = (
                    a.translated(b, offset) for a, b in zip(base, delta)
                )
                for field, v, a in (
                    ("analytic", velocity, acceleration),
                    ("cubic", curve.derivative(u), curve.second_derivative(u)),
                ):
                    radius = curvature_radius(v, a)
                    if radius < worst[field]["radius_mm"]:
                        worst[field] = {
                            "radius_mm": radius,
                            "trace": path.number,
                            "global_parameter": (segment + u) / 32,
                        }
                position_error = max(
                    position_error, magnitude(difference(curve.point(u), position))
                )
                heading_error = max(
                    heading_error,
                    math.degrees(
                        math.acos(
                            max(-1.0, min(1.0, dot(unit(curve.derivative(u)), unit(velocity))))
                        )
                    ),
                )
                current = curve.point(u)
                length += magnitude(difference(current, previous))
                previous = current
        lengths.append(length)
        for actual, endpoint, width in (
            (path.controls[0], case.start, case.start_width),
            (path.controls[-1], case.end, case.end_width),
        ):
            cap_error = max(
                cap_error, magnitude(difference(actual, endpoint.translated(width, offset)))
            )
    center = lerp(case.start, case.end, 0.5)
    return {
        "analytic_smallest_observed": worst["analytic"],
        "cubic_smallest_observed": worst["cubic"],
        "max_position_error_mm": position_error,
        "max_heading_error_degrees": heading_error,
        "cap_position_error_mm": cap_error,
        "sampled_length_spread": (max(lengths) - min(lengths)) / max(lengths),
        "hulls_inside_sphere": all(
            magnitude(difference(p, center)) + case.diameter_mm / 2
            <= 2.5 * case.lines * case.diameter_mm
            for path in paths
            for p in path.controls
        ),
        "observations_per_field": case.lines * 32 * 9,
    }
