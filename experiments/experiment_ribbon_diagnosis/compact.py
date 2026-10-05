"""
Author compact planar bends with independent length bounds and equal-width rails.
"""

from __future__ import annotations

import math
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, lerp, magnitude
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_secure_discrete_ribbon.cases import Expectation, RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    discrete_profile_reach,
    split_curve,
)
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary


def length_bounds(curves: tuple[CubicBezier, ...], depth: int = 6) -> tuple[float, float]:
    """
    Bound arc length between subdivided chord and control-polygon sums.
    """
    lower = upper = 0.0
    pending = [(curve, depth) for curve in curves]
    while pending:
        curve, remaining = pending.pop()
        if remaining:
            pending.extend((part, remaining - 1) for part in split_curve(curve))
        else:
            points = (curve.start, curve.control_a, curve.control_b, curve.end)
            lower += magnitude(difference(points[-1], points[0]))
            upper += sum(magnitude(difference(b, a)) for a, b in zip(points, points[1:]))
    return lower, upper


def compact_cases() -> tuple[RibbonStressCase, ...]:
    """
    Fix six independently authored bends before solving, without return detours.

    Constant Y width gives equal translated input rails. Radius is 0.1% above
    the curvature-policy minimum; cubic approximation and bounds are reported,
    not claimed to be an exact global optimum. Both caps terminate in a turn.
    """
    cases = []
    width_axis = Vector3(0, 1, 0)
    for lines, diameter in ((3, 1.0), (5, 1.0), (19, 0.5)):
        radius = discrete_profile_reach(lines, diameter) / 0.8 * 1.001
        for degrees in (90, 180):
            angle = math.radians(degrees)
            count = degrees // 90 * 8
            step = angle / count
            handle = 4 / 3 * math.tan(step / 4) * radius
            points = tuple(
                Vector3(radius * math.sin(i * step), 0, radius * (1 - math.cos(i * step)))
                for i in range(count + 1)
            )
            tangents = tuple(
                Vector3(math.cos(i * step), 0, math.sin(i * step)) for i in range(count + 1)
            )
            curves = tuple(
                CubicBezier(
                    a, a.translated(tangents[i], handle), b.translated(tangents[i + 1], -handle), b
                )
                for i, (a, b) in enumerate(zip(points, points[1:]))
            )
            name = f"compact_{degrees}_{lines}x{diameter:g}"
            route = RoutePreview(uuid5(NAMESPACE_URL, name), name, points, curves)
            cases.append(
                RibbonStressCase(
                    name,
                    f"compact_{degrees}",
                    lines,
                    diameter,
                    route,
                    width_axis,
                    width_axis,
                    Expectation.BUILD,
                    EndBoundary(lerp(points[0], points[-1], 0.5), 5 * lines * diameter),
                )
            )
    return tuple(cases)


def route_evidence(case: RibbonStressCase) -> dict[str, object]:
    """
    Report a necessary curvature-based global lower bound, not an optimum claim.
    """
    angle = math.radians(int(case.family.rsplit("_", 1)[1]))
    lower, upper = length_bounds(case.route.curves)
    minimum = angle * discrete_profile_reach(case.lines, case.diameter_mm) / 0.8
    return {
        "route_length_lower_mm": lower,
        "route_length_upper_mm": upper,
        "feasible_length_lower_bound_mm": minimum,
        "relative_optimality_gap_upper": (upper - minimum) / minimum,
        "exact_shortest_proven": False,
        "scope": "Trunk only; tangent rotation / maximum curvature lower bound. Other rules still require audits.",
        "input_side_length_difference_mm": 0.0,
        "input_side_equality_basis": "Constant-width translations of the same planar cubic route.",
    }
