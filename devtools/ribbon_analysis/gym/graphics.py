"""
Render the same frozen gym primitives in both native experimental viewers.
"""

from __future__ import annotations

from typing import Any, Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.routing.geometry import Vector3

from ..graphics import coordinates, draw_lines, set_color

COLORS = {
    "grid": (100, 120, 145),
    "void": (25, 185, 170),
    "a": (75, 155, 255),
    "b": (255, 165, 65),
    "a-zone": (55, 100, 150),
    "b-zone": (155, 100, 45),
}
GROUP_NAME = "Gym / empty center / virtual goal faces"


def draw(
    component: Any,
    drawing: dict[str, Any],
    checkpoint: Callable[[], None],
    *,
    prepath: dict[str, Any] | None = None,
) -> Any:
    """
    Replace this owned component's gym groups only after a complete drawing succeeds.

    Remove all prior groups bearing this renderer's reserved name, including
    orphaned groups whose Python handles were lost. Other graphics remain intact.
    Drawing failure removes its incomplete new group and preserves prior groups.
    Failure to retire a prior owned drawing is reported rather than hidden.
    """
    group = component.customGraphicsGroups.add()
    group.name = GROUP_NAME
    try:
        for item in drawing["surfaces"]:
            points = tuple(Vector3(**point) for point in item["points"])
            triangles = [
                vertex for index in range(1, len(points) - 1) for vertex in (0, index, index + 1)
            ]
            mesh = group.addMesh(coordinates(points), triangles, [], [])
            mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
            set_color(mesh, COLORS[item["role"]])
            if not mesh.setOpacity(item["opacity"], True):
                raise RuntimeError("Fusion could not set goal transparency.")
        checkpoint()
        if prepath is not None:
            curve = adsk.core.NurbsCurve3D.createNonRational(
                [
                    adsk.core.Point3D.create(*(p[a] / 10 for a in "xyz"))
                    for p in prepath["controls"]
                ],
                3,
                [0.0] * 4 + [1.0] * 4,
                False,
            )
            if curve is None:
                raise RuntimeError("Fusion could not create the endpoint pre-path.")
            entity = group.addCurve(curve)
            entity.name = "Pre-path - unconstrained endpoint-tangent spline"
            entity.weight = 3
            set_color(entity, (225, 45, 190))
        for item in drawing["strokes"]:
            draw_lines(
                group,
                tuple(Vector3(**point) for point in item["points"]),
                COLORS[item["role"]],
                item["role"],
            )
        checkpoint()
        groups = component.customGraphicsGroups
        for index in reversed(range(groups.count)):
            previous = groups.item(index)
            if previous != group and previous.name == GROUP_NAME:
                if not previous.deleteMe():
                    raise RuntimeError("Fusion could not remove a prior owned gym drawing.")
    except (RuntimeError, ValueError, TypeError, AttributeError):
        group.deleteMe()
        raise
    return group
