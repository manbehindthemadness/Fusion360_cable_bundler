"""
Measure authored native boundary curves independently of their analytical reference.
"""

from __future__ import annotations

import math
from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

from cable_bundler.routing.geometry import difference

from .endpoint_first import EndpointCase


def curve_findings(rows: list[dict[str, Any]]) -> list[str]:
    """
    Classify measured native paths against the unchanged experimental limits.

    Callers separately require all three expected curves. These sampled checks
    cannot establish continuous or thick-ribbon compliance.
    """
    findings: list[str] = []
    if any(
        row["minimum_radius_mm"] < 4.5
        or row["occupied_sphere_reach_mm"] > 71.25
        or row["endpoint_error_mm"] > 1e-8
        for row in rows
    ):
        findings.append("native cubic rule failure")
    if any(row["center_ratio"] is not None and row["center_ratio"] > 0.8 for row in rows):
        findings.append("native center curvature failure")
    return findings


def audit_curves(
    component: Any,
    case: EndpointCase,
    intervals: int,
    checkpoint: Callable[[], None],
    rows: list[dict[str, Any]],
) -> None:
    """
    Append native endpoint/radius/extent checks,retaining completed rows on failure.

    Evaluate513uniform parameters plus both sides of all internal Hermite knots.
    Assumes our normalized[0,1]clamped cubic curves,validated before sampling.
    Geometry is in centimeters;results convert to millimeters. No scene writes,
    mathematical curve reconstruction,solid audit or continuous certificate.
    """
    if not isinstance(intervals, int) or not 16 <= intervals <= 1024:
        raise ValueError("Unsupported native interpolation interval count.")
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half_width, case.diameter_mm / 2)
    center = case.start.translated(difference(case.end, case.start), 0.5)
    native_center = adsk.core.Point3D.create(center.x / 10, center.y / 10, center.z / 10)
    parameters = sorted(
        {i / 512 for i in range(513)}
        | {i / intervals + sign * 1e-7 for i in range(1, intervals) for sign in (-1, 1)}
    )
    offsets = {"A boundary": half_width, "Derived center": 0.0, "Derived B": -half_width}
    for index in range(component.sketches.count):
        sketch = component.sketches.item(index)
        selected = [offset for name, offset in offsets.items() if sketch.name.startswith(name)]
        if not selected:
            continue
        checkpoint()
        evaluator = sketch.sketchCurves.sketchFixedSplines.item(0).geometry.evaluator
        ok, low, high = evaluator.getParameterExtents()
        if not ok or abs(low) > 1e-10 or abs(high - 1) > 1e-10:
            raise RuntimeError("Expected normalized native cubic parameter range.")
        minimum_radius, occupied = math.inf, 0.0
        for station, u in enumerate(parameters):
            if station % 128 == 0:
                checkpoint()
            ok_v, velocity = evaluator.getFirstDerivative(u)
            ok_a, acceleration = evaluator.getSecondDerivative(u)
            ok_p, position = evaluator.getPointAtParameter(u)
            if not (ok_v and ok_a and ok_p) or velocity.length <= 1e-12:
                raise RuntimeError("Native curve evaluator failed or speed vanished.")
            product = velocity.crossProduct(acceleration).length
            if product > 1e-16:
                minimum_radius = min(minimum_radius, 10 * velocity.length**3 / product)
            point = sketch.sketchToModelSpace(position)
            occupied = max(occupied, 10 * point.distanceTo(native_center) + case.diameter_mm / 2)
        offset = selected[0]
        endpoint_error = 0.0
        for fraction, point, width in (
            (0, case.start, case.start_width),
            (1, case.end, case.end_width),
        ):
            ok, position = evaluator.getPointAtParameter(fraction)
            if not ok:
                raise RuntimeError("Native endpoint evaluation failed.")
            actual = sketch.sketchToModelSpace(position)
            target = point.translated(width, offset)
            expected = adsk.core.Point3D.create(target.x / 10, target.y / 10, target.z / 10)
            endpoint_error = max(endpoint_error, 10 * actual.distanceTo(expected))
        rows.append(
            {
                "name": sketch.name,
                "parameters": len(parameters),
                "minimum_radius_mm": minimum_radius,
                "occupied_sphere_reach_mm": occupied,
                "endpoint_error_mm": endpoint_error,
                "center_ratio": reach / minimum_radius if offset == 0 else None,
            }
        )
