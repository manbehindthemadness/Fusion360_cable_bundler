"""
Condition bounded guide crossings and shared-junction tangents before fairing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Optional
from uuid import UUID

from .geometry import Vector3, difference, dot, magnitude, unit
from .parallel import RoutePreview
from .smooth import TransitionLengths

_BASE_AUTO_SHARE = 0.25
_FULL_RELAXATION_SHARE = 0.5


@dataclass(frozen=True)
class CircularGuideConstraint:
    """
    Describe one planar circular region with an orthonormal frame.
    """

    origin: Vector3
    normal: Vector3
    u_direction: Vector3
    v_direction: Vector3
    usable_radius_mm: Optional[float]


@dataclass(frozen=True)
class _JunctionIncident:
    """
    Locate one route endpoint incident to a shared junction control.
    """

    route_index: int
    point_index: int
    route_id: UUID
    outward_direction: Vector3


@dataclass(frozen=True)
class _ControlPointIncident:
    """
    Retain one routed occurrence used to place a shared control crossing.
    """

    route_index: int
    point_index: int
    group_id: UUID
    point: Vector3
    neighbors: tuple[Vector3, ...]
    diameter_mm: float
    strength: float


def condition_connection_points(
    constraints: tuple[CircularGuideConstraint, ...],
    pathway_target: Vector3,
    diameter_mm: float,
    transitions: tuple[TransitionLengths, ...],
    auto_transition_fraction: float,
) -> tuple[Vector3, ...]:
    """
    Place an ordered terminal stack and relax intermediate guide crossings.

    The physical terminal remains at its existing bounded placement. Additional
    guides move only inside their circular aperture, and only by the relaxation
    implied by their resolved transition share.
    """
    if len(constraints) != len(transitions):
        raise ValueError("Guide constraints and transitions must align.")
    if not constraints:
        return ()
    if not math.isfinite(diameter_mm) or diameter_mm <= 0.0:
        raise ValueError("Wire diameter must be finite and positive.")
    _validate_auto_transition_fraction(auto_transition_fraction)

    reversed_points: list[Vector3] = []
    target = pathway_target
    for constraint in reversed(constraints):
        point = _clamp_to_guide(target, constraint, diameter_mm)
        reversed_points.append(point)
        target = point
    points = list(reversed(reversed_points))

    for _sweep in range(2):
        for indices in (range(1, len(points)), range(len(points) - 1, 0, -1)):
            for index in indices:
                previous = points[index - 1]
                current = points[index]
                following = points[index + 1] if index + 1 < len(points) else pathway_target
                strength = _guide_relaxation_strength(
                    previous,
                    current,
                    following,
                    transitions[index],
                    auto_transition_fraction,
                )
                if strength <= 0.0:
                    continue
                candidate = _line_plane_crossing(previous, following, constraints[index])
                candidate = _clamp_to_guide(candidate, constraints[index], diameter_mm)
                blended = Vector3(
                    current.x + (candidate.x - current.x) * strength,
                    current.y + (candidate.y - current.y) * strength,
                    current.z + (candidate.z - current.z) * strength,
                )
                points[index] = _clamp_to_guide(blended, constraints[index], diameter_mm)
    return tuple(points)


def condition_junction_points(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    point_control_ids: tuple[tuple[Optional[UUID], ...], ...],
    transitions: tuple[tuple[TransitionLengths, ...], ...],
    junction_constraints: dict[UUID, CircularGuideConstraint],
    auto_transition_fraction: float,
) -> tuple[RoutePreview, ...]:
    """
    Translate packed junction clusters toward their incident route geometry.

    Every group crossing at one junction receives the same in-plane translation.
    Relative packing and therefore at-guide separation remain unchanged.
    """
    return condition_control_points(
        routes,
        group_ids,
        diameters_mm,
        point_control_ids,
        transitions,
        junction_constraints,
        auto_transition_fraction,
    )


def condition_control_points(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    point_control_ids: tuple[tuple[Optional[UUID], ...], ...],
    transitions: tuple[tuple[TransitionLengths, ...], ...],
    control_constraints: dict[UUID, CircularGuideConstraint],
    auto_transition_fraction: float,
) -> tuple[RoutePreview, ...]:
    """
    Relax packed circular-control clusters toward direct incident passages.

    Two simultaneous passes remove center-seeking bends without making the
    result depend on control iteration order. Every control moves as one rigid,
    aperture-bounded cluster, preserving the deterministic member packing.
    """
    route_count = len(routes)
    if not (
        route_count
        == len(group_ids)
        == len(diameters_mm)
        == len(point_control_ids)
        == len(transitions)
    ):
        raise ValueError("Control conditioning inputs must align by route.")
    _validate_auto_transition_fraction(auto_transition_fraction)
    conditioned = routes
    for _pass_index in range(2):
        updated = _condition_control_point_pass(
            conditioned,
            group_ids,
            diameters_mm,
            point_control_ids,
            transitions,
            control_constraints,
            auto_transition_fraction,
        )
        if updated is conditioned:
            break
        conditioned = updated
    return conditioned


def _condition_control_point_pass(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    point_control_ids: tuple[tuple[Optional[UUID], ...], ...],
    transitions: tuple[tuple[TransitionLengths, ...], ...],
    control_constraints: dict[UUID, CircularGuideConstraint],
    auto_transition_fraction: float,
) -> tuple[RoutePreview, ...]:
    """
    Apply one simultaneous packed-cluster relaxation pass.
    """
    automatic_strength = _automatic_relaxation_strength(auto_transition_fraction)
    incidents: dict[UUID, list[_ControlPointIncident]] = {}
    for route_index, route in enumerate(routes):
        control_ids = point_control_ids[route_index]
        route_transitions = transitions[route_index]
        if not (len(route.points) == len(control_ids) == len(route_transitions)):
            raise ValueError("Every route point requires matching control metadata.")
        for point_index, control_id in enumerate(control_ids):
            if control_id not in control_constraints:
                continue
            neighbors = tuple(
                route.points[neighbor_index]
                for neighbor_index in (point_index - 1, point_index + 1)
                if 0 <= neighbor_index < len(route.points)
            )
            if not neighbors:
                continue
            transition = route_transitions[point_index]
            if (
                transition.approach_mm is None
                and transition.departure_mm is None
                and _neighbors_are_distinct(route.points[point_index], neighbors)
            ):
                strength = automatic_strength
            else:
                strength = transition_relaxation_strength(
                    route.points,
                    point_index,
                    transition,
                    auto_transition_fraction,
                )
            incidents.setdefault(control_id, []).append(
                _ControlPointIncident(
                    route_index,
                    point_index,
                    group_ids[route_index],
                    route.points[point_index],
                    neighbors,
                    diameters_mm[route_index],
                    strength,
                )
            )

    replacements: dict[tuple[int, int], Vector3] = {}
    for control_id, members in incidents.items():
        constraint = control_constraints[control_id]
        by_group: dict[UUID, list[_ControlPointIncident]] = {}
        for member in members:
            by_group.setdefault(member.group_id, []).append(member)
        delta_x = 0.0
        delta_y = 0.0
        delta_z = 0.0
        cluster_strength = 1.0
        for group_members in by_group.values():
            crossing = group_members[0].point
            if len(group_members) == 1:
                desired = _incident_control_target(group_members[0].neighbors, constraint)
            else:
                targets = tuple(
                    _incident_control_target(item.neighbors, constraint) for item in group_members
                )
                target_count = len(targets)
                desired = Vector3(
                    sum(item.x for item in targets) / target_count,
                    sum(item.y for item in targets) / target_count,
                    sum(item.z for item in targets) / target_count,
                )
            delta = difference(desired, crossing)
            normal_distance = dot(delta, constraint.normal)
            delta_x += delta.x - constraint.normal.x * normal_distance
            delta_y += delta.y - constraint.normal.y * normal_distance
            delta_z += delta.z - constraint.normal.z * normal_distance
            cluster_strength = min(
                cluster_strength,
                *(item.strength for item in group_members),
            )
        group_count = len(by_group)
        if cluster_strength <= 0.0 or group_count == 0:
            continue
        translation = Vector3(
            delta_x / group_count * cluster_strength,
            delta_y / group_count * cluster_strength,
            delta_z / group_count * cluster_strength,
        )
        if dot(translation, translation) <= 1e-18:
            continue
        group_points = [
            (group_members[0].point, group_members[0].diameter_mm)
            for group_members in by_group.values()
        ]
        translation_scale = _bounded_cluster_translation_scale(
            group_points,
            translation,
            constraint,
        )
        if translation_scale <= 0.0:
            continue
        for member in members:
            replacements[member.route_index, member.point_index] = Vector3(
                member.point.x + translation.x * translation_scale,
                member.point.y + translation.y * translation_scale,
                member.point.z + translation.z * translation_scale,
            )

    if not replacements:
        return routes
    conditioned: list[RoutePreview] = []
    for route_index, route in enumerate(routes):
        points = tuple(
            replacements.get((route_index, point_index), point)
            for point_index, point in enumerate(route.points)
        )
        conditioned.append(RoutePreview(route.wire_id, route.wire_number, points))
    return tuple(conditioned)


def _incident_control_target(
    neighbors: tuple[Vector3, ...],
    constraint: CircularGuideConstraint,
) -> Vector3:
    """
    Return the natural plane crossing for one through-route or branch incident.
    """
    if len(neighbors) == 2:
        return _line_plane_crossing(neighbors[0], neighbors[1], constraint)
    return _project_to_plane(neighbors[0], constraint)


def _neighbors_are_distinct(point: Vector3, neighbors: tuple[Vector3, ...]) -> bool:
    """
    Return whether every incident span has measurable length.
    """
    return all(
        dot(delta, delta) > 1e-18
        for delta in (difference(neighbor, point) for neighbor in neighbors)
    )


def junction_tangent_targets(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    point_control_ids: tuple[tuple[Optional[UUID], ...], ...],
    junction_control_ids: frozenset[UUID],
) -> tuple[dict[int, Vector3], ...]:
    """
    Choose a deterministic primary trunk axis at every occupied junction.

    Internal junction points follow their through-route secant. Split legs choose
    the best-aligned pair as a continuous trunk, while every side branch approaches
    directly along its own incident span.
    """
    if not (len(routes) == len(group_ids) == len(point_control_ids)):
        raise ValueError("Junction conditioning inputs must align by route.")
    targets: tuple[dict[int, Vector3], ...] = tuple({} for _ in routes)
    incidents: dict[tuple[UUID, UUID], list[_JunctionIncident]] = {}
    for route_index, (route, group_id, control_ids) in enumerate(
        zip(routes, group_ids, point_control_ids)
    ):
        if len(route.points) != len(control_ids):
            raise ValueError("Every route point requires a matching control identity.")
        for point_index, control_id in enumerate(control_ids):
            if control_id not in junction_control_ids or len(route.points) < 2:
                continue
            if 0 < point_index < len(route.points) - 1:
                through_direction = difference(
                    route.points[point_index + 1],
                    route.points[point_index - 1],
                )
                if magnitude(through_direction) > 1e-12:
                    targets[route_index][point_index] = through_direction
                continue
            neighbor_index = 1 if point_index == 0 else point_index - 1
            outward = unit(difference(route.points[neighbor_index], route.points[point_index]))
            incidents.setdefault((group_id, control_id), []).append(
                _JunctionIncident(route_index, point_index, route.wire_id, outward)
            )

    for members in incidents.values():
        if len(members) < 2:
            continue
        ordered = tuple(sorted(members, key=lambda item: (str(item.route_id), item.point_index)))
        trunk_left, trunk_right = min(
            combinations(ordered, 2),
            key=lambda pair: (
                dot(pair[0].outward_direction, pair[1].outward_direction),
                str(pair[0].route_id),
                str(pair[1].route_id),
            ),
        )
        axis_delta = difference(trunk_left.outward_direction, trunk_right.outward_direction)
        axis = trunk_left.outward_direction if magnitude(axis_delta) <= 1e-12 else unit(axis_delta)
        trunk_members = {
            (trunk_left.route_index, trunk_left.point_index),
            (trunk_right.route_index, trunk_right.point_index),
        }
        for incident in ordered:
            incident_key = (incident.route_index, incident.point_index)
            target = axis if incident_key in trunk_members else incident.outward_direction
            targets[incident.route_index][incident.point_index] = target
    return targets


def condition_route_normals(
    route: RoutePreview,
    normals: tuple[Vector3, ...],
    transitions: tuple[TransitionLengths, ...],
    soft_guide_indices: frozenset[int],
    junction_targets: dict[int, Vector3],
    auto_transition_fraction: float,
) -> tuple[Vector3, ...]:
    """
    Relax selected guide normals toward natural or junction-coordinated tangents.

    Tight or equivalently short transitions retain the authored normal. Longer
    resolved transition shares progressively approach the conditioned tangent.
    Physical terminal indices must not be included in ``soft_guide_indices``.
    """
    if not (len(route.points) == len(normals) == len(transitions)):
        raise ValueError("Route conditioning inputs must align by point.")
    _validate_auto_transition_fraction(auto_transition_fraction)
    conditioned = list(normals)
    indices = soft_guide_indices | junction_targets.keys()
    for index in indices:
        if not 0 <= index < len(route.points):
            raise ValueError("Conditioned guide index is outside the route.")
        target = junction_targets.get(index)
        if target is None:
            if index == 0 or index == len(route.points) - 1:
                continue
            target = difference(route.points[index + 1], route.points[index - 1])
        strength = transition_relaxation_strength(
            route.points,
            index,
            transitions[index],
            auto_transition_fraction,
        )
        if strength <= 0.0:
            continue
        conditioned[index] = _blend_axis(normals[index], target, strength)
    return tuple(conditioned)


def transition_relaxation_strength(
    points: tuple[Vector3, ...],
    index: int,
    transition: TransitionLengths,
    auto_transition_fraction: float,
) -> float:
    """
    Map resolved adjacent-span shares from Tight through Loose onto zero through one.
    """
    if not 0 <= index < len(points):
        raise ValueError("Transition index is outside the route.")
    _validate_auto_transition_fraction(auto_transition_fraction)
    shares: list[float] = []
    if index > 0:
        distance = magnitude(difference(points[index], points[index - 1]))
        if distance <= 1e-9:
            return 0.0
        shares.append(
            auto_transition_fraction
            if transition.approach_mm is None
            else transition.approach_mm / distance
        )
    if index + 1 < len(points):
        distance = magnitude(difference(points[index + 1], points[index]))
        if distance <= 1e-9:
            return 0.0
        shares.append(
            auto_transition_fraction
            if transition.departure_mm is None
            else transition.departure_mm / distance
        )
    if not shares:
        return 0.0
    effective_share = min(shares)
    return max(
        0.0,
        min(
            1.0,
            (effective_share - _BASE_AUTO_SHARE) / (_FULL_RELAXATION_SHARE - _BASE_AUTO_SHARE),
        ),
    )


def _guide_relaxation_strength(
    previous: Vector3,
    current: Vector3,
    following: Vector3,
    transition: TransitionLengths,
    auto_transition_fraction: float,
) -> float:
    """
    Resolve one connection-native guide's two-sided relaxation strength.
    """
    points = (previous, current, following)
    return transition_relaxation_strength(points, 1, transition, auto_transition_fraction)


def _line_plane_crossing(
    start: Vector3,
    end: Vector3,
    constraint: CircularGuideConstraint,
) -> Vector3:
    """
    Return the segment's plane crossing or its projected midpoint when nearly parallel.
    """
    direction = difference(end, start)
    denominator = dot(direction, constraint.normal)
    if abs(denominator) <= 1e-12:
        midpoint = Vector3(
            (start.x + end.x) * 0.5,
            (start.y + end.y) * 0.5,
            (start.z + end.z) * 0.5,
        )
        return _project_to_plane(midpoint, constraint)
    parameter = dot(difference(constraint.origin, start), constraint.normal) / denominator
    parameter = max(0.0, min(1.0, parameter))
    crossing = Vector3(
        start.x + direction.x * parameter,
        start.y + direction.y * parameter,
        start.z + direction.z * parameter,
    )
    return _project_to_plane(crossing, constraint)


def _clamp_to_guide(
    point: Vector3,
    constraint: CircularGuideConstraint,
    diameter_mm: float,
) -> Vector3:
    """
    Project a centerline point into one guide's usable circular interior.
    """
    projected = _project_to_plane(point, constraint)
    if constraint.usable_radius_mm is None:
        return constraint.origin
    available_radius = max(0.0, constraint.usable_radius_mm - diameter_mm * 0.5)
    offset = difference(projected, constraint.origin)
    u_offset = dot(offset, constraint.u_direction)
    v_offset = dot(offset, constraint.v_direction)
    radial_distance = math.hypot(u_offset, v_offset)
    scale = (
        1.0
        if radial_distance <= available_radius or radial_distance <= 1e-12
        else available_radius / radial_distance
    )
    return constraint.origin.translated(constraint.u_direction, u_offset * scale).translated(
        constraint.v_direction,
        v_offset * scale,
    )


def _project_to_plane(point: Vector3, constraint: CircularGuideConstraint) -> Vector3:
    """
    Project one point orthogonally onto a guide plane.
    """
    offset = difference(point, constraint.origin)
    normal = constraint.normal
    normal_distance = dot(offset, normal)
    return point.translated(normal, -normal_distance)


def _in_plane(vector: Vector3, constraint: CircularGuideConstraint) -> Vector3:
    """
    Remove the component normal to one guide plane.
    """
    normal = constraint.normal
    normal_distance = dot(vector, normal)
    return vector.translated(normal, -normal_distance)


def _bounded_cluster_translation_scale(
    points: list[tuple[Vector3, float]],
    translation: Vector3,
    constraint: CircularGuideConstraint,
) -> float:
    """
    Return the largest common translation fraction contained by one aperture.
    """
    squared_translation = dot(translation, translation)
    if squared_translation <= 1e-18:
        return 0.0
    scale = 1.0
    for point, diameter_mm in points:
        available_radius = max(0.0, (constraint.usable_radius_mm or 0.0) - diameter_mm * 0.5)
        offset = _in_plane(difference(point, constraint.origin), constraint)
        constant = dot(offset, offset) - available_radius * available_radius
        linear = 2.0 * dot(offset, translation)
        discriminant = linear * linear - 4.0 * squared_translation * constant
        if discriminant < 0.0:
            return 0.0
        positive_root = (-linear + math.sqrt(discriminant)) / (2.0 * squared_translation)
        scale = min(scale, max(0.0, positive_root))
    return scale


def _blend_axis(normal: Vector3, target: Vector3, strength: float) -> Vector3:
    """
    Blend unoriented tangent axes without introducing a sign reversal.
    """
    authored = unit(normal)
    desired = unit(target)
    if dot(authored, desired) < 0.0:
        authored = Vector3(-authored.x, -authored.y, -authored.z)
    return unit(
        Vector3(
            authored.x + (desired.x - authored.x) * strength,
            authored.y + (desired.y - authored.y) * strength,
            authored.z + (desired.z - authored.z) * strength,
        )
    )


def _validate_auto_transition_fraction(value: float) -> None:
    """
    Require the same automatic transition range as the fairing solver.
    """
    if not math.isfinite(value) or value <= 0.0 or value > 0.5:
        raise ValueError("Auto transition fraction must be finite and greater than 0 through 0.5.")


def _automatic_relaxation_strength(auto_transition_fraction: float) -> float:
    """
    Resolve the shared strength for an automatic transition preset.
    """
    return max(
        0.0,
        min(
            1.0,
            (auto_transition_fraction - _BASE_AUTO_SHARE)
            / (_FULL_RELAXATION_SHARE - _BASE_AUTO_SHARE),
        ),
    )
