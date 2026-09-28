"""
Discover connection-compatible row targets in one Fusion ownership context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Sequence

from ..application.interface_contact_rows import ROW_TOLERANCE_MM, RowTarget, select_contact_row
from ..domain import AttachmentTargetKind
from .attachment_targets import attachment_target_kind, face_contact_center
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
    Identify a target's owning sketch or component occurrence.
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
    Use the shared face-contact anchor for row selection and routed cables.
    """
    return _xyz(face_contact_center(face, face.centroid))


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


def _candidates(
    scope: _Scope,
    kind: AttachmentTargetKind,
    bounds: tuple[Sequence[float], Sequence[float]] | None = None,
) -> Iterator[Any]:
    """
    Enumerate the same target kind across bodies in this one occurrence or sketch.
    """
    if kind in (AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE):
        for body in _collection_items(scope.owner.bRepBodies):
            proxy = _in_context(body, scope.occurrence)
            if proxy is None or not getattr(proxy, "isVisible", True):
                continue
            if bounds is not None and not _near_segment_bounds(proxy, *bounds):
                continue
            collection = proxy.faces if kind is AttachmentTargetKind.FACE else proxy.edges
            for index in range(collection.count):
                yield collection.item(index)
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


def _component_scopes(
    component: Any,
    occurrence: Any,
    kind: AttachmentTargetKind,
) -> Iterator[_Scope]:
    """
    Yield the component or its sketches in one assembly context.
    """
    owners = (
        _collection_items(getattr(component, "sketches", None))
        if kind in (AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT)
        else (component,)
    )
    path = getattr(occurrence, "fullPathName", "")
    for owner in owners:
        if getattr(owner, "isVisible", True):
            yield _Scope(owner, occurrence, (owner.entityToken, path))


def _candidate_scopes(
    first: Any,
    last: Any,
    kind: AttachmentTargetKind,
    design: Any = None,
) -> Iterator[_Scope]:
    """
    Search one owner locally or the shared assembly branch across owners.

    Cross-assembly searches need the active design so every candidate can be
    expressed in its own occurrence's assembly context.
    """
    start_scope, end_scope = _scope(first), _scope(last)
    if design is None:
        if start_scope.key != end_scope.key:
            raise ValueError("An active design is required to select across subassemblies.")
        yield start_scope
        return
    root = getattr(design, "rootComponent", None)
    if root is None:
        raise ValueError("The active design has no assembly root.")
    start_path = start_scope.key[1].split("+") if start_scope.key[1] else []
    end_path = end_scope.key[1].split("+") if end_scope.key[1] else []
    common: list[str] = []
    for start_name, end_name in zip(start_path, end_path):
        if start_name != end_name:
            break
        common.append(start_name)
    common_path = "+".join(common)
    if not common_path:
        yield from _component_scopes(root, None, kind)
    occurrences = getattr(root, "allOccurrences", None)
    if occurrences is None:
        raise ValueError("The assembly occurrences are unavailable.")
    for occurrence in _collection_items(occurrences):
        path = getattr(occurrence, "fullPathName", "")
        if common_path and path != common_path and not path.startswith(f"{common_path}+"):
            continue
        if not getattr(occurrence, "isVisible", True):
            continue
        component = getattr(occurrence, "component", None)
        if component is None:
            continue
        yield from _component_scopes(component, occurrence, kind)


def validate_row_endpoints(first: Any, last: Any) -> tuple[RowTarget, RowTarget]:
    """
    Validate endpoint compatibility in their shared assembly frame.
    """
    start, end = describe_row_target(first), describe_row_target(last)
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


def collect_contact_row(
    first: Any,
    last: Any,
    *,
    on_selected: Callable[[Any], None] | None = None,
    design: Any = None,
) -> tuple[RowTarget, ...]:
    """
    Collect the finite row across the shared assembly branch in endpoint order.

    Unavailable neighboring geometry is skipped; endpoint errors remain explicit.
    """
    start, end = validate_row_endpoints(first, last)
    candidates = []
    entities = {id(start): first, id(end): last}
    for scope in _candidate_scopes(first, last, start.kind, design):
        for entity in _candidates(scope, start.kind, (start.center_mm, end.center_mm)):
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
            if on_selected is not None:
                entities[id(candidate)] = entity
    selected = select_contact_row(start, end, candidates)
    if on_selected is not None:
        for target in selected:
            on_selected(entities[id(target)])
    return selected
