"""
Define deterministic bend/roll/return fixtures with explicit expected outcomes.

All coordinates are millimeters. These are exact cubic stress geometries,
not approximations silently substituted for the earlier PH quintic sweeps.
The families reuse their stress dimensions and independent negative controls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, lerp, unit
from cable_bundler.routing.parallel import RoutePreview

from .end_boundary import EndBoundary, bounded_terminal_turns


class Expectation(str, Enum):
    """
    Separate useful builds from deliberately rejected and unsafe controls.
    """

    BUILD = "build_and_audit"
    CURVATURE_REJECTION = "reject_curvature_policy"
    NONLOCAL_REJECTION = "reject_nonlocal_crossing"
    GUIDE_REJECTION = "reject_short_guide"


@dataclass(frozen=True)
class RibbonStressCase:
    """
    Retain fixed geometry and policy expectations before invoking the solver.
    """

    name: str
    family: str
    lines: int
    diameter_mm: float
    route: RoutePreview
    start_width: Vector3
    end_width: Vector3
    expectation: Expectation
    end_boundary: EndBoundary
    guide_width_factor: float = 1.0


def audit_end_boundary(
    case: RibbonStressCase, *, diameter_widths: float = 5.0
) -> dict[str, object]:
    """
    Require both entire authored cable-end guides inside the specified width-scaled sphere.

    Interior sweep and connection-profile locations are deliberately unconfined.
    This fixture requirement does not certify a generated body's geometry.
    """
    width = case.lines * case.diameter_mm
    if not math.isfinite(diameter_widths) or diameter_widths <= 0:
        raise ValueError("Sphere width multiplier must be finite and positive.")
    if case.end_boundary.diameter_mm != diameter_widths * width:
        label = "five" if diameter_widths == 5 else f"{diameter_widths:g}"
        raise ValueError(f"Cable-end sphere diameter must equal {label} cable widths.")
    endpoints = (case.route.curves[0].start, case.route.curves[-1].end)
    points = tuple(
        point.translated(unit(direction), sign * width * case.guide_width_factor / 2)
        for point, direction in zip(endpoints, (case.start_width, case.end_width))
        for sign in (-1, 0, 1)
    )
    maximum = case.end_boundary.require_contains(points)
    center = case.end_boundary.center
    return {
        "center_mm": {"x": center.x, "y": center.y, "z": center.z},
        "diameter_mm": case.end_boundary.diameter_mm,
        "diameter_widths": diameter_widths,
        "maximum_guide_radius_mm": maximum,
        "status": "contained",
        "scope": "Both full cable-end guides; sweep and split connections unconfined.",
    }


def _line(start: Vector3, end: Vector3) -> CubicBezier:
    """
    Represent a straight span with regular, nonzero cubic derivatives.
    """
    return CubicBezier(start, lerp(start, end, 1 / 3), lerp(start, end, 2 / 3), end)


def _hairpin(radius: float, leg: float) -> tuple[CubicBezier, ...]:
    """
    Join two quarter-circle cubic approximants to tangent-continuous legs.
    """
    k = 4 * (math.sqrt(2) - 1) / 3
    a, b, c = Vector3(0, 0, 0), Vector3(radius, radius, 0), Vector3(0, 2 * radius, 0)
    return (
        _line(Vector3(-leg, 0, 0), a),
        CubicBezier(a, Vector3(k * radius, 0, 0), Vector3(radius, (1 - k) * radius, 0), b),
        CubicBezier(b, Vector3(radius, (1 + k) * radius, 0), Vector3(k * radius, 2 * radius, 0), c),
        _line(c, Vector3(-leg, 2 * radius, 0)),
    )


def _helix(radius: float, rise: float) -> tuple[CubicBezier, ...]:
    """
    Make four C1 Hermite spans with a full revolution and a rising centerline.
    """
    step = math.pi / 2
    points = tuple(
        Vector3(radius * math.cos(i * step), radius * math.sin(i * step), rise * i / 4)
        for i in range(5)
    )
    tangents = tuple(
        Vector3(-radius * math.sin(i * step) * step, radius * math.cos(i * step) * step, rise / 4)
        for i in range(5)
    )
    return tuple(
        CubicBezier(a, a.translated(tangents[i], 1 / 3), b.translated(tangents[i + 1], -1 / 3), b)
        for i, (a, b) in enumerate(zip(points, points[1:]))
    )


def _crossing(width: float) -> tuple[CubicBezier, ...]:
    """
    Visit the same interior point twice with distinct tangents and broad bends.
    """
    points = tuple(
        Vector3(x * width, y * width, 0)
        for x, y in ((-80, -20), (0, 0), (40, 40), (80, 0), (40, -40), (0, 0), (-80, 20))
    )
    tangents = tuple(
        difference(points[min(i + 1, len(points) - 1)], points[max(0, i - 1)]).translated(
            difference(points[min(i + 1, len(points) - 1)], points[max(0, i - 1)]), -0.5
        )
        for i in range(len(points))
    )
    return tuple(
        CubicBezier(a, a.translated(tangents[i], 1 / 3), b.translated(tangents[i + 1], -1 / 3), b)
        for i, (a, b) in enumerate(zip(points, points[1:]))
    )


def stress_cases() -> tuple[RibbonStressCase, ...]:
    """
    Cross nine stress families with 3/5/19 lanes and two conductor diameters.

    No expected result is learned from the current solver's output. The
    crossing controls must not be constructed if the guard admits them.
    """
    cases: list[RibbonStressCase] = []
    for lines, diameter in ((3, 1.0), (5, 1.0), (19, 0.5)):
        width = lines * diameter
        y, z = Vector3(0, 1, 0), Vector3(0, 0, 1)
        straight = (_line(Vector3(0, 0, 0), Vector3(10 * width, 0, 0)),)
        spatial = (
            CubicBezier(
                Vector3(0, 0, 0),
                Vector3(4 * width, 0, 2 * width),
                Vector3(8 * width, 3 * width, -2 * width),
                Vector3(12 * width, 3 * width, 0),
            ),
        )
        specifications = (
            ("straight", straight, y, y, Expectation.BUILD, 1.0),
            ("spatial_s", spatial, y, z, Expectation.BUILD, 1.0),
            ("broad_hairpin", _hairpin(3 * width, 6 * width), z, z, Expectation.BUILD, 1.0),
            ("roll_180", straight, y, Vector3(0, -1, 0), Expectation.BUILD, 1.0),
            (
                "helix_360",
                _helix(4 * width, 8 * width),
                Vector3(-1, 0, 0),
                Vector3(-1, 0, 0),
                Expectation.BUILD,
                1.0,
            ),
            (
                "near_return",
                _hairpin(0.75 * width, 6 * width),
                y,
                Vector3(0, -1, 0),
                Expectation.BUILD,
                1.0,
            ),
            (
                "tight_radius",
                _hairpin(0.25 * width, 6 * width),
                y,
                Vector3(0, -1, 0),
                Expectation.CURVATURE_REJECTION,
                1.0,
            ),
            ("nonlocal_crossing", _crossing(width), z, z, Expectation.NONLOCAL_REJECTION, 1.0),
            ("short_end_guide", straight, y, y, Expectation.GUIDE_REJECTION, 0.5),
        )
        for family, curves, start_width, end_width, expectation, guide_factor in specifications:
            name = f"{family}_{lines}x{diameter:g}"
            index = len(cases)
            offset = Vector3((index % 5) * 1100, (index // 5) * 1100, 0)
            turned, boundary = bounded_terminal_turns(curves, start_width, end_width, width)
            translated = tuple(
                CubicBezier(
                    *(
                        point.translated(offset, 1)
                        for point in (curve.start, curve.control_a, curve.control_b, curve.end)
                    )
                )
                for curve in turned
            )
            route = RoutePreview(
                uuid5(NAMESPACE_URL, name),
                name,
                (translated[0].start, *(curve.end for curve in translated)),
                translated,
            )
            cases.append(
                RibbonStressCase(
                    name,
                    family,
                    lines,
                    diameter,
                    route,
                    start_width,
                    end_width,
                    expectation,
                    EndBoundary(boundary.center.translated(offset, 1), boundary.diameter_mm),
                    guide_factor,
                )
            )
    return tuple(cases)
