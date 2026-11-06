"""
Display caller-owned finite terminal envelopes and measured intrusion without changing cable geometry.
"""

from __future__ import annotations

from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.graphics import coordinates, draw_lines, set_color

from .check import Report
from .model import Hardware

GROUP_NAME = "Terminal hardware trial - finite clearance envelopes"


def draw(
    component: Any,
    hardware: Hardware,
    report: Report,
    checkpoint: Callable[[], None],
) -> Any:
    """
    Draw two small translucent boxes and an actual witness in the supplied layout's millimeter frame.

    The caller supplies an explicitly owned component and matching frozen report.
    Only this renderer's prior groups are replaced after successful drawing.
    This helper performs no analysis, body construction or document selection.
    """
    group = component.customGraphicsGroups.add()
    group.name = GROUP_NAME
    try:
        for box in hardware.boxes:
            checkpoint()
            points = box.corners()
            rgb = (
                (255, 65, 75)
                if report.witness is not None and report.witness.terminal == box.terminal.value
                else (65, 205, 245)
            )
            faces = (
                (0, 1, 3, 2),
                (4, 6, 7, 5),
                (0, 4, 5, 1),
                (2, 3, 7, 6),
                (0, 2, 6, 4),
                (1, 5, 7, 3),
            )
            triangles = [index for a, b, c, d in faces for index in (a, b, c, a, c, d)]
            mesh = group.addMesh(coordinates(points), triangles, [], [])
            mesh.name = f"{box.terminal.value} finite hardware envelope"
            set_color(mesh, rgb)
            if not mesh.setOpacity(0.2, True):
                raise RuntimeError("Fusion could not set terminal envelope transparency")
            for i in range(8):
                for bit in (1, 2, 4):
                    if i < (i ^ bit):
                        draw_lines(group, (points[i], points[i ^ bit]), rgb, box.terminal.value)
        if report.witness is not None:
            point = report.witness.point
            radius = hardware.targets.diameter_mm / 2
            for axis in (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)):
                draw_lines(
                    group,
                    (point.translated(axis, -radius), point.translated(axis, radius)),
                    (255, 245, 45),
                    "Measured cable interior inside terminal envelope",
                )
                marker = group.item(group.count - 1)
                marker.depthPriority = 50
                marker.weight = 4
        checkpoint()
        groups = component.customGraphicsGroups
        for index in reversed(range(groups.count)):
            previous = groups.item(index)
            if previous != group and previous.name == GROUP_NAME and not previous.deleteMe():
                raise RuntimeError("Fusion could not retire the prior terminal drawing")
    except (RuntimeError, ValueError, TypeError, AttributeError):
        group.deleteMe()
        raise
    return group
