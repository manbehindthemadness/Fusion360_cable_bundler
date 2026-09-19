"""
Deterministic best-effort separation for already constrained wire routes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterator, Optional
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

    start: Vector3
    end: Vector3
    radius_mm: float
    minimum_x: float
    maximum_x: float
    minimum_y: float
    maximum_y: float
    minimum_z: float
    maximum_z: float


@dataclass(frozen=True)
class _RouteGeometry:
    """
    Cache one route's sampled collision geometry and expanded bounds.
    """

    route: RoutePreview
    group_id: UUID
    capsules: tuple[_Capsule, ...]
    minimum_x: float
    maximum_x: float
    minimum_y: float
    maximum_y: float
    minimum_z: float
    maximum_z: float


class _CollisionIndex:
    """
    Retain sampled routes and incrementally update pairwise collisions.
    """

    def __init__(
        self,
        routes: tuple[RoutePreview, ...],
        group_ids: tuple[UUID, ...],
        diameters_mm: tuple[float, ...],
        clearance_mm: float,
    ) -> None:
        """
        Sample all initial routes once and build the collision-pair map.
        """
        self._group_ids = group_ids
        self._diameters_mm = diameters_mm
        self._clearance_mm = clearance_mm
        self._geometries = [
            _route_geometry(route, group_id, diameter_mm, clearance_mm)
            for route, group_id, diameter_mm in zip(routes, group_ids, diameters_mm)
        ]
        self._collisions: dict[tuple[int, int], RouteCollision] = {}
        for left_index, right_index in _candidate_route_pairs(tuple(self._geometries)):
            collision = _route_pair_collision(
                self._geometries[left_index],
                self._geometries[right_index],
            )
            if collision is not None:
                self._collisions[left_index, right_index] = collision

    @property
    def collisions(self) -> tuple[RouteCollision, ...]:
        """
        Return collisions in stable route-index order.
        """
        return tuple(self._collisions[pair] for pair in sorted(self._collisions))

    def candidate_update(
        self, route_index: int, route: RoutePreview
    ) -> tuple[_RouteGeometry, dict[tuple[int, int], RouteCollision]]:
        """
        Evaluate one replacement route without mutating indexed state.
        """
        geometry = _route_geometry(
            route,
            self._group_ids[route_index],
            self._diameters_mm[route_index],
            self._clearance_mm,
        )
        replacements: dict[tuple[int, int], RouteCollision] = {}
        for other_index, other_geometry in enumerate(self._geometries):
            if other_index == route_index or other_geometry.group_id == geometry.group_id:
                continue
            left_index, right_index = sorted((route_index, other_index))
            left_geometry = geometry if left_index == route_index else other_geometry
            right_geometry = geometry if right_index == route_index else other_geometry
            if not _overlapping_route_bounds(left_geometry, right_geometry):
                continue
            collision = _route_pair_collision(
                left_geometry,
                right_geometry,
            )
            if collision is not None:
                replacements[left_index, right_index] = collision
        return geometry, replacements

    def score_with(
        self,
        route_index: int,
        replacements: dict[tuple[int, int], RouteCollision],
    ) -> tuple[float, int]:
        """
        Score a candidate while retaining all unaffected route pairs.
        """
        collisions = (
            collision for pair, collision in self._collisions.items() if route_index not in pair
        )
        shortfall = sum(collision.clearance_shortfall_mm for collision in collisions)
        shortfall += sum(collision.clearance_shortfall_mm for collision in replacements.values())
        count = sum(1 for pair in self._collisions if route_index not in pair) + len(replacements)
        return shortfall, count

    def accept(
        self,
        route_index: int,
        geometry: _RouteGeometry,
        replacements: dict[tuple[int, int], RouteCollision],
    ) -> None:
        """
        Commit one evaluated route replacement and its changed pairs.
        """
        self._geometries[route_index] = geometry
        self._collisions = {
            pair: collision
            for pair, collision in self._collisions.items()
            if route_index not in pair
        }
        self._collisions.update(replacements)


def separate_route_collisions(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    normals: tuple[tuple[Vector3, ...], ...],
    transitions: tuple[tuple[TransitionLengths, ...], ...],
    minimum_bend_radii_mm: tuple[float, ...],
    clearance_mm: float,
    auto_transition_fraction: float = 0.25,
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
    if (
        not math.isfinite(auto_transition_fraction)
        or auto_transition_fraction <= 0.0
        or auto_transition_fraction > 0.5
    ):
        raise ValueError("Auto transition fraction must be finite and greater than 0 through 0.5.")

    current = list(routes)
    route_normals = [list(items) for items in normals]
    route_transitions = [list(items) for items in transitions]
    detour_counts = [0] * count
    collision_index = _CollisionIndex(tuple(current), group_ids, diameters_mm, clearance_mm)
    collisions = collision_index.collisions
    route_indices = {route.wire_id: index for index, route in enumerate(routes)}
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
                    route_indices[collision.left_route_id],
                    route_indices[collision.right_route_id],
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
                    auto_transition_fraction,
                ):
                    geometry, replacements = collision_index.candidate_update(
                        route_index, candidate_route
                    )
                    if collision_index.score_with(route_index, replacements) >= _collision_score(
                        collisions
                    ):
                        continue
                    current[route_index] = candidate_route
                    route_normals[route_index] = list(candidate_normals)
                    route_transitions[route_index] = list(candidate_transitions)
                    detour_counts[route_index] += 1
                    collision_index.accept(route_index, geometry, replacements)
                    collisions = collision_index.collisions
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
    auto_transition_fraction: float,
) -> Iterator[tuple[RoutePreview, tuple[Vector3, ...], tuple[TransitionLengths, ...]]]:
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
        return
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
        return
    midpoint = Vector3(
        (start.x + end.x) / 2.0,
        (start.y + end.y) / 2.0,
        (start.z + end.z) / 2.0,
    )
    base_offset = max(shortfall_mm + _NUMERIC_MARGIN_MM, minimum_bend_radius_mm * 1.5)
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
                auto_transition_fraction=auto_transition_fraction,
            )
        except ValueError:
            continue
        yield candidate, candidate_normals, candidate_transitions


def _route_collisions(
    routes: tuple[RoutePreview, ...],
    group_ids: tuple[UUID, ...],
    diameters_mm: tuple[float, ...],
    clearance_mm: float,
) -> tuple[RouteCollision, ...]:
    """
    Find the worst capsule overlap for every pair of logical route legs.
    """
    return _CollisionIndex(routes, group_ids, diameters_mm, clearance_mm).collisions


def _route_geometry(
    route: RoutePreview,
    group_id: UUID,
    diameter_mm: float,
    clearance_mm: float,
) -> _RouteGeometry:
    """
    Sample and bound one route for repeated collision queries.
    """
    radius = diameter_mm / 2.0 + clearance_mm / 2.0 + _NUMERIC_MARGIN_MM
    points = _sample_route(route)
    capsules = tuple(
        _capsule(start, end, radius)
        for start, end in zip(points, points[1:])
        if magnitude(difference(end, start)) > 1e-12
    )
    if not capsules:
        raise ValueError(f"Wire {route.wire_number} has no measurable collision geometry.")
    return _RouteGeometry(
        route,
        group_id,
        tuple(sorted(capsules, key=lambda item: item.minimum_x)),
        min(item.minimum_x for item in capsules),
        max(item.maximum_x for item in capsules),
        min(item.minimum_y for item in capsules),
        max(item.maximum_y for item in capsules),
        min(item.minimum_z for item in capsules),
        max(item.maximum_z for item in capsules),
    )


def _capsule(start: Vector3, end: Vector3, radius_mm: float) -> _Capsule:
    """
    Create a capsule with precomputed expanded axis-aligned bounds.
    """
    return _Capsule(
        start,
        end,
        radius_mm,
        min(start.x, end.x) - radius_mm,
        max(start.x, end.x) + radius_mm,
        min(start.y, end.y) - radius_mm,
        max(start.y, end.y) + radius_mm,
        min(start.z, end.z) - radius_mm,
        max(start.z, end.z) + radius_mm,
    )


def _candidate_route_pairs(
    geometries: tuple[_RouteGeometry, ...],
) -> Iterator[tuple[int, int]]:
    """
    Yield only route pairs whose expanded bounds overlap on all axes.
    """
    ordered = sorted(range(len(geometries)), key=lambda index: geometries[index].minimum_x)
    for position, left_index in enumerate(ordered):
        left = geometries[left_index]
        for right_index in ordered[position + 1 :]:
            right = geometries[right_index]
            if right.minimum_x > left.maximum_x:
                break
            if left.group_id == right.group_id or not _overlapping_route_bounds(left, right):
                continue
            yield (
                (left_index, right_index) if left_index < right_index else (right_index, left_index)
            )


def _overlapping_route_bounds(left: _RouteGeometry, right: _RouteGeometry) -> bool:
    """
    Return whether two expanded route boxes overlap on every axis.
    """
    return not (
        right.minimum_x > left.maximum_x
        or left.minimum_x > right.maximum_x
        or right.minimum_y > left.maximum_y
        or left.minimum_y > right.maximum_y
        or right.minimum_z > left.maximum_z
        or left.minimum_z > right.maximum_z
    )


def _route_pair_collision(
    left: _RouteGeometry,
    right: _RouteGeometry,
) -> Optional[RouteCollision]:
    """
    Find the worst sampled capsule overlap for one ordered route pair.
    """
    worst: Optional[RouteCollision] = None
    for left_capsule in left.capsules:
        for right_capsule in right.capsules:
            if right_capsule.minimum_x > left_capsule.maximum_x:
                break
            if right_capsule.maximum_x < left_capsule.minimum_x:
                continue
            if not _overlapping_extents(left_capsule, right_capsule):
                continue
            distance, left_point, right_point = _segment_distance(
                left_capsule.start,
                left_capsule.end,
                right_capsule.start,
                right_capsule.end,
            )
            shortfall = left_capsule.radius_mm + right_capsule.radius_mm - distance
            if shortfall <= 0.0:
                continue
            candidate = RouteCollision(
                left.route.wire_id,
                right.route.wire_id,
                left.route.wire_number,
                right.route.wire_number,
                shortfall,
                left_point,
                right_point,
            )
            if worst is None or shortfall > worst.clearance_shortfall_mm:
                worst = candidate
    return worst


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
        right.minimum_y > left.maximum_y
        or left.minimum_y > right.maximum_y
        or right.minimum_z > left.maximum_z
        or left.minimum_z > right.maximum_z
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


def _collision_score(collisions: tuple[RouteCollision, ...]) -> tuple[float, int]:
    """
    Rank solutions by total penetration before the number of conflicting pairs.
    """
    return sum(item.clearance_shortfall_mm for item in collisions), len(collisions)
