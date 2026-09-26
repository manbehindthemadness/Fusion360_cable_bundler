"""
Discover connection-compatible row targets in one Fusion ownership context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

from ..application.interface_contact_rows import ROW_TOLERANCE_MM, RowTarget, select_contact_row
from ..domain import AttachmentTargetKind
from .attachment_targets import attachment_target_kind
from .interface_contact_projection import (
    _collection_items,
    _direction,
    _face_normal,
    _parent_axes,
    _xyz,
)


@dataclass(frozen=True)
class _Scope:
    """
    Retain a native owning sketch/component and its particular assembly instance.
    """

    owner: Any
    occurrence: Any
    key: tuple[str, str]


def _scope(entity: Any) -> _Scope:
    """
    Restrict a row to the first endpoint's sketch or component occurrence.
    """
    sketch = getattr(entity, "parentSketch", None)
    body = getattr(entity, "body", None)
    owner = (
        sketch or getattr(body, "parentComponent", None) or getattr(entity, "parentComponent", None)
    )
    if owner is None:
        raise ValueError("The row target has no available owning sketch or component.")
    occurrence = (
        getattr(entity, "assemblyContext", None)
        or getattr(sketch, "assemblyContext", None)
        or getattr(body, "assemblyContext", None)
    )
    owner = getattr(owner, "nativeObject", None) or owner
    key = (owner.entityToken, getattr(occurrence, "fullPathName", ""))
    return _Scope(owner, occurrence, key)


def _in_context(entity: Any, occurrence: Any) -> Any:
    """
    Express native geometry in the selected occurrence, preserving its placement.
    """
    if occurrence is None or getattr(entity, "assemblyContext", None) is not None:
        return entity
    return entity.createForAssemblyContext(occurrence)


def _face_center(face: Any) -> list[float] | None:
    """
    Prefer a single circular hole center; otherwise use the face area centroid.

    Hole centers keep circular and square connector pads on the same row even
    when copper connected to the pad changes the face's area centroid.
    """
    inner = [loop for loop in _collection_items(face.loops) if not loop.isOuter]
    if len(inner) == 1:
        centers = []
        for coedge in _collection_items(inner[0].coEdges):
            edge = _in_context(coedge.edge, getattr(face, "assemblyContext", None))
            geometry = edge.geometry
            if geometry.objectType not in ("adsk::core::Circle3D", "adsk::core::Arc3D"):
                break
            center = _xyz(geometry.center)
            if center is None:
                break
            centers.append(center)
        else:
            if centers and all(math.dist(center, centers[0]) < 1e-5 for center in centers):
                return centers[0]
    return _xyz(face.centroid)


def describe_row_target(entity: Any) -> RowTarget:
    """
    Read a target's assembly-space center and actual geometry orientation.

    Raises ValueError for unsupported targets, missing geometry, or orientations.
    Runtime API failures are left visible for endpoint validation.
    """
    kind = attachment_target_kind(entity)
    token = getattr(entity, "entityToken", "")
    if kind is None or not isinstance(token, str) or not token.strip():
        raise ValueError("Pick a persistent connection-compatible row target.")
    normal = None
    geometry_type = kind.value
    if kind is AttachmentTargetKind.FACE:
        geometry = entity.geometry
        geometry_type = geometry.objectType
        center = _face_center(entity)
        normal = _direction(getattr(geometry, "axis", None)) or _face_normal(entity)
    elif kind is AttachmentTargetKind.CIRCULAR_EDGE:
        geometry = entity.geometry
        if geometry.objectType != "adsk::core::Circle3D":
            raise ValueError("Row edges must be circular.")
        center, normal = _xyz(geometry.center), _direction(geometry.normal)
    elif kind is AttachmentTargetKind.PROFILE:
        sketch = entity.parentSketch
        center = _xyz(sketch.sketchToModelSpace(entity.areaProperties().centroid))
        axes = _parent_axes(entity)
        normal = axes[2] if axes is not None else None
    elif kind is AttachmentTargetKind.JOINT_ORIGIN:
        center = _xyz(entity.transform.translation)
        normal = _direction(entity.primaryAxisVector)
    elif kind is AttachmentTargetKind.SKETCH_POINT:
        center = _xyz(entity.worldGeometry)
    else:
        center = _xyz(entity.geometry)
    oriented = kind not in (
        AttachmentTargetKind.SKETCH_POINT,
        AttachmentTargetKind.CONSTRUCTION_POINT,
    )
    if center is None or (oriented and normal is None):
        raise ValueError("The selected target's row center or orientation is unavailable.")
    return RowTarget(
        token.strip(),
        kind,
        geometry_type,
        (center[0], center[1], center[2]),
        None if normal is None else (normal[0], normal[1], normal[2]),
    )


def _candidates(scope: _Scope, kind: AttachmentTargetKind) -> Iterator[Any]:
    """
    Enumerate the same target kind across bodies in this one occurrence or sketch.
    """
    if kind in (AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE):
        for body in _collection_items(scope.owner.bRepBodies):
            proxy = _in_context(body, scope.occurrence)
            if proxy is None or not getattr(proxy, "isVisible", True):
                continue
            collection = proxy.faces if kind is AttachmentTargetKind.FACE else proxy.edges
            yield from _collection_items(collection)
    else:
        collection_name = {
            AttachmentTargetKind.PROFILE: "profiles",
            AttachmentTargetKind.SKETCH_POINT: "sketchPoints",
            AttachmentTargetKind.CONSTRUCTION_POINT: "constructionPoints",
            AttachmentTargetKind.JOINT_ORIGIN: "jointOrigins",
        }[kind]
        for entity in _collection_items(getattr(scope.owner, collection_name)):
            proxy = _in_context(entity, scope.occurrence)
            if proxy is not None:
                yield proxy


def validate_row_endpoints(first: Any, last: Any) -> tuple[RowTarget, RowTarget]:
    """
    Validate endpoint compatibility without scanning the rest of the component.
    """
    start, end = describe_row_target(first), describe_row_target(last)
    if _scope(first).key != _scope(last).key:
        raise ValueError("Pick row endpoints in the same sketch or component occurrence.")
    select_contact_row(start, end, ())
    return start, end


def _near_segment_bounds(entity: Any, start: Sequence[float], end: Sequence[float]) -> bool:
    """
    Reject faces outside the segment's padded bounds before expensive center queries.
    """
    bounds = getattr(entity, "boundingBox", None)
    if bounds is None:
        return True
    lower, upper = _xyz(bounds.minPoint), _xyz(bounds.maxPoint)
    if lower is None or upper is None:
        return True
    return all(
        upper[axis] >= min(start[axis], end[axis]) - ROW_TOLERANCE_MM
        and lower[axis] <= max(start[axis], end[axis]) + ROW_TOLERANCE_MM
        for axis in range(3)
    )


def collect_contact_row(first: Any, last: Any) -> tuple[RowTarget, ...]:
    """
    Collect the finite row in endpoint order, skipping unavailable neighboring geometry.
    """
    start, end = validate_row_endpoints(first, last)
    scope = _scope(first)
    candidates = []
    for entity in _candidates(scope, start.kind):
        try:
            if start.kind is AttachmentTargetKind.FACE and (
                entity.geometry.objectType != start.geometry_type
                or not _near_segment_bounds(entity, start.center_mm, end.center_mm)
            ):
                continue
            candidate = describe_row_target(entity)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        candidates.append(candidate)
    return select_contact_row(start, end, candidates)
