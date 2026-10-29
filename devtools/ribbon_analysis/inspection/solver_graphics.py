"""
Render reusable recorded solver panels and independently switchable constraint witnesses.
"""

from __future__ import annotations

from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from ..constraint_geometry import Overlay
from ..graphics import draw_lines, draw_text, draw_trace
from ..solver_details import retain_solver_details
from .panels import bend_witness, build
from .session import Session


def _draw(
    component: Any,
    overlay: Overlay,
    scale: float,
    *,
    captions: bool = True,
    screen_anchor: Vector3 | None = None,
) -> Any:
    """
    Render the same immutable polylines/captions available to numerical inspection.
    """
    colors = {
        "limit": (220, 65, 50),
        "actual": (35, 90, 170),
        "target": (20, 160, 80),
        "witness": (210, 90, 20),
        "edge_b": (145, 65, 180),
    }
    group = component.customGraphicsGroups.add()
    group.name = overlay.title
    origin = screen_anchor or Vector3(0, 0, 0)
    if screen_anchor is not None:
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(
            origin.x / 10, origin.y / 10, origin.z / 10
        )
        group.transform = transform
        billboard = adsk.fusion.CustomGraphicsBillBoard.create(None)
        if billboard is None:
            raise RuntimeError("Fusion could not create a camera-facing solver panel.")
        group.billBoarding = billboard
    for stroke in overlay.strokes:
        if len(stroke.points) >= 2:
            draw_lines(
                group,
                tuple(difference(point, origin) for point in stroke.points),
                colors[stroke.role],
                overlay.title + " / " + stroke.role,
            )
    if captions:
        draw_text(
            group,
            overlay.title,
            difference(overlay.anchor, origin).translated(Vector3(0, -1, 0), 2 * scale),
            (25, 25, 25),
            2 * scale,
        )
        for index, note in enumerate(overlay.notes):
            draw_text(
                group,
                note,
                difference(overlay.anchor, origin).translated(
                    Vector3(0, -1, 0), (5 + index * 3) * scale
                ),
                (40, 40, 40),
                1.7 * scale,
            )
        if screen_anchor is not None:
            for index in range(group.count):
                entity = group.item(index)
                if entity.objectType == adsk.fusion.CustomGraphicsText.classType():
                    entity.billBoarding = adsk.fusion.CustomGraphicsBillBoard.create(None)
    return group


def render(
    component: Any, method_component: Any, session: Session, checkpoint: Callable[[], None]
) -> tuple[list[Any], list[Any], Any, Any]:
    """
    Retain hidden result metadata and display camera-facing solver panels for every path.

    Physical witness groups start separately switchable. Baseline ghosts use the
    immutable matched result, not a reconstructed route or a previous source version.
    """
    snapshot = session.snapshot
    if snapshot is None:
        raise ValueError("Solver graphics require selected frozen geometry.")
    source, summary, chart = build(session.state(), snapshot)
    scale = min(1.0, max(0.2, snapshot.diameter_mm / 4))
    sketch: Any = (
        retain_solver_details(method_component, source, summary, checkpoint, text_scale=scale)
        if session.proposal == -1
        else None
    )
    if (
        sketch is not None
        and sketch.attributes.itemByName("RibbonInspection", "custom_graphics_presentation") is None
    ):
        sketch.isLightBulbOn = False
        sketch.attributes.add("RibbonInspection", "custom_graphics_presentation", "true")
    panels = [
        _draw(component, chart, scale, screen_anchor=summary.anchor),
        _draw(component, summary, scale, screen_anchor=summary.anchor),
    ]
    half = session.targets.lines * snapshot.diameter_mm / 2 + snapshot.diameter_mm * 0.1
    reach = (half**2 + (snapshot.diameter_mm / 2) ** 2) ** 0.5
    helpers = []
    for guide in snapshot.guides:
        checkpoint()
        minimum = reach / 0.78 if guide.number == 0 else 3.1 * snapshot.diameter_mm
        helpers.append(
            _draw(
                component,
                bend_witness(
                    guide,
                    minimum,
                    "Centre reach reference"
                    if guide.number == 0
                    else f"Edge {guide.number} radius reference",
                ),
                scale,
                captions=False,
            )
        )
    center = next(guide for guide in snapshot.guides if guide.number == 0)
    gap = component.customGraphicsGroups.add()
    gap.name = "Constraint witness - fixed end position"
    if magnitude(difference(center.controls[-1], session.targets.end)) > 1e-12:
        draw_lines(
            gap,
            (center.controls[-1], session.targets.end),
            (20, 160, 80),
            "Actual end to fixed target",
        )
    helpers.append(gap)
    baseline = session.baseline()
    ghost = None
    if baseline is not None:
        ghost = component.customGraphicsGroups.add()
        ghost.name = "Grey matched baseline / recorded result"
        for guide in baseline.guides:
            draw_trace(ghost, guide, (155, 160, 165))
    return panels, helpers, sketch, ghost
