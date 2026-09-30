"""
Resolve Fusion route inputs into deterministic centerline solutions.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Optional, Union
from uuid import UUID, uuid5

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import CableGroupRouteLeg, plan_cable_group_routes
from ...domain import (
    CableGroupDefinition,
    CableGroupType,
    Connection,
    ControlStructure,
    HarnessDefinition,
    RibbonGeometryType,
)
from ...domain.connection_packing import PackedConnection
from ...routing import (
    CableRouteInput,
    GateFrame,
    RefineFrame,
    RoutePreview,
    TransitionAdjustment,
    TransitionLengths,
    Vector3,
    fair_route,
    minimum_circular_bend_radius,
    separate_route_collisions,
    straight_route,
)
from ...routing.conditioning import (
    CircularGuideConstraint,
    condition_control_points,
    condition_route_normals,
    junction_normal_indices,
)
from ...routing.geometry import cross, difference, dot, unit
from . import branch_layout
from .frames import (
    ProfileFrame,
    connection_attachment_frame,
    connection_attachment_parent_frame,
    connection_attachment_route_side_point,
    connection_branch_route_frames,
    connection_profile_frames,
    connection_route_frames,
    routing_frame,
)
from .frames import connection_profile_points as _connection_profile_points
from .ribbon_branches import ribbon_branch_guides
from .solver_controls import (
    _append_route_control,
    _BranchAnchor,
    _place_control_crossings,
    _root_branch_anchors,
    leg_control_ids,
)
from .solver_notices import (
    _adjustment_below_cable_radius,
    _adjustment_notice,
    _collision_notice,
    _straight_for_sweep_notice,
    _straight_route_notice,
)


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


def _packing_diameter_mm(group: CableGroupDefinition) -> float:
    """
    Conservatively enclose a ribbon's full width and thickness for shared packing.
    """
    if group.group_type is CableGroupType.RIBBON:
        return math.hypot(group.ribbon_lines * group.diameter_mm, group.diameter_mm)
    return group.diameter_mm


def _warn_short_ribbon_guide(
    group: CableGroupDefinition,
    frames: tuple[ProfileFrame, ...],
    label: str,
    notices: list[str],
) -> None:
    """
    Report a guide that cannot contain the selected ribbon width.
    """
    if group.group_type is not CableGroupType.RIBBON:
        return
    width_mm = group.ribbon_lines * group.diameter_mm
    if any(
        frame.guide_length_mm is not None and frame.guide_length_mm < width_mm for frame in frames
    ):
        notices.append(
            f"{label}: open guide is shorter than the ribbon width; "
            "the selected alignment will overhang."
        )


def _main_route_connection_frames(
    design: adsk.fusion.Design,
    group: CableGroupDefinition,
    connection: Connection,
    frames: dict[UUID, Union[GateFrame, RefineFrame]],
    cache: dict[str, ProfileFrame],
) -> tuple[ProfileFrame, ...]:
    """
    Stop ribbon trunks at their guides; route contacts as numbered branches.
    """
    if group.group_type is CableGroupType.RIBBON:
        return connection_profile_frames(design, connection, cache)
    return connection_route_frames(design, connection, frames, cache)


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
    for group in definition.cable_groups:
        if group.group_type is not CableGroupType.RIBBON:
            continue
        if group.ribbon_geometry is RibbonGeometryType.FFC:
            raise ValueError("FFC ribbon route preview and geometry are not implemented yet.")
        if sum(leg.cable_group_id == group.cable_group_id for leg in legs) != 1:
            raise ValueError("Discrete ribbons currently require one continuous two-ended route.")
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
                diameter_mm=_packing_diameter_mm(groups_by_id[group_id]),
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
        group = groups_by_id[leg.cable_group_id]
        diameter_mm = _packing_diameter_mm(group)
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
            connection_frames = _main_route_connection_frames(
                design,
                group,
                connection,
                frames,
                profile_frames,
            )
            _warn_short_ribbon_guide(group, connection_frames, leg.label, solve_notices)
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
            connection_frames = _main_route_connection_frames(
                design,
                group,
                connection,
                frames,
                profile_frames,
            )
            _warn_short_ribbon_guide(group, connection_frames, leg.label, solve_notices)
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
        minimum_bend_radii.append(minimum_circular_bend_radius(group.diameter_mm))

    junction_control_ids = frozenset(junction.control_id for junction in definition.junctions)
    control_constraints = {
        control_id: CircularGuideConstraint(
            frame.origin,
            unit(cross(frame.u_direction, frame.v_direction)),
            frame.u_direction,
            frame.v_direction,
            frame.usable_radius_mm,
            frame.boundary_loops_mm,
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
            try:
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
            except ValueError:
                adjustments.clear()
                try:
                    faired_route = fair_route(
                        route,
                        conditioned_normals,
                        route_transition_lengths,
                        minimum_bend_radius_mm=minimum_bend_radii[route_index],
                        adjustments=adjustments,
                        auto_transition_fraction=auto_transition_fraction,
                        allow_bend_radius_clamp=True,
                    )
                except ValueError as error:
                    adjustments.clear()
                    faired_route = straight_route(route)
                    solve_notices.append(_straight_route_notice(route.cable_number, error))
                accepted_normals = conditioned_normals
        physical_diameter_mm = groups_by_id[route_group_ids[route_index]].diameter_mm
        if (
            unsafe := _adjustment_below_cable_radius(adjustments, physical_diameter_mm / 2.0)
        ) is not None:
            faired_route = straight_route(route)
            adjustments.clear()
            solve_notices.append(
                _straight_for_sweep_notice(route.cable_number, unsafe, physical_diameter_mm)
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
        _root_branch_anchors(legs, separated_routes),
        solve_notices,
        ribbon_guides=ribbon_branch_guides(design, definition, legs, separated_routes),
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
    root_anchors: Optional[dict[tuple[UUID, UUID], _BranchAnchor]] = None,
    notices: Optional[list[str]] = None,
    *,
    ribbon_guides: Optional[dict[tuple[UUID, UUID, UUID], ProfileFrame]] = None,
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
                ribbon_root = (
                    group.group_type is CableGroupType.RIBBON and parent_attachment_id is None
                )
                if parent_attachment_id is None:
                    anchor = (root_anchors or {}).get((group.cable_group_id, connection_id))
                    guide = replace(end_guide, origin=anchor.origin) if anchor else end_guide
                    parent_side_point = anchor.interior if anchor else None
                    if len(siblings) <= 1 and not ribbon_root:
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
                    parent_side_point = connection_attachment_route_side_point(
                        design,
                        parent,
                        parent_frame,
                        parent_adjacent,
                        controls,
                        frames,
                    )
                packing = (
                    tuple(PackedConnection(0.0, 0.0, group.diameter_mm) for _ in siblings)
                    if ribbon_root
                    else definition.cable_end_attachment_pack(
                        group, connection_id, parent_attachment_id
                    )
                )
                if packing is None:
                    continue
                parent_diameter_mm = (
                    group.diameter_mm
                    if parent_attachment_id is None
                    else definition.cable_end_attachment_diameter(
                        group, connection_id, parent_attachment_id
                    )
                )
                initial_branch_frames = tuple(
                    connection_branch_route_frames(
                        design,
                        connection,
                        attachment,
                        (
                            (ribbon_guides or {})[
                                group.cable_group_id,
                                connection_id,
                                attachment.attachment_id,
                            ]
                            if ribbon_root and attachment.has_target
                            else guide
                        ),
                        packing[index].x_mm,
                        packing[index].y_mm,
                        controls,
                        frames,
                        cache,
                        parent_side_point=None if ribbon_root else parent_side_point,
                    )
                    for index, attachment in enumerate(siblings)
                )
                targets = tuple(
                    branch_frames[0] if branch_frames else None
                    for branch_frames in initial_branch_frames
                )
                fan_axis = (
                    None if ribbon_root else branch_layout.connection_fan_axis(guide, targets)
                )
                fan_extent_mm = (
                    max(
                        abs(dot(difference(target.origin, guide.origin), fan_axis))
                        for target in targets
                        if target is not None
                    )
                    if fan_axis is not None
                    else 0.0
                )
                original_packing = packing
                if not ribbon_root:
                    packing = branch_layout.assign_connection_packing(guide, packing, targets)
                if fan_axis is not None:
                    packing = branch_layout.expand_connection_packing(packing, parent_diameter_mm)
                sibling_routes: list[RoutePreview] = []
                sibling_legs: list[CableGroupRouteLeg] = []
                sibling_normals: list[tuple[Vector3, ...]] = []
                sibling_transitions: list[tuple[TransitionLengths, ...]] = []
                sibling_radii: list[float] = []
                sibling_fixed_end_normals: list[bool] = []
                for index, attachment in enumerate(siblings):
                    branch_diameter_mm = packing[index].diameter_mm
                    branch_frames = initial_branch_frames[index]
                    if packing[index] != original_packing[index]:
                        branch_frames = connection_branch_route_frames(
                            design,
                            connection,
                            attachment,
                            guide,
                            packing[index].x_mm,
                            packing[index].y_mm,
                            controls,
                            frames,
                            cache,
                            parent_side_point=None if ribbon_root else parent_side_point,
                        )
                    if not branch_frames:
                        continue
                    if len(siblings) > 1 and not ribbon_root:
                        branch_frames = branch_layout.parallel_branch_lead(
                            branch_frames,
                            guide,
                            parent_side_point,
                            parent_diameter_mm,
                            branch_diameter_mm,
                            fan_axis,
                            fan_extent_mm,
                        )
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
                        *(
                            TransitionLengths(None, None)
                            for _ in range(
                                len(branch_frames) - len(attachment.ordered_control_ids) - 1
                            )
                        ),
                    )
                    branch_normals = tuple(frame.normal for frame in branch_frames)
                    branch_radius = minimum_circular_bend_radius(branch_diameter_mm)
                    fixed_indices = (
                        frozenset({len(branch_frames) - 1})
                        if parent_attachment_id is not None or parent_side_point is not None
                        else frozenset()
                    )
                    adjustments: list[TransitionAdjustment] = []
                    try:
                        route = fair_route(
                            raw_route,
                            branch_normals,
                            transitions,
                            minimum_bend_radius_mm=branch_radius,
                            auto_transition_fraction=auto_transition_fraction,
                            fixed_normal_indices=fixed_indices,
                            adjustments=adjustments,
                        )
                    except ValueError:
                        adjustments.clear()
                        try:
                            route = fair_route(
                                raw_route,
                                branch_normals,
                                transitions,
                                minimum_bend_radius_mm=branch_radius,
                                auto_transition_fraction=auto_transition_fraction,
                                fixed_normal_indices=fixed_indices,
                                allow_bend_radius_clamp=True,
                                adjustments=adjustments,
                            )
                        except ValueError as error:
                            adjustments.clear()
                            route = straight_route(raw_route)
                            if notices is not None:
                                notices.append(
                                    _straight_route_notice(raw_route.cable_number, error)
                                )
                    if (
                        unsafe := _adjustment_below_cable_radius(
                            adjustments, branch_diameter_mm / 2.0
                        )
                    ) is not None:
                        route = straight_route(raw_route)
                        adjustments.clear()
                        if notices is not None:
                            notices.append(
                                _straight_for_sweep_notice(
                                    raw_route.cable_number, unsafe, branch_diameter_mm
                                )
                            )
                    if notices is not None:
                        notices.extend(_adjustment_notice(item) for item in adjustments)
                    sibling_routes.append(route)
                    sibling_normals.append(branch_normals)
                    sibling_transitions.append(transitions)
                    sibling_radii.append(branch_radius)
                    sibling_fixed_end_normals.append(bool(fixed_indices))
                    sibling_legs.append(
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
                if len(sibling_routes) > 1 and not ribbon_root:
                    separated, collisions = separate_route_collisions(
                        tuple(sibling_routes),
                        tuple(route.cable_id for route in sibling_routes),
                        tuple(leg.diameter_mm for leg in sibling_legs),
                        tuple(sibling_normals),
                        tuple(sibling_transitions),
                        tuple(sibling_radii),
                        definition.minimum_clearance_mm,
                        auto_transition_fraction=auto_transition_fraction,
                        fixed_end_normals=tuple(sibling_fixed_end_normals),
                    )
                    sibling_routes = list(separated)
                    if notices is not None:
                        notices.extend(_collision_notice(item) for item in collisions)
                routes.extend(sibling_routes)
                legs.extend(sibling_legs)
    return tuple(routes), tuple(legs)


def reset_route_solve_cache() -> None:
    """
    Release the session-only geometry solution cache.
    """
    global _route_solve_cache

    _route_solve_cache = None
