"""
Deterministic best-effort separation for already constrained wire routes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from uuid import UUID

from .geometry import Vector3, cross, difference, dot, magnitude, unit
from .parallel import RoutePreview
from .smooth import TransitionLengths, fair_route, sample_centerline

_SAMPLE_TOLERANCE_MM = 0.025
_NUMERIC_MARGIN_MM = 0.01
_MAX_REPAIR_PASSES = 16
_MAX_ROUTE_DETOURS = 4


@dataclass(frozen=True)
class RouteCollision:
    """
    Describe the worst remaining overlap between two distinct wire groups.
    """

    left_route_id: UUID
    right_route_id: UUID
    left_label: str
    right_label: str
    clearance_shortfall_mm: float
    left_point: Vector3
    right_point: Vector3


@dataclass(frozen=True)
class _Capsule:
    """
    Approximate one centerline interval with a conservatively expanded capsule.
    """

    route_index: int
    group_id: UUID
    start: Vector3
    end: Vector3
    radius_mm: float

    @property
    def minimum_x(self) -> float:
        """
        Return the expanded lower X extent used by sweep-and-prune.
        """
        return min(self.start.x, self.end.x) - self.radius_mm

    @property
    def maximum_x(self) -> float:
        """
        Return the expanded upper X extent used by sweep-and-prune.
        """
        return max(self.start.x, self.end.x) + self.radius_mm


def separate_route_collisions(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    normals: tuple[tuple[Vector3, ...], ...],
    transitions: tuple[tuple[TransitionLengths, ...], ...],
    minimum_bend_radii_mm: tuple[float, ...],
    clearance_mm: float,
) -> tuple[tuple[RoutePreview, ...], tuple[RouteCollision, ...]]:
    """
    Repair inter-group overlaps with bounded ephemeral between-guide detours.

    Guide crossings never move during this stage. Each accepted detour is
    refaired through the existing bend-radius solver, and deterministic limits
    ensure that identical definitions always produce identical geometry.
    """
    count = len(routes)
    if not all(
        len(items) == count
        for items in (group_ids, diameters_mm, normals, transitions, minimum_bend_radii_mm)
    ):
        raise ValueError("Collision routing inputs must align with the route sequence.")
    if not math.isfinite(clearance_mm) or clearance_mm < 0.0:
        raise ValueError("Minimum member clearance must be finite and nonnegative.")

    current = list(routes)
    route_normals = [list(items) for items in normals]
    route_transitions = [list(items) for items in transitions]
    detour_counts = [0] * count
    collisions = _route_collisions(tuple(current), group_ids, diameters_mm, clearance_mm)
    for _pass_index in range(_MAX_REPAIR_PASSES):
        if not collisions:
            break
        repaired = False
        for collision in sorted(
            collisions,
            key=lambda item: (-item.clearance_shortfall_mm, item.left_label, item.right_label),
        ):
            candidates = sorted(
                (
                    _route_index(current, collision.left_route_id),
                    _route_index(current, collision.right_route_id),
                ),
                key=lambda index: str(routes[index].wire_id),
                reverse=True,
            )
            for route_index in candidates:
                if detour_counts[route_index] >= _MAX_ROUTE_DETOURS:
                    continue
                selected_point = (
                    collision.left_point
                    if current[route_index].wire_id == collision.left_route_id
                    else collision.right_point
                )
                other_point = (
                    collision.right_point
                    if current[route_index].wire_id == collision.left_route_id
                    else collision.left_point
                )
                for candidate_route, candidate_normals, candidate_transitions in _detour_candidates(
                    current[route_index],
                    tuple(route_normals[route_index]),
                    tuple(route_transitions[route_index]),
                    minimum_bend_radii_mm[route_index],
                    selected_point,
                    other_point,
                    collision.clearance_shortfall_mm,
                ):
                    trial = list(current)
                    trial[route_index] = candidate_route
                    trial_collisions = _route_collisions(
                        tuple(trial), group_ids, diameters_mm, clearance_mm
                    )
                    if _collision_score(trial_collisions) >= _collision_score(collisions):
                        continue
                    current = trial
                    route_normals[route_index] = list(candidate_normals)
                    route_transitions[route_index] = list(candidate_transitions)
                    detour_counts[route_index] += 1
                    collisions = trial_collisions
                    repaired = True
                    break
                if repaired:
                    break
            if repaired:
                break
        if not repaired:
            break
    return tuple(current), collisions


def route_collisions(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    clearance_mm: float = 0.0,
) -> tuple[RouteCollision, ...]:
    """
    Report conservative inter-group tube collisions without changing routes.
    """
    if len(routes) != len(group_ids) or len(routes) != len(diameters_mm):
        raise ValueError("Collision routing inputs must align with the route sequence.")
    return _route_collisions(routes, group_ids, diameters_mm, clearance_mm)


def _detour_candidates(
    route: RoutePreview,
    normals: tuple[Vector3, ...],
    transitions: tuple[TransitionLengths, ...],
    minimum_bend_radius_mm: float,
    selected_point: Vector3,
    other_point: Vector3,
    shortfall_mm: float,
) -> tuple[tuple[RoutePreview, tuple[Vector3, ...], tuple[TransitionLengths, ...]], ...]:
    """
    Insert one free waypoint into the closest guide span and refair the route.
    """
    span_index = _nearest_span(route.points, selected_point)
    start = route.points[span_index]
    end = route.points[span_index + 1]
    chord = difference(end, start)
    try:
        tangent = unit(chord)
    except ValueError:
        return ()
    separation = difference(selected_point, other_point)
    if magnitude(separation) <= 1e-9:
        axis = min(
            (Vector3(1.0, 0.0, 0.0), Vector3(0.0, 1.0, 0.0), Vector3(0.0, 0.0, 1.0)),
            key=lambda axis_candidate: abs(dot(tangent, axis_candidate)),
        )
        separation = cross(tangent, axis)
    try:
        direction = unit(separation)
    except ValueError:
        return ()
    midpoint = Vector3(
        (start.x + end.x) / 2.0,
        (start.y + end.y) / 2.0,
        (start.z + end.z) / 2.0,
    )
    base_offset = max(shortfall_mm + _NUMERIC_MARGIN_MM, minimum_bend_radius_mm * 1.5)
    candidates = []
    for multiplier in (1.0, 1.5, 2.0, 3.0):
        waypoint = midpoint.translated(direction, base_offset * multiplier)
        points = (*route.points[: span_index + 1], waypoint, *route.points[span_index + 1 :])
        candidate_normals = (*normals[: span_index + 1], tangent, *normals[span_index + 1 :])
        candidate_transitions = (
            *transitions[: span_index + 1],
            TransitionLengths(),
            *transitions[span_index + 1 :],
        )
        try:
            candidate = fair_route(
                replace(route, points=points, curves=()),
                candidate_normals,
                candidate_transitions,
                minimum_bend_radius_mm=minimum_bend_radius_mm,
            )
        except ValueError:
            continue
        candidates.append((candidate, candidate_normals, candidate_transitions))
    return tuple(candidates)


def _route_collisions(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    clearance_mm: float,
) -> tuple[RouteCollision, ...]:
    """
    Find the worst capsule overlap for every pair of logical route legs.
    """
    capsules: list[_Capsule] = []
    for route_index, (route, group_id, diameter_mm) in enumerate(
        zip(routes, group_ids, diameters_mm)
    ):
        radius = diameter_mm / 2.0 + clearance_mm / 2.0 + _NUMERIC_MARGIN_MM
        points = _sample_route(route)
        capsules.extend(
            _Capsule(route_index, group_id, start, end, radius)
            for start, end in zip(points, points[1:])
            if magnitude(difference(end, start)) > 1e-12
        )
    ordered = sorted(capsules, key=lambda item: item.minimum_x)
    worst: dict[tuple[int, int], RouteCollision] = {}
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            if right.minimum_x > left.maximum_x:
                break
            if left.route_index == right.route_index or left.group_id == right.group_id:
                continue
            if not _overlapping_extents(left, right):
                continue
            distance, left_point, right_point = _segment_distance(
                left.start, left.end, right.start, right.end
            )
            required = left.radius_mm + right.radius_mm
            shortfall = required - distance
            if shortfall <= 0.0:
                continue
            first_route_index, second_route_index = sorted((left.route_index, right.route_index))
            pair = (first_route_index, second_route_index)
            left_route = routes[pair[0]]
            right_route = routes[pair[1]]
            candidate = RouteCollision(
                left_route.wire_id,
                right_route.wire_id,
                left_route.wire_number,
                right_route.wire_number,
                shortfall,
                left_point if pair[0] == left.route_index else right_point,
                right_point if pair[1] == right.route_index else left_point,
            )
            previous = worst.get(pair)
            if (
                previous is None
                or candidate.clearance_shortfall_mm > previous.clearance_shortfall_mm
            ):
                worst[pair] = candidate
    return tuple(worst[pair] for pair in sorted(worst))


def _sample_route(route: RoutePreview) -> tuple[Vector3, ...]:
    """
    Sample cubics with the shared bounded-error centerline implementation.
    """
    return sample_centerline(route, _SAMPLE_TOLERANCE_MM)


def _overlapping_extents(left: _Capsule, right: _Capsule) -> bool:
    """
    Reject capsule pairs whose expanded Y or Z extents are disjoint.
    """
    return not (
        min(right.start.y, right.end.y) - right.radius_mm
        > max(left.start.y, left.end.y) + left.radius_mm
        or min(left.start.y, left.end.y) - left.radius_mm
        > max(right.start.y, right.end.y) + right.radius_mm
        or min(right.start.z, right.end.z) - right.radius_mm
        > max(left.start.z, left.end.z) + left.radius_mm
        or min(left.start.z, left.end.z) - left.radius_mm
        > max(right.start.z, right.end.z) + right.radius_mm
    )


def _segment_distance(
    first_start: Vector3,
    first_end: Vector3,
    second_start: Vector3,
    second_end: Vector3,
) -> tuple[float, Vector3, Vector3]:
    """
    Return the closest points and distance between two finite 3D segments.
    """
    first = difference(first_end, first_start)
    second = difference(second_end, second_start)
    offset = difference(first_start, second_start)
    first_length = dot(first, first)
    second_length = dot(second, second)
    mixed = dot(first, second)
    first_offset = dot(first, offset)
    second_offset = dot(second, offset)
    denominator = first_length * second_length - mixed * mixed
    first_fraction = (
        0.0
        if denominator <= 1e-15
        else (mixed * second_offset - first_offset * second_length) / denominator
    )
    first_fraction = max(0.0, min(1.0, first_fraction))
    second_fraction = (
        0.0 if second_length <= 1e-15 else (mixed * first_fraction + second_offset) / second_length
    )
    if second_fraction < 0.0:
        second_fraction = 0.0
        first_fraction = (
            max(0.0, min(1.0, -first_offset / first_length)) if first_length > 1e-15 else 0.0
        )
    elif second_fraction > 1.0:
        second_fraction = 1.0
        first_fraction = (
            max(0.0, min(1.0, (mixed - first_offset) / first_length))
            if first_length > 1e-15
            else 0.0
        )
    first_point = first_start.translated(first, first_fraction)
    second_point = second_start.translated(second, second_fraction)
    return magnitude(difference(first_point, second_point)), first_point, second_point


def _nearest_span(points: tuple[Vector3, ...], target: Vector3) -> int:
    """
    Locate the guide span closest to one collision point.
    """
    return min(
        range(len(points) - 1),
        key=lambda index: _segment_distance(points[index], points[index + 1], target, target)[0],
    )


def _route_index(routes: list[RoutePreview], route_id: UUID) -> int:
    """
    Resolve a collision identity against the current deterministic route list.
    """
    return next(index for index, route in enumerate(routes) if route.wire_id == route_id)


def _collision_score(collisions: tuple[RouteCollision, ...]) -> tuple[float, int]:
    """
    Rank solutions by total penetration before the number of conflicting pairs.
    """
    return sum(item.clearance_shortfall_mm for item in collisions), len(collisions)
