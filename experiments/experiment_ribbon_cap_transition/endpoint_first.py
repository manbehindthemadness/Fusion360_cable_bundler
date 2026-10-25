"""
Construct one quintic from endpoint poses, deriving banking from its bend plane.

This experimental rule is not an elastic equilibrium solver. It makes no length
repairs or shape searches. Singular bend frames reject rather than invent a roll.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.domain import CableGroupDefinition, CableGroupType
from cable_bundler.routing.geometry import Vector3, cross, difference, dot, lerp, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame

SECTIONS = 33


@dataclass(frozen=True)
class EndpointCase:
    """
    Freeze complete ordered endpoint poses independently of an interior curve.
    """

    name: str
    start: Vector3
    end: Vector3
    start_tangent: Vector3
    end_tangent: Vector3
    start_width: Vector3
    end_width: Vector3
    lines: int = 19
    diameter_mm: float = 1.5


def ribbon_group(case: EndpointCase) -> CableGroupDefinition:
    """
    Create native profile metadata with explicit ribbon construction semantics.
    """
    return CableGroupDefinition(
        uuid5(NAMESPACE_URL, "endpoint-first:" + case.name),
        (),
        diameter_mm=case.diameter_mm,
        ribbon_lines=case.lines,
        group_type=CableGroupType.RIBBON,
    )


def endpoint_cases() -> tuple[EndpointCase, ...]:
    """
    Register a straight control and three spatial pose challenges before solving.

    Roll labels identify endpoint width orientations, not guaranteed accumulated
    winding. No interior path is stored or used to author these endpoints.
    """
    x, y, z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)
    return (
        EndpointCase("control", Vector3(-40, 0, 0), Vector3(40, 0, 0), x, x, y, y),
        EndpointCase("quarter_plus", Vector3(-40, 0, 0), Vector3(40, 12, 8), x, x, y, z),
        EndpointCase(
            "quarter_minus", Vector3(-40, 0, 0), Vector3(35, -16, 12), x, x, y, Vector3(0, 0, -1)
        ),
        EndpointCase(
            "half_oblique",
            Vector3(-40, 0, 0),
            Vector3(35, 15, -15),
            x,
            unit(Vector3(1, 0, 0.3)),
            y,
            Vector3(0, -1, 0),
        ),
    )


def evaluate(points: tuple[Vector3, ...], fraction: float) -> Vector3:
    """
    Evaluate a Bernstein polynomial with de Casteljau interpolation.
    """
    if not points or not math.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError("A polynomial needs controls and a fraction in [0, 1].")
    work = points
    while len(work) > 1:
        work = tuple(lerp(a, b, fraction) for a, b in zip(work, work[1:]))
    return work[0]


def derivative(points: tuple[Vector3, ...]) -> tuple[Vector3, ...]:
    """
    Return exact derivative controls for a nonconstant Bernstein polynomial.
    """
    degree = len(points) - 1
    if degree < 1:
        raise ValueError("A derivative requires at least two controls.")
    return tuple(
        Vector3(0, 0, 0).translated(difference(b, a), degree) for a, b in zip(points, points[1:])
    )


def controls(case: EndpointCase) -> tuple[Vector3, ...]:
    """
    Map fixed poses to a quintic using chord-scaled speed and endpoint curvature.

    Both speeds equal endpoint distance. Endpoint curvature magnitude is 1/D;
    its direction is width cross tangent. This fixed policy has no tuning knobs.
    A collinear, equally oriented input uses the exact straight solution.
    """
    vectors = (
        case.start,
        case.end,
        case.start_tangent,
        case.end_tangent,
        case.start_width,
        case.end_width,
    )
    if any(not all(math.isfinite(v) for v in (p.x, p.y, p.z)) for p in vectors):
        raise ValueError("Endpoint vectors must be finite.")
    if case.lines < 1 or not math.isfinite(case.diameter_mm) or case.diameter_mm <= 0:
        raise ValueError("Ribbon dimensions must be positive.")
    distance = magnitude(difference(case.end, case.start))
    if distance <= 1e-8:
        raise UnsafeRibbon("Coincident endpoints are unsupported; no fallback.")
    for tangent, width in (
        (case.start_tangent, case.start_width),
        (case.end_tangent, case.end_width),
    ):
        if (
            abs(magnitude(tangent) - 1) > 1e-8
            or abs(magnitude(width) - 1) > 1e-8
            or abs(dot(tangent, width)) > 1e-8
        ):
            raise ValueError("Endpoint axes must be perpendicular unit vectors.")
    chord = unit(difference(case.end, case.start))
    if (
        all(
            magnitude(difference(axis, chord)) < 1e-10
            for axis in (case.start_tangent, case.end_tangent)
        )
        and magnitude(difference(case.start_width, case.end_width)) < 1e-10
    ):
        return tuple(lerp(case.start, case.end, i / 5) for i in range(6))
    p1 = case.start.translated(case.start_tangent, distance / 5)
    p4 = case.end.translated(case.end_tangent, -distance / 5)
    p2 = p1.translated(case.start_tangent, distance / 5).translated(
        cross(case.start_width, case.start_tangent), distance / 20
    )
    p3 = p4.translated(case.end_tangent, -distance / 5).translated(
        cross(case.end_width, case.end_tangent), distance / 20
    )
    return case.start, p1, p2, p3, p4, case.end


def certify(
    points: tuple[Vector3, ...], reach: float, center: Vector3, radius: float
) -> dict[str, float | int]:
    """
    Bound continuous curvature and occupied containment with fixed-depth hulls.

    Generalizes the existing Bernstein derivative-hull macaroni bound to quintics.
    Subdivision is verification, never a shape revision. Depth exhaustion rejects.
    """
    if not all(math.isfinite(v) and v > 0 for v in (reach, radius)):
        raise ValueError("Certificate dimensions must be positive and finite.")
    pending = [(points, 0)]
    worst, count = 0.0, 0
    while pending:
        piece, depth = pending.pop()
        velocity = derivative(piece)
        acceleration = derivative(velocity)
        middle = evaluate(velocity, 0.5)
        speed = min(dot(v, unit(middle)) for v in velocity) if magnitude(middle) > 1e-12 else 0
        ratio = (
            reach * max(magnitude(cross(v, a)) for v in velocity for a in acceleration) / speed**3
            if speed > 1e-12
            else math.inf
        )
        inside = max(magnitude(difference(p, center)) for p in piece) + reach <= radius
        products = tuple(cross(v, a) for v in velocity for a in acceleration)
        global_velocity = derivative(points)
        global_acceleration = derivative(global_velocity)
        straight = (
            max(magnitude(cross(v, a)) for v in global_velocity for a in global_acceleration)
            < 1e-10
        )
        axis = cross(evaluate(velocity, 0.5), evaluate(acceleration, 0.5))
        regular = straight or (
            magnitude(axis) > 1e-18 and min(dot(p, unit(axis)) for p in products) > 0
        )
        if ratio <= 0.8 and inside and regular:
            worst = max(worst, ratio)
            count += 1
            continue
        if depth == 16:
            raise UnsafeRibbon("Endpoint construction is uncertified at fixed depth; no repair.")
        rows = [piece]
        while len(rows[-1]) > 1:
            rows.append(tuple(lerp(a, b, 0.5) for a, b in zip(rows[-1], rows[-1][1:])))
        pending.extend(
            (
                (tuple(row[0] for row in rows), depth + 1),
                (tuple(row[-1] for row in reversed(rows)), depth + 1),
            )
        )
    return {"maximum_ratio": worst, "certified_intervals": count}


def construct(case: EndpointCase) -> tuple[tuple[RibbonFrame, ...], dict[str, object]]:
    """
    Generate one path and analytic binormal frames, then reject hard findings.

    At nonzero curvature, width=tangent cross curvature guarantees zero modeled
    wide-axis bending continuously wherever that frame is defined. The
    derivative-hull certificate excludes interior bend-frame singularities for
    nonstraight curves. Native interpolation, continuous spacing and physical
    strain remain unverified.
    """
    points = controls(case)
    velocity, acceleration = derivative(points), derivative(derivative(points))
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    certificate = certify(
        points, reach, lerp(case.start, case.end, 0.5), 2.5 * case.lines * case.diameter_mm
    )
    straight = all(
        magnitude(cross(difference(p, case.start), difference(case.end, case.start))) < 1e-8
        for p in points
    )
    frames = []
    for index in range(SECTIONS):
        u = index / (SECTIONS - 1)
        tangent = unit(evaluate(velocity, u))
        normal = cross(tangent, evaluate(acceleration, u))
        if not straight and magnitude(normal) <= 1e-8:
            raise UnsafeRibbon("Sampled bend frame is singular; no roll fallback.")
        width = case.start_width if straight else unit(normal)
        frames.append(RibbonFrame(evaluate(points, u), tangent, width, unit(cross(tangent, width))))
    for frame, target in ((frames[0], case.start_width), (frames[-1], case.end_width)):
        if magnitude(difference(frame.width, target)) > 1e-8:
            raise UnsafeRibbon("Generated endpoint ordering differs from frozen pose.")
    lanes = [
        tuple(
            f.origin.translated(f.width, (lane - (case.lines - 1) / 2) * case.diameter_mm)
            for f in frames
        )
        for lane in range(case.lines)
    ]
    lengths = [sum(magnitude(difference(b, a)) for a, b in zip(lane, lane[1:])) for lane in lanes]
    minimum_radius = math.inf
    for lane in lanes:
        for a, b, c in zip(lane, lane[1:], lane[2:]):
            ab, bc, ac = difference(b, a), difference(c, b), difference(c, a)
            area = magnitude(cross(ab, bc))
            if area > 1e-12:
                minimum_radius = min(
                    minimum_radius, magnitude(ab) * magnitude(bc) * magnitude(ac) / (2 * area)
                )
    if minimum_radius < 3 * case.diameter_mm:
        raise UnsafeRibbon("Sampled conductor radius below three diameters; no repair.")
    report: dict[str, object] = {
        "certificate": certificate,
        "controls": [{"x": p.x, "y": p.y, "z": p.z} for p in points],
        "sampled_minimum_lane_radius_mm": minimum_radius if math.isfinite(minimum_radius) else None,
        "sampled_lane_lengths_mm": lengths,
        "sampled_length_spread": (max(lengths) - min(lengths)) / max(lengths),
        "unmeasured": [
            "continuous lane curvature and clearance",
            "native banking and cap flow",
            "material strain and equilibrium",
        ],
    }
    return tuple(frames), report
