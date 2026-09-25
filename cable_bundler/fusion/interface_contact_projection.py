"""
Best-effort planar diagram data for persistent Interface contacts.
"""

from __future__ import annotations

import math
from typing import Any

from ..domain import AttachmentTargetKind, InterfaceContact
from .attachment_targets import attachment_target_kind, attachment_target_name


def _xyz(point: object) -> list[float] | None:
    """
    Return finite model coordinates in millimeters.
    """
    try:
        values = [float(getattr(point, axis)) * 10.0 for axis in ("x", "y", "z")]
    except (AttributeError, TypeError, ValueError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def _direction(vector: object) -> list[float] | None:
    """
    Normalize a Fusion vector without changing its handedness.
    """
    point = _xyz(vector)
    if point is None:
        return None
    length = math.sqrt(sum(value * value for value in point))
    return [value / length for value in point] if length > 1e-9 else None


def _cross(first: list[float], second: list[float]) -> list[float]:
    """
    Compute one orientation normal from two in-plane axes.
    """
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def _collection_items(collection: object) -> list[object]:
    """
    Read a Fusion collection without assuming Python iteration support.
    """
    count = getattr(collection, "count", 0)
    item = getattr(collection, "item", None)
    return [item(index) for index in range(count)] if callable(item) else []


def _parent_axes(entity: object) -> list[list[float]] | None:
    """
    Return the owning sketch or occurrence axes expressed in assembly space.

    Root-component geometry uses the palette's identity-frame fallback. Missing
    or unavailable host transforms also fall back without hiding the contact.
    """
    try:
        sketch = getattr(entity, "parentSketch", None)
        if sketch is not None:
            x = _direction(getattr(sketch, "xDirection", None))
            y = _direction(getattr(sketch, "yDirection", None))
            if x is not None and y is not None:
                return [x, y, _cross(x, y)]
        occurrence = getattr(entity, "assemblyContext", None)
        if occurrence is None:
            occurrence = getattr(getattr(entity, "body", None), "assemblyContext", None)
        transform = getattr(occurrence, "transform2", None)
        if transform is None:
            return None
        _origin, x_axis, y_axis, z_axis = transform.getAsCoordinateSystem()
        axes = [_direction(axis) for axis in (x_axis, y_axis, z_axis)]
        return [axis for axis in axes if axis is not None] if all(axes) else None
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _curve_points(curve: object, sketch: object | None = None) -> list[list[float]]:
    """
    Sample a curve's outline to within 0.1 mm where Fusion permits.
    """
    evaluator = getattr(curve, "evaluator", None)
    if evaluator is None:
        return []
    points: object = ()
    try:
        extents = evaluator.getParameterExtents()
        if extents[0]:
            sampled = evaluator.getStrokes(extents[1], extents[2], 0.01)
            if sampled[0]:
                points = sampled[1]
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    if not points:
        try:
            ends = evaluator.getEndPoints()
            if ends[0]:
                points = ends[1:3]
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return []
    result: list[list[float]] = []
    for point in list(points)[:512]:
        model_point = sketch.sketchToModelSpace(point) if sketch is not None else point
        coordinates = _xyz(model_point)
        if coordinates is not None:
            result.append(coordinates)
    return result


def _profile_loops(profile: object) -> list[list[list[float]]]:
    """
    Sample each profile boundary, including interior holes.
    """
    sketch = getattr(profile, "parentSketch", None)
    loops = []
    for loop in _collection_items(getattr(profile, "profileLoops", None)):
        outline: list[list[float]] = []
        for segment in _collection_items(getattr(loop, "profileCurves", None)):
            points = _curve_points(getattr(segment, "geometry", None), sketch)
            outline.extend(points if not outline else points[1:])
        if outline:
            loops.append(outline)
    return loops


def _face_loops(face: object) -> list[list[list[float]]]:
    """
    Sample each B-rep edge loop in assembly/model coordinates.
    """
    loops = []
    occurrence = getattr(face, "assemblyContext", None)
    for loop in _collection_items(getattr(face, "loops", None)):
        outline: list[list[float]] = []
        for coedge in _collection_items(getattr(loop, "coEdges", None)):
            edge = getattr(coedge, "edge", None)
            if occurrence is not None and getattr(edge, "assemblyContext", None) is None:
                create_proxy = getattr(edge, "createForAssemblyContext", None)
                if callable(create_proxy):
                    edge = create_proxy(occurrence)
            points = _curve_points(edge)
            if getattr(coedge, "isOpposedToEdge", False):
                points.reverse()
            outline.extend(points if not outline else points[1:])
        if outline:
            loops.append(outline)
    return loops


def _face_normal(face: object) -> list[float] | None:
    """
    Read the local face normal at a representative interior point.
    """
    evaluator = getattr(face, "evaluator", None)
    point = getattr(face, "centroid", None) or getattr(face, "pointOnFace", None)
    surface_normal = _direction(getattr(getattr(face, "geometry", None), "normal", None))
    if evaluator is None or point is None:
        return surface_normal
    try:
        result = evaluator.getNormalAtPoint(point)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return surface_normal
    return _direction(result[1]) if result[0] else surface_normal


def project_interface_contact(design: Any, contact: InterfaceContact) -> dict[str, object]:
    """
    Resolve one contact and expose bounded world-space outline samples.

    A nonplanar face is represented by its boundary projected onto a tangent
    plane. A missing or unsupported outline falls back to a point marker.
    """
    entity = next(
        (
            candidate
            for candidate in (design.findEntityByToken(contact.entity_token) or ())
            if attachment_target_kind(candidate) is contact.kind
        ),
        None,
    )
    parent_axes = _parent_axes(entity) if entity is not None else None
    payload: dict[str, object] = {
        "contactId": str(contact.contact_id),
        "kind": contact.kind.value,
        "name": attachment_target_name(entity, contact.kind)
        if entity is not None
        else contact.kind.value,
        "linked": entity is not None,
        "normal": parent_axes[2] if parent_axes is not None else [0.0, 0.0, 1.0],
        "parentAxes": parent_axes,
        "loops": [],
    }
    if entity is None:
        return payload
    kind = contact.kind
    sketch = getattr(entity, "parentSketch", None)
    if sketch is not None:
        x = _direction(getattr(sketch, "xDirection", None))
        y = _direction(getattr(sketch, "yDirection", None))
        if x is not None and y is not None:
            payload["normal"] = _cross(x, y)
    if kind is AttachmentTargetKind.PROFILE:
        try:
            payload["loops"] = _profile_loops(entity)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            payload["loops"] = []
    elif kind is AttachmentTargetKind.FACE:
        payload["normal"] = _face_normal(entity) or payload["normal"]
        try:
            payload["loops"] = _face_loops(entity)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            payload["loops"] = []
    elif kind is AttachmentTargetKind.CIRCULAR_EDGE:
        payload["normal"] = (
            _direction(getattr(getattr(entity, "geometry", None), "normal", None))
            or payload["normal"]
        )
        try:
            payload["loops"] = [_curve_points(entity)]
        except (AttributeError, RuntimeError, TypeError, ValueError):
            payload["loops"] = []
    else:
        if kind is AttachmentTargetKind.JOINT_ORIGIN:
            first = _direction(getattr(entity, "primaryAxisVector", None))
            second = _direction(getattr(entity, "secondaryAxisVector", None))
            if first is not None and second is not None:
                payload["normal"] = _cross(first, second)
        point = (
            getattr(entity, "worldGeometry", None)
            or getattr(entity, "geometry", None)
            or getattr(getattr(entity, "transform", None), "translation", None)
        )
        coordinates = _xyz(point)
        if coordinates is not None:
            payload["loops"] = [[coordinates]]
    if not any(payload["loops"]):
        fallback = (
            getattr(entity, "centroid", None)
            or getattr(entity, "pointOnFace", None)
            or getattr(getattr(entity, "geometry", None), "center", None)
        )
        coordinates = _xyz(fallback)
        if coordinates is not None:
            payload["loops"] = [[coordinates]]
    return payload
