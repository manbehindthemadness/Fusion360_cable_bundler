"""
Render opt-in sweep analysis evidence without changing native ribbon geometry.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .budget import NativeBudget
from .contracts import RibbonPath as DirectorPath
from .contracts import TargetPose as EndpointCase
from .provenance import mark_loaded
from .traces import TracePath
from .traces import trace as _trace
from .tubes import Witness, inspect_trace

BLUE = (65, 140, 215)
RED = (240, 55, 45)
AMBER = (255, 175, 35)
GREEN = (65, 230, 120)
WHITE = (245, 245, 245)


def set_color(entity: Any, rgb: tuple[int, int, int]) -> None:
    """
    Apply one solid color to a named graphics primitive.
    """
    entity.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(*rgb, 255)
    )


def coordinates(points: tuple[Vector3, ...]) -> Any:
    """
    Convert diagnostic millimeter coordinates to Fusion centimeters.
    """
    return adsk.fusion.CustomGraphicsCoordinates.create(
        [v / 10 for p in points for v in (p.x, p.y, p.z)]
    )


def draw_lines(
    group: Any, points: tuple[Vector3, ...], rgb: tuple[int, int, int], name: str
) -> None:
    """
    Draw connected evidence lines with an inspectable graphics name.
    """
    line = group.addLines(coordinates(points), list(range(len(points))), True)
    line.name = name
    line.weight = 2
    set_color(line, rgb)


def draw_text(
    group: Any, text: str, position: Vector3, rgb: tuple[int, int, int], size: float = 2.5
) -> None:
    """
    Place an experiment annotation in the component's local XY plane.
    """
    matrix = adsk.core.Matrix3D.create()
    matrix.translation = adsk.core.Vector3D.create(
        position.x / 10, position.y / 10, position.z / 10
    )
    entity = group.addText(text, "Arial", size / 10, matrix)
    # Neutral annotations must remain legible on Fusion's light canvas.
    set_color(entity, (40, 40, 40) if rgb == WHITE else rgb)


def draw_curve(
    group: Any, path: DirectorPath, offset: float, number: int, rgb: tuple[int, int, int]
) -> None:
    """
    Draw the same512interval cubic-chain NURBS used for native conductor paths.
    """
    trace = _trace(path, number, offset)
    draw_trace(group, trace, rgb)


def draw_trace(group: Any, trace: TracePath, rgb: tuple[int, int, int]) -> None:
    """
    Display one frozen cubic path without evaluating its original solver again.
    """
    points = [adsk.core.Point3D.create(p.x / 10, p.y / 10, p.z / 10) for p in trace.controls]
    curve = adsk.core.NurbsCurve3D.createNonRational(points, 3, list(trace.knots), False)
    entity = group.addCurve(curve)
    entity.name = {0: "Center trajectory", -1: "A boundary", -2: "B boundary"}.get(
        trace.number, f"Trace {trace.number:02}"
    )
    entity.weight = 2
    set_color(entity, rgb)


def draw_guides(
    groups: dict[str, Any], path: DirectorPath, case: EndpointCase, budget: NativeBudget
) -> list[Witness]:
    """
    Show fixed targets, actual guides and local outside-edge proxy along the run.

    Rulings are material lines, not rigid perpendicular section planes. The
    largerJedge is a proxy and neutral locations are labeled separately.
    """
    half = path.field.half_width_mm
    reach = math.hypot(half, case.diameter_mm / 2)
    witnesses: list[Witness] = []
    for number, offset, rgb in ((-1, half, AMBER), (0, 0.0, WHITE), (-2, -half, (200, 100, 245))):
        budget.check("guide")
        draw_curve(groups["paths"], path, offset, number, rgb)
        measured, _ = inspect_trace(
            _trace(path, number, offset), case, offset, lambda: None, center=number == 0
        )
        witnesses.extend(measured)
        if number != 0:
            worst = next(w for w in measured if w.kind == "lane curvature x 3D")
            value = worst.value * reach / (3 * case.diameter_mm)
            witnesses.append(
                Witness(
                    "proposed boundary macaroni",
                    number,
                    worst.fraction,
                    worst.point,
                    value,
                    0.8,
                    "amber" if value > 0.8 else "measured",
                )
            )
    for position, width, name in (
        (case.start, case.start_width, "Fixed start"),
        (case.end, case.end_width, "Fixed end"),
    ):
        draw_lines(
            groups["targets"],
            (position.translated(width, -half), position.translated(width, half)),
            GREEN,
            name,
        )
        draw_text(groups["targets"], name, position.translated(width, half + 2), GREEN, 2)
    for i in range(17):
        u = i / 16
        a, b = path.lane(u, half)[0], path.lane(u, -half)[0]
        eta_s = path.field.sample(u)[2]
        draw_lines(groups["rulings"], (a, b), (110, 110, 110), f"Material ruling u={u:.4f}")
        outside = a if eta_s > 0 else b
        label = "=" if abs(half * eta_s) <= 1e-6 else ("A" if eta_s > 0 else "B")
        draw_text(groups["rulings"], f"{u:.2f}:{label}", outside, WHITE, 1.5)
    for number in (1, case.lines):
        offset = (number - 1 - (case.lines - 1) / 2) * case.diameter_mm
        actual = path.lane(1, offset)[0]
        target = case.end.translated(case.end_width, offset)
        if magnitude(difference(actual, target)) > 1e-8:
            draw_lines(
                groups["findings"], (actual, target), RED, f"Trace{number:02} closure residual"
            )
    return witnesses


def draw_markers(group: Any, witnesses: list[Witness], diameter: float) -> list[dict[str, Any]]:
    """
    Label the worst finding of each kind, retaining every trace witness in memory.
    """
    worst: dict[str, Witness] = {}
    for witness in witnesses:
        if witness.severity != "measured" and (
            witness.kind not in worst or witness.value > worst[witness.kind].value
        ):
            worst[witness.kind] = witness
    for i, w in enumerate(worst.values()):
        rgb = RED if w.severity == "red" else AMBER
        p = w.point
        draw_lines(
            group,
            (p.translated(Vector3(1, 0, 0), -diameter), p.translated(Vector3(1, 0, 0), diameter)),
            rgb,
            w.kind,
        )
        anchor = p.translated(Vector3(0, 0, 1), (i + 1) * 3 * diameter)
        draw_lines(group, (p, anchor), rgb, f"Witness {w.kind}")
        draw_text(
            group,
            f"{w.kind} T{w.trace} u={w.fraction:.4f}: {w.value:.5g} / {w.limit:.5g}",
            anchor,
            rgb,
            1.7,
        )
    return [asdict(w) for w in worst.values()]


mark_loaded(__file__)
