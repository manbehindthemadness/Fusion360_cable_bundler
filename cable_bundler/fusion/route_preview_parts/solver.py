"""Resolve Fusion route inputs into deterministic centerline solutions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID, uuid5

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg, plan_cable_group_routes
from ...domain import (
    Connection,
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
    condition_control_points,
    condition_route_normals,
    junction_normal_indices,
)
from ...routing.geometry import cross, unit
from .frames import (
    ProfileFrame,
    connection_attachment_frame,
    connection_attachment_parent_frame,
    connection_branch_route_frames,
    connection_profile_frames,
    connection_route_frames,
    routing_frame,
)
from .frames import connection_profile_points as _connection_profile_points


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


# noinspection DuplicatedCode
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
            member_frames = connection_profile_frames(design, connection, profile_frames)
            for attachment in connection.attachments:
                parent_frame = connection_attachment_parent_frame(
                    design,
                    connection,
                    attachment,
                    member_frames[0],
                    profile_frames,
                )
                if parent_frame is None:
                    continue
                for control_id in attachment.ordered_control_ids:
                    if control_id not in frames:
                        frames[control_id] = routing_frame(
                            design,
                            controls.get(control_id),
                            control_id,
                        )
                connection_attachment_frame(
                    design,
                    connection,
                    attachment,
                    parent_frame,
                    profile_frames,
                )
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
            connection_frames = connection_route_frames(
                design,
                connection,
                frames,
                profile_frames,
            )
            has_attachment_frame = len(connection_frames) > len(connection.member_tokens)
            root_attachments = connection.attachment_children(None)
            attachment_control_ids = (
                root_attachments[0].ordered_control_ids if has_attachment_frame else ()
            )
            start_frames = connection_frames
            points.extend(frame.origin for frame in connection_frames)
            normals.extend(frame.normal for frame in connection_frames)
            start_transitions = (
                ((TransitionLengths(None, None),) if has_attachment_frame else ())
                + tuple(
                    TransitionLengths(
                        controls[control_id].interpolation.approach_mm,
                        controls[control_id].interpolation.departure_mm,
                    )
                    for control_id in attachment_control_ids
                )
                + tuple(
                    TransitionLengths(settings.approach_mm, settings.departure_mm)
                    for settings in connection.member_settings
                )
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
            connection_frames = connection_route_frames(
                design,
                connection,
                frames,
                profile_frames,
            )
            has_attachment_frame = len(connection_frames) > len(connection.member_tokens)
            root_attachments = connection.attachment_children(None)
            attachment_control_ids = (
                root_attachments[0].ordered_control_ids if has_attachment_frame else ()
            )
            native_end_transitions = (
                ((TransitionLengths(None, None),) if has_attachment_frame else ())
                + tuple(
                    TransitionLengths(
                        controls[control_id].interpolation.approach_mm,
                        controls[control_id].interpolation.departure_mm,
                    )
                    for control_id in attachment_control_ids
                )
                + tuple(
                    TransitionLengths(settings.approach_mm, settings.departure_mm)
                    for settings in connection.member_settings
                )
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
            reversed_member_transitions = tuple(
                TransitionLengths(settings.departure_mm, settings.approach_mm)
                for settings in reversed(connection.member_settings)
            )
            reversed_attachment_transitions = tuple(
                TransitionLengths(
                    controls[control_id].interpolation.departure_mm,
                    controls[control_id].interpolation.approach_mm,
                )
                for control_id in reversed(attachment_control_ids)
            )
            transitions.extend(
                reversed_member_transitions
                + reversed_attachment_transitions
                + ((TransitionLengths(None, None),) if has_attachment_frame else ())
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
    branch_routes, branch_legs = _connection_branch_routes(
        design,
        definition,
        connections,
        controls,
        frames,
        profile_frames,
        auto_transition_fraction,
    )
    solved_routes = (*separated_routes, *branch_routes)
    solved_legs = (*legs, *branch_legs)
    _route_solve_cache = _RouteSolveCache(
        design,
        definition,
        control_frame_snapshot,
        profile_frame_snapshot,
        solved_routes,
        solved_legs,
        tuple(solve_notices),
    )
    if notices is not None:
        notices.extend(solve_notices)
    return solved_routes, solved_legs


def _connection_branch_routes(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    connections: dict[UUID, Connection],
    controls: dict[UUID, ControlStructure],
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    cache: dict[str, ProfileFrame],
    auto_transition_fraction: float,
) -> tuple[tuple[RoutePreview, ...], tuple[CableGroupRouteLeg, ...]]:
    """
    Build every root split and descendant connection span.
    """
    routes: list[RoutePreview] = []
    legs: list[CableGroupRouteLeg] = []
    for group in definition.cable_groups:
        for connection_id in group.connection_ids:
            connection = connections.get(connection_id)
            if connection is None:
                continue
            end_guide = connection_profile_frames(design, connection, cache)[0]
            parent_ids = tuple(
                dict.fromkeys(item.parent_attachment_id for item in connection.attachments)
            )
            for parent_attachment_id in parent_ids:
                siblings = connection.attachment_children(parent_attachment_id)
                if parent_attachment_id is None:
                    guide = end_guide
                    parent_diameter_mm = group.diameter_mm
                    if len(siblings) <= 1:
                        continue
                else:
                    parent = next(
                        item
                        for item in connection.attachments
                        if item.attachment_id == parent_attachment_id
                    )
                    parent_adjacent = connection_attachment_parent_frame(
                        design, connection, parent, end_guide, cache
                    )
                    if parent_adjacent is None:
                        continue
                    parent_frame = connection_attachment_frame(
                        design, connection, parent, parent_adjacent, cache
                    )
                    if parent_frame is None:
                        continue
                    guide = parent_frame
                    parent_diameter_mm = definition.cable_end_attachment_diameter(
                        group, connection_id, parent_attachment_id
                    )
                for index, attachment in enumerate(siblings):
                    branch_diameter_mm = definition.cable_end_attachment_diameter(
                        group, connection_id, attachment.attachment_id
                    )
                    branch_frames = connection_branch_route_frames(
                        design,
                        connection,
                        attachment,
                        guide,
                        index,
                        len(siblings),
                        parent_diameter_mm,
                        branch_diameter_mm,
                        controls,
                        frames,
                        cache,
                    )
                    if not branch_frames:
                        continue
                    route_id = uuid5(
                        attachment.attachment_id,
                        f"{group.cable_group_id}:{connection_id}:connection-branch",
                    )
                    label = f"{group.name or 'Cable group'} · {attachment.display_name}"
                    raw_route = RoutePreview(
                        route_id,
                        label,
                        tuple(frame.origin for frame in branch_frames),
                    )
                    transitions = (
                        TransitionLengths(None, None),
                        *(
                            TransitionLengths(
                                controls[control_id].interpolation.approach_mm,
                                controls[control_id].interpolation.departure_mm,
                            )
                            for control_id in attachment.ordered_control_ids
                        ),
                        TransitionLengths(None, None),
                    )
                    route = fair_route(
                        raw_route,
                        tuple(frame.normal for frame in branch_frames),
                        transitions,
                        minimum_bend_radius_mm=minimum_circular_bend_radius(branch_diameter_mm),
                        auto_transition_fraction=auto_transition_fraction,
                    )
                    routes.append(route)
                    legs.append(
                        CableGroupRouteLeg(
                            route_id,
                            group.cable_group_id,
                            label,
                            connection_id,
                            None,
                            (),
                            (),
                            diameter_mm=branch_diameter_mm,
                            is_connection_branch=True,
                            attachment_id=attachment.attachment_id,
                        )
                    )
    return tuple(routes), tuple(legs)


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


def reset_route_solve_cache() -> None:
    """
    Release the session-only geometry solution cache.
    """
    global _route_solve_cache

    _route_solve_cache = None
