"""
Render the shared thickness shell as translucent Fusion Custom Graphics only.
"""

from __future__ import annotations

from typing import Any

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..graphics import coordinates, draw_lines, set_color
from .thickness import ThicknessMesh


def draw(component: Any, shell: ThicknessMesh) -> Any:
    """
    Return one switchable group containing a mesh and sparse boundary guides.
    """
    group = component.customGraphicsGroups.add()
    group.name = f"Nominal thickness envelope / {shell.thickness_mm:g} mm"
    mesh = group.addMesh(
        coordinates(shell.vertices),
        [index for triangle in shell.triangles for index in triangle],
        [],
        [],
    )
    mesh.name = shell.description
    mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
    set_color(mesh, (25, 145, 155))
    if not mesh.setOpacity(shell.opacity, True):
        raise RuntimeError("Fusion could not make the thickness envelope translucent.")
    for indices in shell.outlines:
        draw_lines(
            group,
            tuple(shell.vertices[index] for index in indices),
            (40, 125, 135),
            "Nominal thickness boundary",
        )
    return group
