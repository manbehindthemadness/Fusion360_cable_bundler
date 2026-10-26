"""
Freeze visual constraint witnesses without changing or re-solving a route.

Utilization shows available local margin, not whether relaxing a rule would close
the route. Circle polylines are display glyphs, never geometry certificates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .api import Evidence
from .provenance import mark_loaded
from .traces import TracePath


@dataclass(frozen=True)
class Restriction:
    """
    Capture a caller-declared solver coordinate bound independently of physical rules.
    """

    name: str
    value: float
    lower: float
    upper: float
    source: str

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.source
            or not all(math.isfinite(v) for v in (self.value, self.lower, self.upper))
            or self.lower >= self.upper
        ):
            raise ValueError("Solver restriction requires named finite ordered bounds and source.")


@dataclass(frozen=True)
class Stroke:
    """
    Identify one immutable colored polyline in component-local millimeters.
    """

    role: str
    points: tuple[Vector3, ...]


@dataclass(frozen=True)
class Overlay:
    """
    Share exact displayed measurements and geometry between human and agent.
    """

    key: str
    title: str
    measurements: tuple[tuple[str, float | None], ...]
    strokes: tuple[Stroke, ...]
    notes: tuple[str, ...]
    anchor: Vector3


def circle(point: Vector3, tangent: Vector3, normal: Vector3, radius: float) -> Stroke:
    """
    Draw a 64-chord osculating-circle glyph tangent at the witness point.
    """
    return Stroke(
        "limit",
        tuple(
            point.translated(normal, radius * (1 - math.cos(2 * math.pi * i / 64))).translated(
                tangent, radius * math.sin(2 * math.pi * i / 64)
            )
            for i in range(65)
        ),
    )


def _jet(guide: TracePath, u: float) -> tuple[Vector3, Vector3, Vector3]:
    """
    Evaluate one frozen cubic using its own local derivatives.
    """
    index = min(int(u * len(guide.curves)), len(guide.curves) - 1)
    curve = guide.curves[index]
    t = u * len(guide.curves) - index
    return curve.point(t), curve.derivative(t), curve.second_derivative(t)


def _bend(guide: TracePath, minimum: float, key: str, title: str) -> Overlay:
    """
    Compare actual and minimum radius at the most curved sampled cubic witness.
    """
    peak, witness = 0.0, 0.0
    stationary = 0
    first_moving: float | None = None
    for i, curve in enumerate(guide.curves):
        for t in (0.0, 0.5, 1.0):
            velocity = curve.derivative(t)
            speed = magnitude(velocity)
            if speed <= 1e-12:
                stationary += 1
                continue
            if first_moving is None:
                first_moving = (i + t) / len(guide.curves)
            k = magnitude(cross(velocity, curve.second_derivative(t))) / speed**3
            if k > peak:
                peak, witness = k, (i + t) / len(guide.curves)
    if peak == 0 and first_moving is not None:
        witness = first_moving
    point, velocity, acceleration = _jet(guide, witness)
    tangent = unit(velocity) if magnitude(velocity) > 1e-12 else Vector3(1, 0, 0)
    normal_vector = acceleration.translated(tangent, -dot(acceleration, tangent))
    if magnitude(normal_vector) <= 1e-12:
        axis = min(
            (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)),
            key=lambda a: abs(dot(a, tangent)),
        )
        normal_vector = cross(tangent, axis)
    normal = unit(normal_vector)
    strokes = [circle(point, tangent, normal, minimum)]
    actual = 1 / peak if peak > 1e-10 else None
    # Very large actual circles obscure the route; retain their numerical radius.
    if actual is not None and actual <= 8 * minimum:
        observed = circle(point, tangent, normal, actual)
        strokes.append(Stroke("actual", observed.points))
    strokes.append(Stroke("witness", (point, point.translated(normal, minimum))))
    return Overlay(
        key,
        title,
        (
            ("actual_radius_mm", actual),
            ("minimum_radius_mm", minimum),
            ("utilization", peak * minimum if first_moving is not None else None),
            ("u", witness),
            ("stationary_samples", float(stationary)),
        ),
        tuple(strokes),
        (
            "Red: minimum permitted radius; blue: actual radius.",
            f"R actual {'unavailable (stationary)' if first_moving is None else 'straight/very large' if actual is None else f'{actual:.4g}'} mm; minimum {minimum:.4g} mm; measured use {peak * minimum:.1%}",
            "Local sampled margin is not proof of endpoint reachability.",
            f"Stationary samples with unavailable curvature: {stationary}.",
        ),
        point,
    )


def _containment(evidence: Evidence) -> Overlay:
    """
    Show the existing sphere policy and its worst retained occupied point.
    """
    case = evidence.targets
    midpoint = case.start.translated(difference(case.end, case.start), 0.5)
    radius = 2.5 * case.lines * case.diameter_mm
    axes = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    sphere = tuple(
        Stroke(
            "limit",
            tuple(
                midpoint.translated(axes[i], radius * math.cos(2 * math.pi * j / 64)).translated(
                    axes[(i + 1) % 3], radius * math.sin(2 * math.pi * j / 64)
                )
                for j in range(65)
            ),
        )
        for i in range(3)
    )
    points = (s.point for row in evidence.series for s in row.samples)
    # Older pre-Evidence views retain guides but no scalar sample series.
    positions = tuple(points) or tuple(
        p for g in evidence.guides for p in (c.start for c in g.curves)
    )
    farthest = max(positions, key=lambda p: magnitude(difference(p, midpoint)))
    occupied = magnitude(difference(farthest, midpoint)) + case.diameter_mm / 2
    return Overlay(
        "containment",
        "Containment sphere",
        (("radius_mm", radius), ("occupied_reach_mm", occupied), ("slack_mm", radius - occupied)),
        sphere + (Stroke("witness", (midpoint, farthest)),),
        (
            f"Sphere R {radius:.4g} mm; sampled occupied reach {occupied:.4g} mm; slack {radius - occupied:.4g} mm",
            "Five nominal widths in diameter; thickness allowance included in the measurement.",
        ),
        midpoint,
    )


def _progress(evidence: Evidence, guides: dict[int, TracePath], half: float) -> Overlay:
    """
    Show the worst retained material Jacobian with normalized advance arrows.
    """
    case = evidence.targets
    material = [
        row for row in evidence.series if row.kind == "material J" and row.trace in (-1, -2)
    ]
    progress_strokes = []
    progress_values = []
    material_samples = [(r, s) for r in material for s in r.samples if s.value is not None]
    if material_samples:
        row, sample = min(
            material_samples,
            key=lambda pair: pair[1].value,
        )
        assert sample.value is not None
        u = sample.u
        tangent = unit(_jet(guides[0], u)[1])
        scale = max(half * 0.6, case.diameter_mm)
        for number in (0, -1, -2):
            point = _jet(guides[number], u)[0]
            series = next((r for r in material if r.trace == number), None)
            value = next((s.value for s in series.samples if s.u == u), None) if series else 1.0
            if value is None:
                continue
            progress_strokes.append(
                Stroke("actual", (point, point.translated(tangent, scale * value)))
            )
        progress_values = [("minimum_j", sample.value), ("u", u)]
        notes = (
            f"Minimum J {sample.value:.4g} at u={u:.4f}; hard limit J>0.",
            "Arrows compare modeled forward progress for the same illustrative center advance.",
            "Zero collapses stations; negative progress reverses material order.",
        )
        anchor = sample.point
    else:
        notes = ("Material J measurements were not retained for this older result.",)
        anchor = case.start
    return Overlay(
        "material_progress",
        "Material progress / folding",
        tuple(progress_values),
        tuple(progress_strokes),
        notes,
        anchor,
    )


def _targets(evidence: Evidence, guides: dict[int, TracePath], half: float) -> Overlay:
    """
    Show required terminal frames and the explicitly labeled unsolved center gap.
    """
    case = evidence.targets
    target_strokes = []
    for point, tangent, width in (
        (case.start, case.start_tangent, case.start_width),
        (case.end, case.end_tangent, case.end_width),
    ):
        target_strokes.extend(
            (
                Stroke("target", (point.translated(width, -half), point.translated(width, half))),
                Stroke("target", (point, point.translated(tangent, half))),
            )
        )
    endpoint = guides[0].controls[-1]
    target_strokes.append(Stroke("witness", (endpoint, case.end)))
    gap = magnitude(difference(endpoint, case.end))
    return Overlay(
        "targets",
        "Fixed targets and arrival",
        (("center_gap_mm", gap),),
        tuple(target_strokes),
        (
            f"Green: fixed width/tangent axes; red: unsolved center gap {gap:.4g} mm.",
            "Target frames are not connector-body obstacle geometry.",
        ),
        case.end,
    )


def _solver_limits(
    evidence: Evidence, restrictions: tuple[Restriction, ...], half: float
) -> Overlay:
    """
    Plot declared coordinate bounds without inferring them from the route shape.
    """
    case = evidence.targets
    bars = []
    values = []
    captions = []
    for i, r in enumerate(restrictions):
        point = case.start.translated(Vector3(0, -1, 0), (i + 1) * half * 0.5)
        end = point.translated(Vector3(1, 0, 0), 2 * half)
        at = point.translated(
            Vector3(1, 0, 0), 2 * half * (r.value - r.lower) / (r.upper - r.lower)
        )
        bars.extend(
            (
                Stroke("limit", (point, end)),
                Stroke(
                    "actual",
                    (
                        at.translated(Vector3(0, 1, 0), -half * 0.08),
                        at.translated(Vector3(0, 1, 0), half * 0.08),
                    ),
                ),
            )
        )
        values.extend(
            ((r.name, r.value), (r.name + " lower", r.lower), (r.name + " upper", r.upper))
        )
        captions.append(f"{r.name}: {r.value:.4g} in [{r.lower:.4g}, {r.upper:.4g}]")
    return Overlay(
        "solver_limits",
        "Solver restrictions - not physical laws",
        tuple(values),
        tuple(bars),
        tuple(captions)
        + (
            (
                "Caller-declared coordinate bounds; contact with a bound does not prove it causes failure.",
            )
            if restrictions
            else ("Solver restriction metadata unavailable for this result.",)
        ),
        case.start,
    )


def build(evidence: Evidence, restrictions: tuple[Restriction, ...] = ()) -> tuple[Overlay, ...]:
    """
    Freeze containment, bend, material-map, endpoint and solver-bound witnesses.

    Boundary curvature is a guide witness, not an all-conductor audit. Missing
    material/solver metadata is labeled unavailable rather than inferred.
    """
    guides = {g.number: g for g in evidence.guides}
    half = magnitude(difference(guides[-1].controls[0], guides[-2].controls[0])) / 2
    reach = math.hypot(half, evidence.targets.diameter_mm / 2)
    center = _bend(guides[0], reach / 0.8, "center_bend", "Center macaroni radius")
    witness_u = float(dict(center.measurements)["u"] or 0)
    point, velocity, _ = _jet(guides[0], witness_u)
    if magnitude(velocity) > 1e-12:
        tangent = unit(velocity)
        ruling = difference(_jet(guides[-1], witness_u)[0], _jet(guides[-2], witness_u)[0])
        width = ruling.translated(tangent, -dot(ruling, tangent))
        if magnitude(width) > 1e-12:
            center = replace(
                center,
                strokes=center.strokes
                + (
                    Stroke(
                        "target",
                        (point.translated(unit(width), -half), point.translated(unit(width), half)),
                    ),
                ),
                notes=center.notes
                + ("Green: projected material width; bend plane must be perpendicular to it.",),
            )
    edges = tuple(
        _bend(
            guides[n],
            3 * evidence.targets.diameter_mm,
            "lane_bend",
            "Lane radius - boundary witness",
        )
        for n in (-1, -2)
    )
    edge = max(edges, key=lambda o: dict(o.measurements)["utilization"] or 0)
    return layout(
        evidence,
        (
            _containment(evidence),
            center,
            edge,
            _progress(evidence, guides, half),
            _targets(evidence, guides, half),
            _solver_limits(evidence, restrictions, half),
        ),
    )


def layout(evidence: Evidence, overlays: tuple[Overlay, ...]) -> tuple[Overlay, ...]:
    """
    Move labels and abstract solver gauges beside the route without remeasuring it.

    Physical circles, target axes and progress witnesses retain their real positions.
    """
    points = tuple(p for guide in evidence.guides for p in guide.controls)
    base = Vector3(max(p.x for p in points) + 5, min(p.y for p in points), 0)
    guides = {guide.number: guide for guide in evidence.guides}
    half = magnitude(difference(guides[-1].controls[0], guides[-2].controls[0])) / 2
    result = []
    for overlay in overlays:
        if overlay.key != "solver_limits":
            result.append(replace(overlay, anchor=base))
            continue
        strokes = []
        for i in range(0, len(overlay.strokes), 2):
            bar, marker = overlay.strokes[i : i + 2]
            start = base.translated(Vector3(0, -1, 0), 5 + i / 2 * 3)
            shift = difference(start, bar.points[0])
            strokes.extend(
                Stroke(s.role, tuple(p.translated(shift, 1) for p in s.points))
                for s in (bar, marker)
            )
        result.append(
            replace(
                overlay,
                strokes=tuple(strokes),
                anchor=base.translated(Vector3(1, 0, 0), 2 * half + 3),
            )
        )
    return tuple(result)


mark_loaded(__file__)
