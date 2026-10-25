"""
Derive fixed circular-trace sweep paths from one shared endpoint-first scaffold.

This new diagnostic construction uses piecewise cubic Hermite interpolation with
exact prescribed endpoint headings. It is not the historical loft interpolant.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, lerp, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    _curvature_bound,
    split_curve,
)

from .endpoint_first import EndpointCase, construct


@dataclass(frozen=True)
class TracePath:
    """
    Retain one ordered trace's exact cubic chain and equivalent NURBS controls.
    """

    number: int
    curves: tuple[CubicBezier, ...]
    controls: tuple[Vector3, ...]
    knots: tuple[float, ...]


def interpolate_trace(
    number: int,
    points: tuple[Vector3, ...],
    start_tangent: Vector3,
    end_tangent: Vector3,
) -> TracePath:
    """
    Interpolate ordered nodes once, with shared interior jets and fixed cap headings.

    Endpoint jet lengths equal the adjacent chord; interior jets use centered
    differences in the uniform node parameter. There is no fitting search or repair.
    """
    if len(points) < 3 or any(
        magnitude(difference(b, a)) <= 1e-8 for a, b in zip(points, points[1:])
    ):
        raise ValueError("Trace interpolation needs three distinct ordered nodes.")
    zero = Vector3(0, 0, 0)
    jets = (
        zero.translated(unit(start_tangent), magnitude(difference(points[1], points[0]))),
        *(zero.translated(difference(b, a), 0.5) for a, b in zip(points, points[2:])),
        zero.translated(unit(end_tangent), magnitude(difference(points[-1], points[-2]))),
    )
    curves = tuple(
        CubicBezier(a, a.translated(ja, 1 / 3), b.translated(jb, -1 / 3), b)
        for a, b, ja, jb in zip(points, points[1:], jets, jets[1:])
    )
    controls = (curves[0].start, *(p for c in curves for p in (c.control_a, c.control_b, c.end)))
    knots = (
        (0.0,) * 4
        + tuple(i / len(curves) for i in range(1, len(curves)) for _ in range(3))
        + (1.0,) * 4
    )
    return TracePath(number, curves, controls, knots)


def plan_trace_sweeps(case: EndpointCase) -> tuple[tuple[TracePath, ...], dict[str, object]]:
    """
    Generate one shared scaffold, interpolate all traces and bound their curvature.

    At most4096 derivative-hull intervals are visited across the complete ribbon;
    max depth12. Exhaustion is uncertified, not infeasible or accepted. Every trace
    must retain at least a three-diameter radius before any sweep is attempted.
    Continuous spacing/interference of the interpolants remains unmeasured.
    """
    frames, numerical = construct(case)
    paths = tuple(
        interpolate_trace(
            i + 1,
            tuple(
                f.origin.translated(f.width, (i - (case.lines - 1) / 2) * case.diameter_mm)
                for f in frames
            ),
            case.start_tangent,
            case.end_tangent,
        )
        for i in range(case.lines)
    )
    visited, maximum_curvature = 0, 0.0
    sphere_center = lerp(case.start, case.end, 0.5)
    sphere_radius = 2.5 * case.lines * case.diameter_mm
    for path in paths:
        if (
            max(magnitude(difference(p, sphere_center)) for p in path.controls)
            + case.diameter_mm / 2
            > sphere_radius
        ):
            raise UnsafeRibbon(
                "Interpolated trace hull exceeds the fixed sphere; no native attempt."
            )
        pending = [(c, 0) for c in path.curves]
        while pending:
            visited += 1
            if visited > 4096:
                raise UnsafeRibbon(
                    "Trace interpolation certificate exhausted4096 intervals; no native attempt."
                )
            curve, depth = pending.pop()
            bound = _curvature_bound(curve)
            if bound * (3 * case.diameter_mm) <= 1:
                maximum_curvature = max(maximum_curvature, bound)
            elif depth >= 12:
                raise UnsafeRibbon(
                    f"Trace{path.number} interpolated radius cannot be certified at three diameters; no native attempt."
                )
            else:
                left, right = split_curve(curve)
                pending.extend(((left, depth + 1), (right, depth + 1)))
    numerical["trace_interpolation"] = {
        "method": "shared-node-cubic-hermite-v1",
        "visited_intervals": visited,
        "maximum_curvature_bound_per_mm": maximum_curvature,
        "minimum_radius_bound_mm": 1 / maximum_curvature if maximum_curvature else None,
        "cross_section": "circular per-trace diameter; not the historical bonded lobe outline",
        "unmeasured": [
            "continuous inter-trace spacing/interference",
            "material strain",
            "native interpolation error",
        ],
    }
    return paths, numerical
