"""Resolve Fusion route inputs into deterministic centerline solutions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg, plan_cable_group_routes
from ...domain import (
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
)
from ...routing import (
    CableRouteInput,
    GateCapacityError,
    GateCapacityPolicy,
    GateFrame,
    RefineFrame,
    RouteCollision,
    RoutePreview,
    TransitionAdjustment,
    TransitionLengths,
    Vector3,
    fair_route,
    minimum_circular_bend_radius,
    place_route_crossings,
    separate_route_collisions,
)
from ...routing.conditioning import (
    CircularGuideConstraint,
    condition_connection_points,
    condition_control_points,
    condition_route_normals,
    junction_normal_indices,
)
from ...routing.geometry import cross, unit


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


@dataclass(frozen=True)
class _RouteSolveCache:
    """
    Retain one geometry-validated route solution for immediate reuse.
    """

    design: adsk.fusion.Design
    definition: HarnessDefinition
    control_frames: tuple[tuple[UUID, Union[GateFrame, RefineFrame]], ...]
    profile_frames: tuple[tuple[str, ProfileFrame], ...]
    routes: tuple[RoutePreview, ...]
    legs: tuple[CableGroupRouteLeg, ...]
    notices: tuple[str, ...]


_route_solve_cache: Optional[_RouteSolveCache] = None


def leg_control_ids(
    leg: CableGroupRouteLeg,
    end_control_ids: dict[UUID, tuple[UUID, ...]],
) -> tuple[UUID, ...]:
    """
    Return end-owned and pathway controls in one leg's traversal order.
    """
    return (
        *(
            end_control_ids.get(leg.start_connection_id, ())
            if leg.start_connection_id is not None
            else ()
        ),
        *(step.control_id for step in leg.control_steps),
        *(
            reversed(end_control_ids.get(leg.end_connection_id, ()))
            if leg.end_connection_id is not None
            else ()
        ),
    )


def _place_control_crossings(
    cables: tuple[CableRouteInput, ...],
    frame: Union[GateFrame, RefineFrame],
    clearance_mm: float,
    preferred_points: tuple[Optional[Vector3], ...],
    notices: list[str],
) -> tuple[Vector3, ...]:
    """
    Preserve deterministic spacing and warn when it exceeds a gate aperture.
    """
    try:
        return place_route_crossings(cables, frame, clearance_mm, preferred_points)
    except GateCapacityError as error:
        notices.append(
            f"{error} Cable spacing is preserved, so routes may extend outside the aperture."
        )
        return place_route_crossings(
            cables,
            frame,
            clearance_mm,
            preferred_points,
            capacity_policy=GateCapacityPolicy.ALLOW_OVERFLOW,
        )


def _append_route_control(
    leg_label: str,
    cable_group_id: UUID,
    control_id: UUID,
    reversed_direction: bool,
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    crossings: dict[tuple[UUID, UUID], Vector3],
    points: list[Vector3],
    normals: list[Vector3],
    transitions: list[TransitionLengths],
    point_control_ids: list[Optional[UUID]],
    soft_guide_indices: set[int],
) -> None:
    """
    Append one shared or end-owned routing control in traversal order.
    """
    control = controls.get(control_id)
    if control is None:
        raise RuntimeError(f"{leg_label} references a missing routing control.")
    frame = frames[control_id]
    control_point_index = len(points)
    points.append(crossings[control_id, cable_group_id])
    normals.append(cross(frame.u_direction, frame.v_direction))
    point_control_ids.append(control_id)
    soft_guide_indices.add(control_point_index)
    settings = control.interpolation
    transitions.append(
        TransitionLengths(
            settings.departure_mm if reversed_direction else settings.approach_mm,
            settings.approach_mm if reversed_direction else settings.departure_mm,
        )
    )


def solve_cable_group_routes(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    notices: Optional[list[str]] = None,
) -> tuple[tuple[RoutePreview, ...], tuple[CableGroupRouteLeg, ...]]:
    """
    Solve every cable group as one topology tree with shared hub crossings.

    One group occupies one slot at each control regardless of how many legs
    meet there, preventing duplicated paths and split junction crossings.
    """
    global _route_solve_cache

    if not definition.cable_groups:
        raise ValueError("Create at least one cable group before previewing routes.")
    legs = plan_cable_group_routes(definition)
    groups_by_id = {group.cable_group_id: group for group in definition.cable_groups}
    controls = {control.control_id: control for control in definition.controls}
    connections = {connection.connection_id: connection for connection in definition.connections}
    end_control_ids = {
        end.connection_id: end.ordered_control_ids for end in definition.standalone_ends
    }
    frames: dict[UUID, Union[GateFrame, RefineFrame]] = {}
    group_order = {
        group.cable_group_id: index for index, group in enumerate(definition.cable_groups)
    }
    control_groups: dict[UUID, list[UUID]] = defaultdict(list)
    for leg in legs:
        route_leg_control_ids = leg_control_ids(leg, end_control_ids)
        for control_id in route_leg_control_ids:
            if control_id not in frames:
                frames[control_id] = routing_frame(design, controls.get(control_id), control_id)
            if leg.cable_group_id not in control_groups[control_id]:
                control_groups[control_id].append(leg.cable_group_id)
    profile_frames: dict[str, ProfileFrame] = {}
    for leg in legs:
        for connection_id, position in (
            (leg.start_connection_id, "start"),
            (leg.end_connection_id, "end"),
        ):
            if connection_id is None:
                continue
            connection = connections.get(connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing {position} connection.")
            connection_profile_frames(design, connection, profile_frames)
    control_frame_snapshot = tuple(sorted(frames.items(), key=lambda item: str(item[0])))
    profile_frame_snapshot = tuple(sorted(profile_frames.items()))
    cached = _route_solve_cache
    if (
        cached is not None
        and cached.design is design
        and cached.definition == definition
        and cached.control_frames == control_frame_snapshot
        and cached.profile_frames == profile_frame_snapshot
    ):
        if notices is not None:
            notices.extend(cached.notices)
        return cached.routes, cached.legs
    crossings: dict[tuple[UUID, UUID], Vector3] = {}
    prior_crossings: dict[UUID, Vector3] = {}
    solve_notices: list[str] = []
    origin = Vector3(0.0, 0.0, 0.0)
    for control_id, group_ids in control_groups.items():
        ordered_group_ids = sorted(group_ids, key=group_order.__getitem__)
        placement_inputs = tuple(
            CableRouteInput(
                cable_id=group_id,
                cable_number=f"Group {group_order[group_id] + 1}",
                start=origin,
                end=origin,
                diameter_mm=groups_by_id[group_id].diameter_mm,
            )
            for group_id in ordered_group_ids
        )
        points = _place_control_crossings(
            placement_inputs,
            frames[control_id],
            definition.minimum_clearance_mm,
            tuple(prior_crossings.get(group_id) for group_id in ordered_group_ids),
            solve_notices,
        )
        crossings.update(
            ((control_id, group_id), point) for group_id, point in zip(ordered_group_ids, points)
        )
        prior_crossings.update(zip(ordered_group_ids, points))

    raw_routes: list[RoutePreview] = []
    route_group_ids: list[UUID] = []
    route_diameters: list[float] = []
    raw_route_normals: list[tuple[Vector3, ...]] = []
    route_transitions: list[tuple[TransitionLengths, ...]] = []
    route_control_ids: list[tuple[Optional[UUID], ...]] = []
    route_soft_guide_indices: list[frozenset[int]] = []
    minimum_bend_radii: list[float] = []
    auto_transition_fraction = definition.auto_transition_preset.span_fraction
    for leg in legs:
        diameter_mm = groups_by_id[leg.cable_group_id].diameter_mm
        points: list[Vector3] = []
        normals: list[Vector3] = []
        transitions: list[TransitionLengths] = []
        point_control_ids: list[Optional[UUID]] = []
        soft_guide_indices: set[int] = set()
        start_frames: tuple[ProfileFrame, ...] = ()
        start_transitions: tuple[TransitionLengths, ...] = ()

        if leg.start_connection_id is not None:
            connection = connections.get(leg.start_connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing start connection.")
            connection_frames = connection_profile_frames(design, connection, profile_frames)
            start_frames = connection_frames
            points.extend(frame.origin for frame in connection_frames)
            normals.extend(frame.normal for frame in connection_frames)
            start_transitions = tuple(
                TransitionLengths(settings.approach_mm, settings.departure_mm)
                for settings in connection.member_settings
            )
            transitions.extend(start_transitions)
            point_control_ids.extend((None,) * len(connection_frames))
            soft_guide_indices.update(range(1, len(connection_frames)))
            for control_id in end_control_ids.get(leg.start_connection_id, ()):
                _append_route_control(
                    leg.label,
                    leg.cable_group_id,
                    control_id,
                    False,
                    controls,
                    frames,
                    crossings,
                    points,
                    normals,
                    transitions,
                    point_control_ids,
                    soft_guide_indices,
                )
        for step in leg.control_steps:
            _append_route_control(
                leg.label,
                leg.cable_group_id,
                step.control_id,
                step.reversed,
                controls,
                frames,
                crossings,
                points,
                normals,
                transitions,
                point_control_ids,
                soft_guide_indices,
            )
        if start_frames and len(points) > len(start_frames):
            start_points = _connection_profile_points(
                start_frames,
                points[len(start_frames)],
                diameter_mm,
                start_transitions,
                auto_transition_fraction,
            )
            points[: len(start_frames)] = start_points
        if leg.end_connection_id is not None:
            for control_id in reversed(end_control_ids.get(leg.end_connection_id, ())):
                _append_route_control(
                    leg.label,
                    leg.cable_group_id,
                    control_id,
                    True,
                    controls,
                    frames,
                    crossings,
                    points,
                    normals,
                    transitions,
                    point_control_ids,
                    soft_guide_indices,
                )
            connection = connections.get(leg.end_connection_id)
            if connection is None:
                raise RuntimeError(f"{leg.label} references a missing end connection.")
            connection_frames = connection_profile_frames(design, connection, profile_frames)
            native_end_transitions = tuple(
                TransitionLengths(settings.approach_mm, settings.departure_mm)
                for settings in connection.member_settings
            )
            end_points = _connection_profile_points(
                connection_frames,
                points[-1],
                diameter_mm,
                native_end_transitions,
                auto_transition_fraction,
            )
            end_start_index = len(points)
            points.extend(reversed(end_points))
            normals.extend(frame.normal for frame in reversed(connection_frames))
            point_control_ids.extend((None,) * len(connection_frames))
            soft_guide_indices.update(
                range(end_start_index, end_start_index + max(0, len(connection_frames) - 1))
            )
            transitions.extend(
                TransitionLengths(settings.departure_mm, settings.approach_mm)
                for settings in reversed(connection.member_settings)
            )
        if len(points) < 2:
            raise ValueError(f"{leg.label} does not contain enough route geometry.")
        route = RoutePreview(leg.route_id, leg.label, tuple(points))
        raw_routes.append(route)
        route_group_ids.append(leg.cable_group_id)
        route_diameters.append(diameter_mm)
        raw_route_normals.append(tuple(normals))
        route_transitions.append(tuple(transitions))
        route_control_ids.append(tuple(point_control_ids))
        route_soft_guide_indices.append(frozenset(soft_guide_indices))
        minimum_bend_radii.append(minimum_circular_bend_radius(diameter_mm))

    junction_control_ids = frozenset(junction.control_id for junction in definition.junctions)
    control_constraints = {
        control_id: CircularGuideConstraint(
            frame.origin,
            unit(cross(frame.u_direction, frame.v_direction)),
            frame.u_direction,
            frame.v_direction,
            frame.usable_radius_mm,
        )
        for control_id, frame in frames.items()
        if isinstance(frame, GateFrame)
    }
    conditioned_routes = condition_control_points(
        tuple(raw_routes),
        tuple(route_group_ids),
        tuple(route_diameters),
        tuple(route_control_ids),
        tuple(route_transitions),
        control_constraints,
        auto_transition_fraction,
    )
    raw_routes = list(conditioned_routes)
    fixed_junction_indices = junction_normal_indices(
        conditioned_routes,
        tuple(route_control_ids),
        junction_control_ids,
    )
    routes: list[RoutePreview] = []
    route_normals: list[tuple[Vector3, ...]] = []
    for route_index, route in enumerate(raw_routes):
        original_normals = raw_route_normals[route_index]
        route_transition_lengths = route_transitions[route_index]
        conditioned_normals = condition_route_normals(
            route,
            original_normals,
            route_transition_lengths,
            route_soft_guide_indices[route_index],
            fixed_junction_indices[route_index],
            auto_transition_fraction,
        )
        adjustments: list[TransitionAdjustment] = []
        try:
            faired_route = fair_route(
                route,
                conditioned_normals,
                route_transition_lengths,
                minimum_bend_radius_mm=minimum_bend_radii[route_index],
                adjustments=adjustments,
                auto_transition_fraction=auto_transition_fraction,
            )
            accepted_normals = conditioned_normals
        except ValueError:
            adjustments.clear()
            faired_route = fair_route(
                route,
                original_normals,
                route_transition_lengths,
                minimum_bend_radius_mm=minimum_bend_radii[route_index],
                adjustments=adjustments,
                auto_transition_fraction=auto_transition_fraction,
            )
            accepted_normals = original_normals
            solve_notices.append(
                f"{route.cable_number}: retained the original guide interpolation because "
                "the relaxed guide shape was infeasible."
            )
        routes.append(faired_route)
        route_normals.append(accepted_normals)
        solve_notices.extend(_adjustment_notice(item) for item in adjustments)
    separated_routes, collisions = separate_route_collisions(
        tuple(routes),
        tuple(route_group_ids),
        tuple(route_diameters),
        tuple(route_normals),
        tuple(route_transitions),
        tuple(minimum_bend_radii),
        definition.minimum_clearance_mm,
        auto_transition_fraction=auto_transition_fraction,
    )
    solve_notices.extend(_collision_notice(item) for item in collisions)
    _route_solve_cache = _RouteSolveCache(
        design,
        definition,
        control_frame_snapshot,
        profile_frame_snapshot,
        separated_routes,
        legs,
        tuple(solve_notices),
    )
    if notices is not None:
        notices.extend(solve_notices)
    return separated_routes, legs


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


def _connection_profile_points(
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


def _adjustment_notice(adjustment: TransitionAdjustment) -> str:
    """
    Format a dynamic transition correction for the palette event console.
    """
    return (
        f"Cable {adjustment.cable_number}: dynamically adjusted transitions between profiles "
        f"{adjustment.start_profile} and {adjustment.end_profile} from "
        f"{adjustment.required_mm:.3f} mm to {adjustment.applied_mm:.3f} mm; "
        f"the {adjustment.minimum_bend_radius_mm:.3f} mm sweep radius is preserved."
    )


def _collision_notice(collision: RouteCollision) -> str:
    """
    Format one residual member collision for the event console.
    """
    return (
        f"{collision.left_label} and {collision.right_label} remain "
        f"{collision.clearance_shortfall_mm:.3f} mm inside the requested separation; "
        "the original deterministic route is retained."
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
    Resolve one stored token to a Fusion sketch profile.
    """
    entities = design.findEntityByToken(entity_token)
    profile = adsk.fusion.Profile.cast(entities[0] if entities else None)
    if profile is None:
        raise RuntimeError("A route profile is missing or no longer resolves in Fusion.")
    return profile


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


def reset_route_solve_cache() -> None:
    """
    Release the session-only geometry solution cache.
    """
    global _route_solve_cache

    _route_solve_cache = None
