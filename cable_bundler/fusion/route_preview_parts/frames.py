"""
Resolve Fusion entities into routing profile and control frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Union, cast
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    Connection,
    ControlKind,
    ControlStructure,
)
from ...routing import GateFrame, RefineFrame, TransitionLengths, Vector3
from ...routing.conditioning import CircularGuideConstraint, condition_connection_points
from ...routing.geometry import cross, difference, dot, unit
from ..attachment_targets import resolve_attachment_target


@dataclass(frozen=True)
class ProfileFrame:
    """
    Describe one end guide and any circular interior available to its route.
    """

    origin: Vector3
    normal: Vector3
    u_direction: Vector3
    v_direction: Vector3
    usable_radius_mm: Optional[float] = None


def connection_branch_route_frames(
    design: adsk.fusion.Design,
    connection: Connection,
    attachment: CableEndAttachment,
    guide: ProfileFrame,
    index: int,
    count: int,
    parent_diameter_mm: float,
    branch_diameter_mm: float,
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    cache: dict[str, ProfileFrame],
    *,
    parent_side_point: Optional[Vector3] = None,
) -> tuple[ProfileFrame, ...]:
    """
    Resolve one external branch from its target through owned refines to its guide origin.
    """
    target = connection_attachment_frame(design, connection, attachment, guide, cache)
    if target is None:
        return ()
    refine_frames = _attachment_refine_frames(design, attachment, controls, frames)
    origin = _clockface_branch_origin(
        guide,
        index,
        count,
        parent_diameter_mm,
        branch_diameter_mm,
    )
    origin_normal = _profile_normal_toward_point(guide, origin, parent_side_point)
    origin_frame = ProfileFrame(
        origin,
        origin_normal,
        guide.u_direction,
        guide.v_direction,
    )
    return target, *refine_frames, origin_frame


def _profile_normal_toward_point(
    profile: ProfileFrame,
    origin: Vector3,
    parent_side_point: Optional[Vector3],
) -> Vector3:
    """
    Orient a descendant terminal tangent toward its parent's routed side.
    """
    if parent_side_point is None:
        return profile.normal
    normal = unit(profile.normal)
    parent_projection = dot(difference(parent_side_point, origin), normal)
    return normal if parent_projection >= 0.0 else Vector3(-normal.x, -normal.y, -normal.z)


def connection_attachment_route_side_point(
    design: adsk.fusion.Design,
    attachment: CableEndAttachment,
    attachment_frame: ProfileFrame,
    adjacent_frame: ProfileFrame,
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
) -> Optional[Vector3]:
    """
    Resolve the nearest routed point that establishes which side leaves a profile.
    """
    route_frames = (
        *_attachment_refine_frames(design, attachment, controls, frames),
        adjacent_frame,
    )
    normal = unit(attachment_frame.normal)
    return next(
        (
            frame.origin
            for frame in route_frames
            if abs(dot(difference(frame.origin, attachment_frame.origin), normal)) > 1e-9
        ),
        None,
    )


def _attachment_refine_frames(
    design: adsk.fusion.Design,
    attachment: CableEndAttachment,
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
) -> tuple[ProfileFrame, ...]:
    """
    Resolve the ordered routing-control frames owned by one attachment.
    """
    resolved: list[ProfileFrame] = []
    for control_id in attachment.ordered_control_ids:
        frame = frames.get(control_id)
        if frame is None:
            frame = routing_frame(design, controls.get(control_id), control_id)
            frames[control_id] = frame
        resolved.append(_routing_profile_frame(frame))
    return tuple(resolved)


def _routing_profile_frame(frame: Union[GateFrame, RefineFrame]) -> ProfileFrame:
    """
    Project a saved routing control into the common profile-frame contract.
    """
    return ProfileFrame(
        frame.origin,
        unit(cross(frame.u_direction, frame.v_direction)),
        frame.u_direction,
        frame.v_direction,
        frame.usable_radius_mm if isinstance(frame, GateFrame) else None,
    )


def _clockface_branch_origin(
    guide: ProfileFrame,
    index: int,
    count: int,
    parent_diameter_mm: float,
    branch_diameter_mm: float,
) -> Vector3:
    """
    Place one branch center on an even clock face inside the parent envelope.
    """
    radius_mm = max(0.0, (parent_diameter_mm - branch_diameter_mm) * 0.5)
    angle = math.pi * 0.5 - math.tau * index / count
    return guide.origin.translated(guide.u_direction, math.cos(angle) * radius_mm).translated(
        guide.v_direction, math.sin(angle) * radius_mm
    )


def connection_profile_frames(
    design: adsk.fusion.Design,
    connection: Connection,
    cache: dict[str, ProfileFrame],
) -> tuple[ProfileFrame, ...]:
    """
    Resolve and cache every ordered profile frame owned by one connection.
    """
    member_tokens = connection.member_tokens
    for token in member_tokens:
        if token not in cache:
            cache[token] = _profile_frame(design, token)
    return tuple(cache[token] for token in member_tokens)


def connection_route_frames(
    design: adsk.fusion.Design,
    connection: Connection,
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    cache: dict[str, ProfileFrame],
) -> tuple[ProfileFrame, ...]:
    """
    Prepend one resolved external attachment to the end's native guide frames.
    """
    member_frames = connection_profile_frames(design, connection, cache)
    root_attachments = connection.attachment_children(None)
    attachment = root_attachments[0] if len(root_attachments) == 1 else None
    attachment_frame = (
        connection_attachment_frame(
            design,
            connection,
            attachment,
            member_frames[0],
            cache,
        )
        if attachment is not None
        else None
    )
    if attachment_frame is None or attachment is None:
        return member_frames
    refine_frames = tuple(
        _routing_profile_frame(frames[control_id]) for control_id in attachment.ordered_control_ids
    )
    return attachment_frame, *refine_frames, *member_frames


def connection_attachment_parent_frame(
    design: adsk.fusion.Design,
    connection: Connection,
    attachment: CableEndAttachment,
    end_guide: ProfileFrame,
    cache: dict[str, ProfileFrame],
) -> Optional[ProfileFrame]:
    """
    Resolve the immediate parent profile for one connection node.
    """
    parent_id = attachment.parent_attachment_id
    if parent_id is None:
        return end_guide
    parent = next(
        (item for item in connection.attachments if item.attachment_id == parent_id),
        None,
    )
    if parent is None:
        return None
    adjacent = connection_attachment_parent_frame(design, connection, parent, end_guide, cache)
    if adjacent is None:
        return None
    return connection_attachment_frame(design, connection, parent, adjacent, cache)


def connection_attachment_frame(
    design: adsk.fusion.Design,
    connection: Connection,
    attachment: CableEndAttachment,
    adjacent_frame: ProfileFrame,
    cache: dict[str, ProfileFrame],
) -> Optional[ProfileFrame]:
    """
    Resolve and cache the external contact frame for one attached cable end.
    """
    key = f"attachment:{connection.connection_id}:{attachment.attachment_id}"
    if key not in cache:
        frame = _attachment_frame(design, attachment, adjacent_frame)
        if frame is None:
            return None
        cache[key] = frame
    return cache[key]


def _basis_from_normal(normal: Vector3) -> tuple[Vector3, Vector3]:
    """
    Build one stable orthonormal in-plane basis for a target normal.
    """
    normalized = unit(normal)
    seed = Vector3(1.0, 0.0, 0.0) if abs(normalized.x) < 0.9 else Vector3(0.0, 1.0, 0.0)
    u_direction = unit(cross(seed, normalized))
    return u_direction, unit(cross(normalized, u_direction))


def _attachment_frame(
    design: adsk.fusion.Design,
    attachment: CableEndAttachment,
    adjacent_frame: ProfileFrame,
) -> Optional[ProfileFrame]:
    """
    Convert one supported live Fusion target into a route contact frame.
    """
    entity = resolve_attachment_target(design, attachment)
    if entity is None:
        return None
    resolved_entity = cast(Any, entity)
    if attachment.target_kind is AttachmentTargetKind.PROFILE:
        frame = _profile_frame(design, attachment.entity_token)
        return ProfileFrame(
            frame.origin,
            frame.normal,
            frame.u_direction,
            frame.v_direction,
        )
    if attachment.target_kind is AttachmentTargetKind.FACE:
        parameter = adsk.core.Point2D.create(*attachment.parameters)
        point_result = resolved_entity.evaluator.getPointAtParameter(parameter)
        normal_result = resolved_entity.evaluator.getNormalAtParameter(parameter)
        if not point_result[0] or not normal_result[0]:
            return None
        normal = _vector(normal_result[1])
        u_direction, v_direction = _basis_from_normal(normal)
        return ProfileFrame(_point_to_mm(point_result[1]), unit(normal), u_direction, v_direction)
    if attachment.target_kind is AttachmentTargetKind.JOINT_ORIGIN:
        transform = resolved_entity.transform
        return ProfileFrame(
            _point_to_mm(transform.translation),
            _vector(resolved_entity.primaryAxisVector),
            _vector(resolved_entity.secondaryAxisVector),
            _vector(resolved_entity.thirdAxisVector),
        )
    if attachment.target_kind is AttachmentTargetKind.CIRCULAR_EDGE:
        geometry = resolved_entity.geometry
        normal = _vector(geometry.normal)
        u_direction, v_direction = _basis_from_normal(normal)
        return ProfileFrame(_point_to_mm(geometry.center), unit(normal), u_direction, v_direction)
    if attachment.target_kind is AttachmentTargetKind.SKETCH_POINT:
        sketch = resolved_entity.parentSketch
        u_direction = _vector(sketch.xDirection)
        v_direction = _vector(sketch.yDirection)
        return ProfileFrame(
            _point_to_mm(resolved_entity.worldGeometry),
            unit(cross(u_direction, v_direction)),
            u_direction,
            v_direction,
        )
    return ProfileFrame(
        _point_to_mm(resolved_entity.geometry),
        adjacent_frame.normal,
        adjacent_frame.u_direction,
        adjacent_frame.v_direction,
    )


def connection_profile_points(
    frames: tuple[ProfileFrame, ...],
    pathway_target: Vector3,
    diameter_mm: float,
    transitions: tuple[TransitionLengths, ...],
    auto_transition_fraction: float,
) -> list[Vector3]:
    """
    Use bounded, transition-scaled guide conditioning to approach the pathway.

    Frames are stored terminal-to-pathway, so placement propagates backward
    from the known pathway crossing while preserving the authored guide order.
    """
    constraints = tuple(
        CircularGuideConstraint(
            frame.origin,
            frame.normal,
            frame.u_direction,
            frame.v_direction,
            frame.usable_radius_mm,
        )
        for frame in frames
    )
    return list(
        condition_connection_points(
            constraints,
            pathway_target,
            diameter_mm,
            transitions,
            auto_transition_fraction,
        )
    )


def routing_frame(
    design: adsk.fusion.Design,
    control: Optional[ControlStructure],
    control_id: UUID,
) -> Union[GateFrame, RefineFrame]:
    """
    Build a constrained gate or unconstrained refine routing frame.
    """
    if control is None:
        raise RuntimeError(f"Routing control is missing: {control_id}")
    if control.kind is ControlKind.REFINE:
        geometry = control.refine_geometry
        if geometry is None:
            raise RuntimeError(f"{control.name} has no saved refine geometry.")
        return RefineFrame(
            refine_id=control.control_id,
            name=control.name,
            origin=Vector3(*geometry.origin_mm),
            u_direction=Vector3(*geometry.u_direction),
            v_direction=Vector3(*geometry.v_direction),
        )
    return _gate_frame(design, control, control_id)


def _gate_frame(
    design: adsk.fusion.Design,
    control: Optional[ControlStructure],
    control_id: UUID,
) -> GateFrame:
    """
    Build a millimeter-scale circular aperture frame from one physical control.

    Connection-owned end profiles are resolved separately as centroid/normal
    frames. Their position and orientation guide fairing and the resulting sweep,
    but they are not apertures against which the cable bundle is fit-tested.
    """
    if control is None:
        raise RuntimeError(f"Routing control is missing: {control_id}")
    if control.kind is not ControlKind.ROUTING_GATE:
        raise RuntimeError(
            f"{control.name} is not a routing gate; profile-gate preview is not supported yet."
        )
    profile = _resolve_profile(design, control.entity_token)
    profile_loops = profile.profileLoops
    if profile_loops.count != 1:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    profile_curves = profile_loops.item(0).profileCurves
    if profile_curves.count != 1:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    profile_curve = profile_curves.item(0)
    circle = adsk.fusion.SketchCircle.cast(
        profile_curve.sketchEntity if profile_curve is not None else None
    )
    if circle is None:
        raise RuntimeError(f"{control.name} must be one circular profile.")
    sketch = profile.parentSketch
    center = sketch.sketchToModelSpace(circle.geometry.center)
    return GateFrame(
        gate_id=control.control_id,
        name=control.name,
        origin=_point_to_mm(center),
        u_direction=_vector(sketch.xDirection),
        v_direction=_vector(sketch.yDirection),
        usable_radius_mm=circle.geometry.radius * 10.0,
    )


def _profile_frame(design: adsk.fusion.Design, entity_token: str) -> ProfileFrame:
    """
    Return a millimeter-scale model centroid and dimensionless unit plane normal.
    """
    profile = _resolve_profile(design, entity_token)
    area_properties = profile.areaProperties()
    if area_properties is None:
        raise RuntimeError("Fusion could not calculate connection-profile area properties.")
    sketch = profile.parentSketch
    u_direction = _vector(sketch.xDirection)
    v_direction = _vector(sketch.yDirection)
    normal = unit(cross(u_direction, v_direction))
    usable_radius_mm: Optional[float] = None
    origin = sketch.sketchToModelSpace(area_properties.centroid)
    loops = profile.profileLoops
    if loops.count == 1:
        curves = loops.item(0).profileCurves
        if curves.count == 1:
            profile_curve = curves.item(0)
            circle = adsk.fusion.SketchCircle.cast(
                profile_curve.sketchEntity if profile_curve is not None else None
            )
            if circle is not None:
                origin = sketch.sketchToModelSpace(circle.geometry.center)
                usable_radius_mm = circle.geometry.radius * 10.0
    return ProfileFrame(
        _point_to_mm(origin),
        normal,
        u_direction,
        v_direction,
        usable_radius_mm,
    )


def _resolve_profile(design: adsk.fusion.Design, entity_token: str) -> adsk.fusion.Profile:
    """
    Resolve one stored token to a valid Fusion sketch profile.

    Fusion can return multiple entities for a persistent token after modeling
    operations split or remap its geometry. Invalid historical candidates must
    not hide a later live profile in that result.
    """
    for entity in design.findEntityByToken(entity_token) or ():
        profile = adsk.fusion.Profile.cast(entity)
        if profile is None:
            continue
        try:
            if profile.isValid:
                return profile
        except (AttributeError, RuntimeError):
            continue
    raise RuntimeError("A route profile is missing or no longer resolves in Fusion.")


def _point_to_mm(point: adsk.core.Point3D) -> Vector3:
    """
    Convert a Fusion point from centimeters to millimeters.
    """
    return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)


def _vector(vector: adsk.core.Vector3D) -> Vector3:
    """
    Copy a Fusion model-space direction into the routing model.
    """
    return Vector3(vector.x, vector.y, vector.z)
