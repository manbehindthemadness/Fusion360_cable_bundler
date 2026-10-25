"""
Construct one closed-form two-arc centerline from fixed endpoint poses.

Explicit circular radii replace polynomial curvature guesses. The equal-distance
biarc does not enforce prescribed ribbon widths or smooth curvature at its join;
those remain hard audit findings, never silently accepted. No searches or repairs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit

from .endpoint_first import EndpointCase, controls


@dataclass(frozen=True)
class RouteArc:
    """
    Retain an exact directed circular arc, or a straight segment with no center.
    """

    start: Vector3
    end: Vector3
    center: Vector3 | None
    normal: Vector3 | None
    radius: float
    sweep: float

    def point(self, fraction: float) -> Vector3:
        """
        Evaluate a bounded arc fraction without fitting or changing its radius.
        """
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Arc fraction outside [0,1].")
        if self.center is None or self.normal is None:
            return lerp(self.start, self.end, fraction)
        radial = difference(self.start, self.center)
        return self.center.translated(radial, math.cos(self.sweep * fraction)).translated(
            cross(self.normal, radial), math.sin(self.sweep * fraction)
        )

    def tangent(self, fraction: float) -> Vector3:
        """
        Evaluate the ordered unit tangent.
        """
        if self.center is None or self.normal is None:
            return unit(difference(self.end, self.start))
        return unit(cross(self.normal, difference(self.point(fraction), self.center)))

    def curvature(self, fraction: float) -> Vector3:
        """
        Return the arclength curvature vector, zero for a straight segment.
        """
        if self.center is None:
            return Vector3(0, 0, 0)
        return Vector3(0, 0, 0).translated(
            difference(self.center, self.point(fraction)), 1 / self.radius**2
        )


def _arc(start: Vector3, end: Vector3, tangent: Vector3) -> RouteArc:
    """
    Discover the unique circle through two points with the given starting tangent.
    """
    chord = difference(end, start)
    transverse = chord.translated(tangent, -dot(chord, tangent))
    length = magnitude(transverse)
    if length <= 1e-10:
        if dot(chord, tangent) <= 0:
            raise ValueError("Collinear backward arc is undefined; no fallback.")
        return RouteArc(start, end, None, None, math.inf, 0)
    radius = dot(chord, chord) / (2 * length)
    center = start.translated(unit(transverse), radius)
    radial = unit(difference(start, center))
    normal = unit(cross(radial, tangent))
    end_radial = unit(difference(end, center))
    sweep = math.atan2(dot(normal, cross(radial, end_radial)), dot(radial, end_radial))
    if sweep <= 0:
        sweep += 2 * math.pi
    return RouteArc(start, end, center, normal, radius, sweep)


def biarc(case: EndpointCase) -> tuple[RouteArc, RouteArc]:
    """
    Solve one equal-distance biarc without moving any external targets.
    """
    controls(case)
    chord = difference(case.end, case.start)
    a = 2 * (1 - dot(case.start_tangent, case.end_tangent))
    b = 2 * dot(chord, case.start_tangent.translated(case.end_tangent, 1))
    squared = dot(chord, chord)
    if a <= 1e-12:
        if b <= 1e-12:
            raise ValueError("Parallel biarc has no positive equal-distance solution.")
        distance = squared / b
    else:
        root = math.sqrt(b * b + 4 * a * squared)
        distance = 2 * squared / (b + root) if b >= 0 else (-b + root) / (2 * a)
    join = lerp(case.start, case.end, 0.5).translated(
        difference(case.start_tangent, case.end_tangent), distance / 2
    )
    first = _arc(case.start, join, case.start_tangent)
    reverse = _arc(case.end, join, Vector3(0, 0, 0).translated(case.end_tangent, -1))
    second = RouteArc(
        join,
        case.end,
        reverse.center,
        Vector3(0, 0, 0).translated(reverse.normal, -1) if reverse.normal is not None else None,
        reverse.radius,
        reverse.sweep,
    )
    if magnitude(difference(first.tangent(1), second.tangent(0))) > 1e-7:
        raise ValueError("Closed-form biarc failed tangent continuity; no repair.")
    return first, second


def rational_spline(
    arcs: tuple[RouteArc, ...],
) -> tuple[tuple[Vector3, ...], tuple[float, ...], tuple[float, ...]]:
    """
    Represent the same circles exactly as one positive-weight degree2NURBS.

    Split arcs into at most90degree rational spans. Positive weights preserve the
    control-hull containment bound. This conversion adds no geometric interpolation.
    """
    points, weights = [arcs[0].start], [1.0]
    spans = 0
    for arc in arcs:
        count = max(1, math.ceil(arc.sweep / (math.pi / 2)))
        for index in range(count):
            a, b = index / count, (index + 1) / count
            weight = math.cos(arc.sweep / count / 2) if arc.center is not None else 1.0
            middle = arc.point((a + b) / 2)
            control = (
                arc.center.translated(difference(middle, arc.center), 1 / weight)
                if arc.center is not None
                else middle
            )
            points.extend((control, arc.end if index + 1 == count else arc.point(b)))
            weights.extend((weight, 1.0))
            spans += 1
    knots = (0.0,) * 3 + tuple(i / spans for i in range(1, spans) for _ in range(2)) + (1.0,) * 3
    return tuple(points), tuple(weights), knots


def audit(case: EndpointCase, arcs: tuple[RouteArc, ...]) -> dict[str, Any]:
    """
    Separate exact centerline radius/hull checks from known ribbon frame failures.
    """
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    points, _weights, _knots = rational_spline(arcs)
    sphere_center = lerp(case.start, case.end, 0.5)
    cap_bending = [
        abs(dot(unit(arc.curvature(u)), width)) if magnitude(arc.curvature(u)) > 1e-12 else 0.0
        for arc, u, width in ((arcs[0], 0, case.start_width), (arcs[-1], 1, case.end_width))
    ]
    jump = magnitude(difference(arcs[0].curvature(1), arcs[-1].curvature(0)))
    return {
        "radii_mm": [arc.radius for arc in arcs],
        "minimum_radius_mm": min(arc.radius for arc in arcs),
        "required_envelope_radius_mm": reach / 0.8,
        "radius_ok": all(arc.radius >= reach / 0.8 for arc in arcs),
        "hull_inside_sphere": max(magnitude(difference(p, sphere_center)) for p in points) + reach
        <= 2.5 * case.lines * case.diameter_mm,
        "cap_wide_axis_bending": cap_bending,
        "cap_width_rule_ok": max(cap_bending) <= 1e-8,
        "join_curvature_vector_jump_per_mm": jump,
        "join_curvature_continuous": jump <= 1e-8,
        "centerline_length_mm": sum(
            arc.radius * arc.sweep
            if math.isfinite(arc.radius)
            else magnitude(difference(arc.end, arc.start))
            for arc in arcs
        ),
        "scope": "Centerline diagnostic; frame failures reject ribbon compliance. No conductor sweeps, clearance or strain audit.",
    }
