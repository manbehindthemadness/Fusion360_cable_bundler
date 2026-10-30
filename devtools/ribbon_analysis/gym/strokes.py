"""
Build shared drawing primitives for an empty gym and two selected virtual goals.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross

from .scene import AXES, ZONES, Box, Scene


def drawing(scene: Scene) -> dict[str, Any]:
    """
    Describe sparse zones, solid faces and target glyphs without drawing a route.
    """
    strokes: list[dict[str, Any]] = []
    surfaces: list[dict[str, Any]] = []

    def line(points: tuple[Vector3, ...], role: str) -> None:
        """
        Append one connected millimeter polyline with its visual role.
        """
        strokes.append({"points": [asdict(point) for point in points], "role": role})

    def box(shape: Box, role: str, opacity: float) -> None:
        """
        Add six quadrilaterals and their shared boundary strokes.
        """
        for index in range(6):
            corners = shape.face(index)[3]
            line(corners + (corners[0],), role)
            if opacity:
                surfaces.append(
                    {
                        "points": [asdict(point) for point in corners],
                        "role": role,
                        "opacity": opacity,
                        "face": index,
                    }
                )

    side = scene.config.side_mm
    box(Box(Vector3(0, 0, 0), (side, side, side)), "void", 0.035)
    box(Box(Vector3(0, 0, 0), (3 * side,) * 3), "grid", 0)
    for axis in range(3):
        for sign in (-1, 1):
            origin = Vector3(0, 0, 0).translated(AXES[axis], sign * 1.5 * side)
            for fixed, moving in (
                ((axis + 1) % 3, (axis + 2) % 3),
                ((axis + 2) % 3, (axis + 1) % 3),
            ):
                for offset in (-0.5, 0.5):
                    center = origin.translated(AXES[fixed], offset * side)
                    line(
                        (
                            center.translated(AXES[moving], -1.5 * side),
                            center.translated(AXES[moving], 1.5 * side),
                        ),
                        "grid",
                    )
    for target_role, goal in (("a", scene.a), ("b", scene.b)):
        zone = ZONES[goal.zone]
        box(
            Box(Vector3(*(coordinate * side for coordinate in zone)), (side,) * 3),
            target_role + "-zone",
            0,
        )
        solid = scene.box(goal.zone)
        box(solid, target_role, 0.18)
        target_corners = solid.face(goal.face)[3]
        surfaces.append(
            {
                "points": [asdict(point) for point in target_corners],
                "role": target_role,
                "opacity": 0.65,
                "face": goal.face,
            }
        )
        origin, normal, across = scene.pose(goal)
        up = cross(normal, across)
        tip = origin.translated(normal, side * 0.45)
        line((origin, tip), target_role)
        for sign in (-1, 1):
            line(
                (tip.translated(normal, -side * 0.10).translated(across, sign * side * 0.05), tip),
                target_role,
            )
        line(
            (
                origin.translated(across, -scene.config.width_mm / 2),
                origin.translated(across, scene.config.width_mm / 2),
            ),
            target_role,
        )
        for conductor_index in range(scene.config.lines):
            offset = (conductor_index - (scene.config.lines - 1) / 2) * scene.config.diameter_mm
            center = origin.translated(across, offset)
            circle = tuple(
                center.translated(
                    across, scene.config.diameter_mm / 2 * math.cos(i * math.tau / 24)
                ).translated(up, scene.config.diameter_mm / 2 * math.sin(i * math.tau / 24))
                for i in range(25)
            )
            line(circle, target_role)
    return {"strokes": strokes, "surfaces": surfaces}
