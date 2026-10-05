"""
Bound continuous cubic curvature without trusting preview sample spacing.

Certification is conservative: uncertainty rejects the route rather than
changing its endpoints, material envelope, or conductor ordering. This is
an input certificate, not a certificate of an arbitrary Fusion loft surface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import (
    CubicBezier,
    cross,
    difference,
    dot,
    lerp,
    magnitude,
    unit,
)
from cable_bundler.routing.parallel import RoutePreview


class UnsafeRibbon(ValueError):
    """
    Reject invalid or uncertifiable input before constructing a ribbon.
    """


@dataclass(frozen=True)
class CurvatureCertificate:
    """
    Record the worst conservative macaroni ratio and subdivision work.
    """

    maximum_ratio: float
    certified_intervals: int


def split_curve(curve: CubicBezier) -> tuple[CubicBezier, CubicBezier]:
    """
    Bisect a cubic exactly using de Casteljau interpolation.
    """
    a = lerp(curve.start, curve.control_a, 0.5)
    b = lerp(curve.control_a, curve.control_b, 0.5)
    c = lerp(curve.control_b, curve.end, 0.5)
    d, e = lerp(a, b, 0.5), lerp(b, c, 0.5)
    middle = lerp(d, e, 0.5)
    return CubicBezier(curve.start, a, d, middle), CubicBezier(middle, e, c, curve.end)


def _curvature_bound(curve: CubicBezier) -> float:
    """
    Bound |v cross a|/|v| cubed over the complete cubic interval.

    Derivatives lie in their Bernstein control hulls. Projection supplies a
    positive speed lower bound; convexity bounds the cross product above.
    """
    points = (curve.start, curve.control_a, curve.control_b, curve.end)
    velocities = tuple(
        difference(b, a).translated(difference(b, a), 2.0) for a, b in zip(points, points[1:])
    )
    accelerations = tuple(
        difference(b, a).translated(difference(b, a), 1.0)
        for a, b in zip(velocities, velocities[1:])
    )
    middle_velocity = curve.derivative(0.5)
    if magnitude(middle_velocity) <= 1e-14:
        return math.inf
    axis = unit(middle_velocity)
    minimum_speed = min(dot(velocity, axis) for velocity in velocities)
    if minimum_speed <= 1e-14:
        return math.inf
    maximum_cross = max(magnitude(cross(v, a)) for v in velocities for a in accelerations)
    return maximum_cross / minimum_speed**3


def certify_curvature(
    route: RoutePreview,
    profile_reach_mm: float,
    *,
    ratio_limit: float = 0.8,
    maximum_depth: int = 16,
) -> CurvatureCertificate:
    """
    Certify every cubic, including cable-end segments, with positive margin.

    The supplied reach must enclose the entire occupied profile, not merely
    a conductor radius. Reject nonfinite input, singularities, discontinuous
    tangents, and exhausted bounds. No geometric repair or fallback is made.
    """
    if not math.isfinite(profile_reach_mm) or profile_reach_mm <= 0.0:
        raise UnsafeRibbon("Profile reach must be finite and positive.")
    if not 0.0 < ratio_limit < 1.0 or maximum_depth < 0:
        raise UnsafeRibbon("Certification requires a strict margin and bounded depth.")
    if not route.curves:
        raise UnsafeRibbon("A route must retain its exact cubic geometry.")
    for curve in route.curves:
        for point in (curve.start, curve.control_a, curve.control_b, curve.end):
            if not all(math.isfinite(value) for value in (point.x, point.y, point.z)):
                raise UnsafeRibbon("Nonfinite cubic geometry.")
    for left, right in zip(route.curves, route.curves[1:]):
        if magnitude(difference(left.end, right.start)) > 1e-7:
            raise UnsafeRibbon("Disconnected cubic route.")
        a, b = left.derivative(1.0), right.derivative(0.0)
        if min(magnitude(a), magnitude(b)) <= 1e-12 or dot(unit(a), unit(b)) < 1.0 - 1e-7:
            raise UnsafeRibbon("Unbounded curvature at a cubic join.")
    pending = [(curve, 0) for curve in route.curves]
    maximum_ratio, count = 0.0, 0
    while pending:
        curve, depth = pending.pop()
        ratio = profile_reach_mm * _curvature_bound(curve)
        if ratio <= ratio_limit:
            maximum_ratio = max(maximum_ratio, ratio)
            count += 1
        elif depth >= maximum_depth:
            raise UnsafeRibbon("Continuous macaroni bound cannot be certified.")
        else:
            left, right = split_curve(curve)
            pending.extend(((left, depth + 1), (right, depth + 1)))
    return CurvatureCertificate(maximum_ratio, count)


def discrete_profile_reach(line_count: int, diameter_mm: float) -> float:
    """
    Enclose all lobes and side caps independently of the selected bank.
    """
    if line_count < 1 or not math.isfinite(diameter_mm) or diameter_mm <= 0.0:
        raise UnsafeRibbon("Invalid discrete profile dimensions.")
    return math.hypot((line_count + 0.2) * diameter_mm / 2.0, diameter_mm / 2.0)
