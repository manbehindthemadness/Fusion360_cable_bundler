"""
Resolve the supported Fusion targets used by cable-end attachments.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Optional, Union

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget


def _invoke_cast(
    cast_function: Callable[[object], Optional[object]], entity: object
) -> Optional[object]:
    """
    Invoke a Fusion cast function after its callable boundary has been validated.
    """
    return cast_function(entity)


def _cast(entity_type: object, entity: object) -> Optional[object]:
    """
    Cast an entity through one Fusion type without assuming a live host in tests.
    """
    cast_function = getattr(entity_type, "cast", None)
    if cast_function is None or not callable(cast_function):
        return None
    return _invoke_cast(cast_function, entity)


def attachment_target_kind(entity: object) -> Optional[AttachmentTargetKind]:
    """
    Classify one Fusion selection into the supported attachment target set.
    """
    candidates = (
        (adsk.fusion.Profile, AttachmentTargetKind.PROFILE),
        (adsk.fusion.BRepFace, AttachmentTargetKind.FACE),
        (adsk.fusion.JointOrigin, AttachmentTargetKind.JOINT_ORIGIN),
        (adsk.fusion.BRepEdge, AttachmentTargetKind.CIRCULAR_EDGE),
        (adsk.fusion.ConstructionPoint, AttachmentTargetKind.CONSTRUCTION_POINT),
        (adsk.fusion.SketchPoint, AttachmentTargetKind.SKETCH_POINT),
    )
    return next((kind for entity_type, kind in candidates if _cast(entity_type, entity)), None)


def _point_coordinates(point: object) -> Optional[tuple[float, float, float]]:
    """
    Validate finite model-space coordinates from one Fusion point.
    """
    try:
        coordinates = float(point.x), float(point.y), float(point.z)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return coordinates if all(math.isfinite(value) for value in coordinates) else None


def _collection_items(collection: object) -> tuple[object, ...]:
    """
    Read indexed Fusion collections without assuming Python iteration support.
    """
    count = getattr(collection, "count", 0)
    item = getattr(collection, "item", None)
    return tuple(item(index) for index in range(count)) if callable(item) else ()


def _circular_hole_center(face: object) -> Optional[adsk.core.Point3D]:
    """
    Resolve one concentric circular inner loop in the face's assembly context.
    """
    inner_loops = [
        loop for loop in _collection_items(getattr(face, "loops", None)) if not loop.isOuter
    ]
    if len(inner_loops) != 1:
        return None
    centers: list[adsk.core.Point3D] = []
    coordinates: list[tuple[float, float, float]] = []
    context = getattr(face, "assemblyContext", None)
    for coedge in _collection_items(inner_loops[0].coEdges):
        edge = coedge.edge
        if context is not None and getattr(edge, "assemblyContext", None) is None:
            edge = edge.createForAssemblyContext(context)
        geometry = edge.geometry
        if geometry.objectType not in ("adsk::core::Circle3D", "adsk::core::Arc3D"):
            return None
        center = geometry.center
        point = _point_coordinates(center)
        if point is None:
            return None
        centers.append(center)
        coordinates.append(point)
    if not centers:
        return None
    first = coordinates[0]
    if any(math.dist(point, first) >= 1e-6 for point in coordinates[1:]):
        return None
    return centers[0]


def face_contact_center(face: object, sampled_point: adsk.core.Point3D) -> adsk.core.Point3D:
    """
    Anchor a face contact at its circular hole or geometric area center.

    The saved on-face sample remains the fallback when Fusion cannot provide a
    center; callers may still use that sample to evaluate the normal.
    """
    try:
        hole_center = _circular_hole_center(face)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        hole_center = None
    if hole_center is not None:
        return hole_center
    try:
        center = getattr(face, "centroid", None)
        if center is not None and _point_coordinates(center) is not None:
            return center
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return sampled_point


def explicit_attachment_target_name(entity: object, kind: AttachmentTargetKind) -> str:
    """
    Return the closest explicit Fusion geometry name, or empty text if absent.
    """
    if kind in {AttachmentTargetKind.JOINT_ORIGIN, AttachmentTargetKind.CONSTRUCTION_POINT}:
        name = getattr(entity, "name", "")
    elif kind in {AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT}:
        name = getattr(getattr(entity, "parentSketch", None), "name", "")
    else:
        body = getattr(entity, "body", None)
        name = getattr(body, "name", "")
    return name.strip() if isinstance(name, str) else ""


def attachment_target_name(entity: object, kind: AttachmentTargetKind) -> str:
    """
    Return the closest user-controlled Fusion name or a descriptive fallback.
    """
    name = explicit_attachment_target_name(entity, kind)
    if name:
        return name
    labels = {
        AttachmentTargetKind.PROFILE: "Socket profile",
        AttachmentTargetKind.FACE: "Body face",
        AttachmentTargetKind.JOINT_ORIGIN: "Joint origin",
        AttachmentTargetKind.CIRCULAR_EDGE: "Circular edge",
        AttachmentTargetKind.CONSTRUCTION_POINT: "Construction point",
        AttachmentTargetKind.SKETCH_POINT: "Sketch point",
    }
    return labels[kind]


def resolve_attachment_target(
    design: adsk.fusion.Design,
    attachment: Union[CableEndAttachment, CableEndTarget],
) -> Optional[object]:
    """
    Resolve the saved token only when it still identifies the expected entity kind.
    """
    if not attachment.has_target:
        return None
    entities = design.findEntityByToken(attachment.entity_token) or ()
    return next(
        (entity for entity in entities if attachment_target_kind(entity) is attachment.target_kind),
        None,
    )


def attachment_display_name(
    design: Optional[adsk.fusion.Design],
    attachment: Union[CableEndAttachment, CableEndTarget],
) -> str:
    """
    Resolve a live inherited name while retaining the saved fallback when disconnected.
    """
    if attachment.name.strip():
        return attachment.name.strip()
    entity = resolve_attachment_target(design, attachment) if design is not None else None
    return (
        attachment_target_name(entity, attachment.target_kind)
        if entity is not None and attachment.target_kind is not None
        else attachment.display_name
    )
