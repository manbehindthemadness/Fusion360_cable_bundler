"""
Author fixed oblique, twisted, and spatial fixtures without outcome-dependent repair.
"""

from __future__ import annotations

import math
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import (
    CubicBezier,
    Vector3,
    cross,
    difference,
    dot,
    magnitude,
    unit,
)
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.cases import Expectation, RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import discrete_profile_reach
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary

from .compact import compact_cases, length_bounds


def rotate(vector: Vector3, axis: Vector3, degrees: float) -> Vector3:
    """
    Apply a rigid right-handed rotation, preserving all metric constraints.
    """
    normal = unit(axis)
    angle = math.radians(degrees)
    perpendicular = cross(normal, vector)
    parallel = dot(normal, vector) * (1 - math.cos(angle))
    return Vector3(
        *(
            a * math.cos(angle) + b * math.sin(angle) + c * parallel
            for a, b, c in zip(
                (vector.x, vector.y, vector.z),
                (perpendicular.x, perpendicular.y, perpendicular.z),
                (normal.x, normal.y, normal.z),
            )
        )
    )


def spatial_cases(diameter_widths: float = 4.0) -> tuple[RibbonStressCase, ...]:
    """
    Place six production-width inputs at varied orientations in a fixed sphere.

    The first four retain compact bend geometry before a declared end-width
    rotation. The last two are nonplanar S curves. Twist is prescribed through
    end-guide orientation, not asserted to equal the solver's accumulated roll.
    Four-width fixtures uniformly compress five-width route coordinates to 80%
    without shrinking the material profile. Their tight bends are known input
    curvature controls, still attempted in diagnostic observation mode.
    """
    quarter, half = compact_cases()[-2:]
    specifications = (
        ("oblique_quarter", quarter, 0.0, 25.0),
        ("oblique_quarter_twist45", quarter, 45.0, 70.0),
        ("oblique_half_twist_minus90", half, -90.0, 130.0),
        ("oblique_half_twist180", half, 180.0, 205.0),
    )
    cases = []
    axis = Vector3(1, 2, 3)
    for label, base, twist, position in specifications:
        center = base.end_boundary.center

        def point(value: Vector3, origin: Vector3 = center, angle: float = position) -> Vector3:
            """
            Scale the fixture to 1.5 mm conductors and rotate around the sphere center.
            """
            delta = difference(value, origin)
            return rotate(Vector3(delta.x * 3, delta.y * 3, delta.z * 3), axis, angle)

        curves = tuple(
            CubicBezier(*(point(p) for p in (c.start, c.control_a, c.control_b, c.end)))
            for c in base.route.curves
        )
        width = rotate(base.start_width, axis, position)
        end_width = rotate(width, curves[-1].derivative(1), twist)
        name = f"spatial_{label}_19x1.5"
        route = RoutePreview(
            uuid5(NAMESPACE_URL, name), name, (curves[0].start, *(c.end for c in curves)), curves
        )
        cases.append(
            replace(
                base,
                name=name,
                family=f"spatial_{label}",
                diameter_mm=1.5,
                route=route,
                start_width=width,
                end_width=end_width,
                end_boundary=EndBoundary(Vector3(0, 0, 0), 142.5),
            )
        )
    width_mm = 28.5
    for twist, position in ((45, 45), (-90, 160)):
        controls = tuple(
            rotate(Vector3(x * width_mm, y * width_mm, z * width_mm), axis, position)
            for x, y, z in ((-2, 0, 0), (-1, 0, 1), (1, -1, 0), (2, 0, 0))
        )
        curve = CubicBezier(*controls)
        start_width = rotate(Vector3(0, 1, 0), axis, position)
        end_width = rotate(rotate(Vector3(0, 0, 1), axis, position), curve.derivative(1), twist)
        name = f"spatial_s_twist{twist}_19x1.5"
        route = RoutePreview(uuid5(NAMESPACE_URL, name), name, (curve.start, curve.end), (curve,))
        cases.append(
            RibbonStressCase(
                name,
                f"spatial_s_twist{twist}",
                19,
                1.5,
                route,
                start_width,
                end_width,
                Expectation.BUILD,
                EndBoundary(Vector3(0, 0, 0), 5 * width_mm),
            )
        )
    if diameter_widths == 5.0:
        return tuple(cases)
    if diameter_widths != 4.0:
        raise ValueError("Spatial matrix supports four- or five-width spheres.")
    compressed = []
    for case in cases:
        curves = tuple(
            CubicBezier(
                *(
                    Vector3(p.x * 0.8, p.y * 0.8, p.z * 0.8)
                    for p in (c.start, c.control_a, c.control_b, c.end)
                )
            )
            for c in case.route.curves
        )
        route = replace(
            case.route, curves=curves, points=(curves[0].start, *(c.end for c in curves))
        )
        compressed.append(
            replace(
                case,
                route=route,
                expectation=Expectation.CURVATURE_REJECTION
                if case.family.startswith("spatial_oblique")
                else case.expectation,
                end_boundary=EndBoundary(Vector3(0, 0, 0), 4 * width_mm),
            )
        )
    return tuple(compressed)


def spatial_evidence(case: RibbonStressCase) -> dict[str, object]:
    """
    Record input length versus necessary distance and tangent-rotation lower bounds.
    """
    curves = case.route.curves
    angle = math.acos(
        max(-1.0, min(1.0, dot(unit(curves[0].derivative(0)), unit(curves[-1].derivative(1)))))
    )
    bound = max(
        magnitude(difference(curves[-1].end, curves[0].start)),
        angle * discrete_profile_reach(case.lines, case.diameter_mm) / 0.8,
    )
    lower, upper = length_bounds(curves)
    return {
        "route_length_lower_mm": lower,
        "route_length_upper_mm": upper,
        "feasible_length_lower_bound_mm": bound,
        "relative_optimality_gap_upper": (upper - bound) / bound,
        "exact_shortest_proven": False,
        "scope": "Necessary trunk-only bound; no global clearance, twist feasibility, or skin-strain certificate.",
    }
