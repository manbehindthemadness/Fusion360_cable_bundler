"""
Inspect exact sweep cubics and tessellate diagnostic circular conductor tubes.

This opt-in experiment instrument supplies sampled witnesses, not a physical
simulation, continuous collision certificate or Fusion kernel prediction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from cable_bundler.routing.geometry import (
    Vector3,
    cross,
    difference,
    dot,
    lerp,
    magnitude,
    unit,
)

from .endpoint_first import EndpointCase
from .endpoint_trace_paths import TracePath


@dataclass(frozen=True)
class Witness:
    """
    Locate one worst sampled measurement on an identified material trajectory.
    """

    kind: str
    trace: int
    fraction: float
    point: Vector3
    value: float
    limit: float
    severity: str


@dataclass
class Tube:
    """
    Hold a disposable indexed mesh in millimeters and its sampled evidence.
    """

    vertices: list[float]
    triangles: list[int]
    hot_triangles: list[int]
    points: tuple[Vector3, ...]
    witnesses: tuple[Witness, ...]
    length_mm: float
    midpoint_chord_error_mm: float
    angular_sagitta_mm: float
    maximum_tangent_step_degrees: float
    analysis_seconds: float
    mesh_seconds: float


def transport_normal(previous: Vector3, tangent: Vector3, normal: Vector3) -> Vector3:
    """
    Rotate a circle frame by the shortest tangent rotation, without Frenet flips.

    Opposed tangents are unresolved; do not invent a frame through a cusp.
    This only orients mesh vertices, never the ribbon's physical material frame.
    """
    cosine = max(-1.0, min(1.0, dot(previous, tangent)))
    if cosine < -0.999999:
        raise ValueError("Opposed mesh tangents need finer sampling or a cusp investigation.")
    axis = cross(previous, tangent)
    rotated = normal.translated(cross(axis, normal), 1).translated(
        cross(axis, cross(axis, normal)), 1 / (1 + cosine)
    )
    return unit(rotated.translated(tangent, -dot(rotated, tangent)))


def inspect_trace(
    trace: TracePath,
    case: EndpointCase,
    offset: float,
    checkpoint: Callable[[], None],
    *,
    center: bool = False,
) -> tuple[tuple[Witness, ...], frozenset[int]]:
    """
    Sample each exact cubic at both ends and midpoint; retain worst rule witnesses.

    Knot sides are evaluated separately. Full-width macaroni on boundary paths is
    a proposed diagnostic only; center macaroni and lane3D are existing policies.
    No pass/compliance classification is returned. Length and contact are separate.
    """
    if not trace.curves or len(trace.curves) > 1024:
        raise ValueError("Expected one bounded, nonempty cubic trace chain.")
    diameter = case.diameter_mm
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Conductor diameter must be positive and finite.")
    reach = math.hypot(case.lines * diameter / 2 + 0.1 * diameter, diameter / 2)
    origin = lerp(case.start, case.end, 0.5)
    maxima: dict[str, Witness] = {}
    hot: set[int] = set()

    def retain(kind: str, fraction: float, location: Vector3, value: float, limit: float) -> None:
        """
        Retain the worst normalized value, including a location when below limit.
        """
        old = maxima.get(kind)
        if old is None or value > old.value:
            maxima[kind] = Witness(
                kind,
                trace.number,
                fraction,
                location,
                value,
                limit,
                "red" if value > limit else "measured",
            )

    for index, curve in enumerate(trace.curves):
        if index % 64 == 0:
            checkpoint()
        for t in (0.0, 0.5, 1.0):
            point, velocity = curve.point(t), curve.derivative(t)
            speed = magnitude(velocity)
            if speed <= 1e-12:
                raise ValueError(f"Trace{trace.number} has a stationary cubic at{index}:{t}.")
            curvature = magnitude(cross(velocity, curve.second_derivative(t))) / speed**3
            u = (index + t) / len(trace.curves)
            retain("lane curvature x 3D", u, point, curvature * 3 * diameter, 1)
            retain(
                "sphere reach mm",
                u,
                point,
                magnitude(difference(point, origin)) + diameter / 2,
                2.5 * case.lines * diameter,
            )
            if center:
                retain("center macaroni", u, point, curvature * reach, 0.8)
            if curvature * 3 * diameter > 1:
                hot.add(index)
    for end, position, width, tangent in (
        (0, case.start, case.start_width, case.start_tangent),
        (1, case.end, case.end_width, case.end_tangent),
    ):
        curve = trace.curves[0 if end == 0 else -1]
        point = curve.point(float(end))
        retain(
            "target error mm",
            float(end),
            point,
            magnitude(difference(point, position.translated(width, offset))),
            1e-8,
        )
        retain(
            "target tangent vector error",
            float(end),
            point,
            magnitude(difference(unit(curve.derivative(float(end))), tangent)),
            1e-7,
        )
    return tuple(maxima.values()), frozenset(hot)


def tube_mesh(
    trace: TracePath,
    case: EndpointCase,
    offset: float,
    checkpoint: Callable[[], None],
    *,
    sides: int = 12,
) -> Tube:
    """
    Tessellate at every cubic boundary, using transported circular rings and caps.

    Report midpoint chord deviation and angular sagitta, not a surface error bound.
    Coarse intervals are explicitly unresolved; no smoothing or path repair occurs.
    Red faces mark intervals with a sampled lane-curvature policy violation.
    """
    if isinstance(sides, bool) or not isinstance(sides, int) or not 6 <= sides <= 32:
        raise ValueError("Use6..32vertices per diagnostic circular section.")
    started = perf_counter()
    witnesses, hot = inspect_trace(trace, case, offset, checkpoint)
    analysis_seconds = perf_counter() - started
    started = perf_counter()
    points = tuple(c.start for c in trace.curves) + (trace.curves[-1].end,)
    tangents = tuple(unit(c.derivative(0)) for c in trace.curves) + (
        unit(trace.curves[-1].derivative(1)),
    )
    if any(
        magnitude(difference(a.end, b.start)) > 1e-8 for a, b in zip(trace.curves, trace.curves[1:])
    ):
        raise ValueError("Disconnected sweep cubics cannot be joined by a preview mesh.")
    tangent = tangents[0]
    axis = min(
        (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)), key=lambda a: abs(dot(a, tangent))
    )
    normal = unit(cross(tangent, axis))
    radius = case.diameter_mm / 2
    circle = tuple(
        (math.cos(2 * math.pi * j / sides), math.sin(2 * math.pi * j / sides)) for j in range(sides)
    )
    vertices: list[float] = []
    triangles: list[int] = []
    red: list[int] = []
    angle = 0.0
    for i, (point, following) in enumerate(zip(points, tangents)):
        if i % 64 == 0:
            checkpoint()
        angle = max(angle, math.degrees(math.acos(max(-1.0, min(1.0, dot(tangent, following))))))
        normal = transport_normal(tangent, following, normal)
        tangent = following
        other = cross(tangent, normal)
        for cosine, sine in circle:
            vertex = point.translated(normal, radius * cosine).translated(other, radius * sine)
            vertices.extend((vertex.x, vertex.y, vertex.z))
        if i == 0:
            continue
        for j in range(sides):
            a, b = (i - 1) * sides + j, (i - 1) * sides + (j + 1) % sides
            c, d = i * sides + j, i * sides + (j + 1) % sides
            faces = [a, b, c, b, d, c]
            triangles.extend(faces)
            if i - 1 in hot:
                red.extend(faces)
    for end, point in ((0, points[0]), (len(points) - 1, points[-1])):
        cap = len(vertices) // 3
        vertices.extend((point.x, point.y, point.z))
        for j in range(sides):
            a, b = end * sides + j, end * sides + (j + 1) % sides
            triangles.extend([cap, b, a] if end == 0 else [cap, a, b])
    error = max(
        magnitude(difference(c.point(0.5), lerp(c.start, c.end, 0.5))) for c in trace.curves
    )
    length = sum(magnitude(difference(b, a)) for a, b in zip(points, points[1:]))
    return Tube(
        vertices,
        triangles,
        red,
        points,
        witnesses,
        length,
        error,
        radius * (1 - math.cos(math.pi / sides)),
        angle,
        analysis_seconds,
        perf_counter() - started,
    )
