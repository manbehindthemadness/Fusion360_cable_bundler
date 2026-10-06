"""
Author five-width developmental fixtures before observing any solver result.

The centerlines and fifteen-degree, four-conductor-radius connection turns are
fixed inputs, not optimized routes. Mixed directions are reflection-related.
"""

from __future__ import annotations

import math
from dataclasses import replace
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import CubicBezier, Vector3, lerp
from cable_bundler.routing.parallel import RoutePreview
from experiments.experiment_ribbon_diagnosis.compact import compact_cases
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases
from experiments.experiment_secure_discrete_ribbon.cases import Expectation, RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary


def _line(start: Vector3, end: Vector3) -> CubicBezier:
    """
    Represent a straight span with nonzero endpoint derivatives.
    """
    return CubicBezier(start, lerp(start, end, 1 / 3), lerp(start, end, 2 / 3), end)


def _arc(x: float, z: float, radius: float, start: float, sweep: float) -> tuple[CubicBezier, ...]:
    """
    Author tangent-continuous circular cubic approximants in the XZ plane.
    """
    count = math.ceil(abs(sweep) / (math.pi / 2))
    step = sweep / count
    result = []
    for index in range(count):
        a, b = start + index * step, start + (index + 1) * step
        handle = 4 / 3 * math.tan(step / 4) * radius
        left = Vector3(x + radius * math.cos(a), 0, z + radius * math.sin(a))
        right = Vector3(x + radius * math.cos(b), 0, z + radius * math.sin(b))
        result.append(
            CubicBezier(
                left,
                left.translated(Vector3(-math.sin(a), 0, math.cos(a)), handle),
                right.translated(Vector3(-math.sin(b), 0, math.cos(b)), -handle),
                right,
            )
        )
    return tuple(result)


def _case(name: str, curves: tuple[CubicBezier, ...], center: Vector3) -> RibbonStressCase:
    """
    Give every configuration a stable identity and the same material and sphere.
    """
    route = RoutePreview(
        uuid5(NAMESPACE_URL, name),
        name,
        (curves[0].start, *(curve.end for curve in curves)),
        curves,
    )
    return replace(
        compact_cases()[0],
        name=name,
        family=name,
        lines=19,
        diameter_mm=1.5,
        route=route,
        start_width=Vector3(0, 1, 0),
        end_width=Vector3(0, 1, 0),
        expectation=Expectation.BUILD,
        end_boundary=EndBoundary(center, 142.5),
    )


def direction_cases() -> tuple[RibbonStressCase, ...]:
    """
    Fix four cap-to-connection directions with a shared pair of cap positions.

    Outward/inward refers to connection-facing cap normals relative to the
    sphere center. These translated-lane controls do not cover width-axis bends
    or arbitrary twisting, and the reflected mixed pair is an invariance check.
    """
    radius = 0.75 * 28.5
    left, right = Vector3(-radius, 0, 0), Vector3(radius, 0, 0)
    center = Vector3(0, 0, radius)
    inward = (
        *_arc(-radius, radius, radius, -math.pi / 2, -math.pi),
        _line(Vector3(-radius, 0, 2 * radius), Vector3(radius, 0, 2 * radius)),
        *_arc(radius, radius, radius, math.pi / 2, -math.pi),
    )
    mixed = (
        *_arc(-radius, radius, radius, -math.pi / 2, math.pi / 2),
        *_arc(radius, radius, radius, math.pi, -math.pi / 2),
        *_arc(radius, radius, radius, math.pi / 2, -math.pi),
    )

    def reflect(point: Vector3) -> Vector3:
        """
        Reflect across the center plane without changing distances.
        """
        return Vector3(-point.x, point.y, point.z)

    reflected = tuple(
        CubicBezier(
            *(
                reflect(point)
                for point in (curve.end, curve.control_b, curve.control_a, curve.start)
            )
        )
        for curve in reversed(mixed)
    )
    return (
        _case("sphere5_both_outward", (_line(left, right),), center),
        _case("sphere5_both_inward", inward, center),
        _case("sphere5_A_out_B_in", mixed, center),
        _case("sphere5_A_in_B_out", reflected, center),
    )


def development_cases() -> tuple[RibbonStressCase, ...]:
    """
    Retain broader spatial challenges and an explicitly invalid tight control.
    """
    gentle = _case("sphere5_gentle", _arc(0, 30, 30, -math.pi / 2, math.pi / 2), Vector3(15, 0, 15))
    invalid = replace(
        _case("sphere5_invalid_tight", _arc(0, 8, 8, -math.pi / 2, math.pi / 2), Vector3(4, 0, 4)),
        expectation=Expectation.CURVATURE_REJECTION,
    )
    return (*direction_cases(), gentle, *spatial_cases(5.0)[-2:], invalid)


def reversal_case() -> RibbonStressCase:
    """
    Freeze a 180-degree U-turn and signed half-twist inside a four-width sphere.

    Two tangent-continuous quarter-cubic approximants have radius 30 mm. Opposite
    Y guide widths impose a 180-degree roll relative to parallel transport in the
    XZ bend plane. Material, conductor order and short split fixtures are unchanged.
    This is one new developmental configuration, not an optimized route/holdout.
    """
    return replace(
        _case(
            "sphere4_reversal180_twist180",
            _arc(0, 0, 30, -math.pi / 2, math.pi),
            Vector3(0, 0, 0),
        ),
        end_width=Vector3(0, -1, 0),
        end_boundary=EndBoundary(Vector3(0, 0, 0), 114.0),
    )


def full_turn_case() -> RibbonStressCase:
    """
    Freeze the same four-width U-turn with endpoint roll for one explicit full turn.

    Parent: sphere4_reversal180_twist180. The fixed centerline, material and sphere
    are unchanged. End width returns to +Y; ordered B cap/connection inputs are
    authored for this roll before results. Winding is a separate prescription,
    because equal endpoint widths alone do not distinguish zero from 360 degrees.
    """
    parent = reversal_case()
    return replace(
        _case("sphere4_reversal180_twist360", parent.route.curves, parent.end_boundary.center),
        end_boundary=parent.end_boundary,
    )


def close_full_turn_case() -> RibbonStressCase:
    """
    Freeze 40 mm cap separation by tightening the full-turn semicircle to R20.

    Parent: sphere4_reversal180_twist360. Sphere, material and endpoint directions
    remain unchanged; new cap/connection positions are authored before the solve.
    This is a fixed-centerline development variant, not a routing optimization.
    """
    parent = full_turn_case()
    return replace(
        _case(
            "sphere4_reversal180_twist360_gap40",
            _arc(0, 0, 20, -math.pi / 2, math.pi),
            parent.end_boundary.center,
        ),
        end_boundary=parent.end_boundary,
    )


def certificate_limit_case(radius_mm: float) -> RibbonStressCase:
    """
    Author the selected full-turn semicircle before freezing all native targets.

    Only positive radii at or below the parent R20 are permitted. Search probes
    share this development identity; they are not complete-ribbon configurations.
    Sphere, material, endpoint directions and conductor order remain unchanged.
    """
    if not math.isfinite(radius_mm) or not 0 < radius_mm <= 20:
        raise ValueError("Certificate-limit radius must be finite and in (0, 20].")
    parent = close_full_turn_case()
    return replace(
        _case(
            "sphere4_reversal180_twist360_curve_limit",
            _arc(0, 0, radius_mm, -math.pi / 2, math.pi),
            parent.end_boundary.center,
        ),
        end_boundary=parent.end_boundary,
    )
