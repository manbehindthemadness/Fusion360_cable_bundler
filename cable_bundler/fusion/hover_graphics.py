"""
Transient, view-scaled crosses for geometry owned by a hovered diagram node.
"""

from __future__ import annotations

from typing import Any, Union

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget
from .graphics_styles import REFINE_COLOR

_GROUP_ID = "kev0.cable_bundler.hover_widgets"


def clear_hover_widgets(design: adsk.fusion.Design) -> None:
    """
    Delete only this add-in's temporary hover widgets.
    """
    groups = design.rootComponent.customGraphicsGroups
    for index in range(groups.count - 1, -1, -1):
        group = groups.item(index)
        if group is not None and group.id == _GROUP_ID:
            group.deleteMe()


def target_point(
    entity: Any, target: Union[CableEndAttachment, CableEndTarget]
) -> adsk.core.Point3D:
    """
    Locate the saved contact point, including face UV coordinates, in model space.
    """
    kind = target.target_kind
    if kind is AttachmentTargetKind.PROFILE:
        return profile_point(entity)
    if kind is AttachmentTargetKind.FACE:
        success, point = entity.evaluator.getPointAtParameter(
            adsk.core.Point2D.create(*target.parameters)
        )
        if not success:
            raise ValueError("Fusion could not resolve the hovered face contact point.")
        return point
    if kind is AttachmentTargetKind.JOINT_ORIGIN:
        translation = entity.transform.translation
        return adsk.core.Point3D.create(translation.x, translation.y, translation.z)
    if kind is AttachmentTargetKind.CIRCULAR_EDGE:
        return entity.geometry.center
    if kind is AttachmentTargetKind.SKETCH_POINT:
        return entity.worldGeometry
    if kind is AttachmentTargetKind.CONSTRUCTION_POINT:
        return entity.geometry
    raise ValueError("The hovered connection has no supported contact geometry.")


def profile_point(profile: adsk.fusion.Profile) -> adsk.core.Point3D:
    """
    Locate a profile centroid in model coordinates rather than sketch coordinates.
    """
    return profile.parentSketch.sketchToModelSpace(profile.areaProperties().centroid)


def show_hover_widgets(design: adsk.fusion.Design, points: tuple[adsk.core.Point3D, ...]) -> None:
    """
    Replace hover crosses with nonselectable, 40-pixel pink XYZ markers.

    View scaling preserves screen size and the model-space contact anchor during
    zoom. Covered portions show through geometry at 98 percent opacity.
    """
    clear_hover_widgets(design)
    if not points:
        return
    group = design.rootComponent.customGraphicsGroups.add()
    group.id = _GROUP_ID
    group.isSelectable = False
    seen: set[tuple[float, float, float]] = set()
    try:
        for point in points:
            center = (point.x, point.y, point.z)
            if center in seen:
                continue
            seen.add(center)
            vertices: list[float] = []
            for axis in range(3):
                for offset in (-20.0, 20.0):
                    vertex = list(center)
                    vertex[axis] += offset
                    vertices.extend(vertex)
            coordinates = adsk.fusion.CustomGraphicsCoordinates.create(vertices)
            lines = group.addLines(coordinates, [], False)
            color = adsk.core.Color.create(*REFINE_COLOR, 255)
            effect = adsk.fusion.CustomGraphicsShowThroughColorEffect.create(color, 0.98)
            if effect is None:
                raise RuntimeError("Fusion could not create the hover show-through color.")
            lines.color = effect
            lines.weight = 4.0
            lines.isSelectable = False
            lines.depthPriority = 100
            lines.viewScale = adsk.fusion.CustomGraphicsViewScale.create(1.0, point)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        clear_hover_widgets(design)
        raise
