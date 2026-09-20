"""Split, orient, and classify routed curves for solid sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# noinspection PyUnresolvedReferences
# noinspection PyUnresolvedReferences
from ...routing import (
    CubicBezier,
    RoutePreview,
    Vector3,
)
from ...routing.geometry import cross, difference, magnitude
from .constants import JUNCTION_TOLERANCE_MM


@dataclass(frozen=True)
class RouteSweepSegment:
    """
    Retain logical-route ownership for one junction-bounded sweep segment.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


def is_straight(curve: CubicBezier) -> bool:
    """
    Identify monotone collinear cubic spans that Fusion can represent as sketch lines.
    """
    chord = difference(curve.end, curve.start)
    length = magnitude(chord)
    if length <= 1e-9:
        raise ValueError("A wire curve has coincident endpoints.")
    return all(
        magnitude(cross(difference(point, curve.start), chord)) / length < 1e-9
        for point in (curve.control_a, curve.control_b)
    )


def _shared_route_endpoints(
    routes: tuple[RoutePreview, ...],
    tolerance_mm: float = JUNCTION_TOLERANCE_MM,
) -> tuple[tuple[Vector3, tuple[int, ...]], ...]:
    """
    Locate route endpoints shared by multiple legs in stable route order.
    """
    clusters: list[tuple[Vector3, set[int]]] = []
    for route_index, route in enumerate(routes):
        if not route.curves:
            raise ValueError(f"{route.wire_number} contains no curves for solid generation.")
        for point in (route.curves[0].start, route.curves[-1].end):
            cluster = next(
                (
                    candidate
                    for candidate in clusters
                    if magnitude(difference(point, candidate[0])) <= tolerance_mm
                ),
                None,
            )
            if cluster is None:
                clusters.append((point, {route_index}))
            else:
                cluster[1].add(route_index)
    return tuple(
        (point, tuple(sorted(route_indices)))
        for point, route_indices in clusters
        if len(route_indices) >= 2
    )


def prepare_group_sweep_segments(
    routes: tuple[RoutePreview, ...],
) -> tuple[
    tuple[RouteSweepSegment, ...],
    tuple[Optional[int], ...],
    tuple[Optional[int], ...],
]:
    """
    Split pass-through routes at attached leads and orient the resulting tree.
    """
    segments = _split_routes_at_interior_junctions(routes)
    oriented_routes, start_junctions, end_junctions = _orient_group_routes(
        tuple(segment.route for segment in segments)
    )
    oriented_segments = tuple(
        RouteSweepSegment(
            route,
            segment.source_route_index,
            segment.segment_index,
            segment.segment_count,
        )
        for segment, route in zip(segments, oriented_routes)
    )
    return oriented_segments, start_junctions, end_junctions


def _split_routes_at_interior_junctions(
    routes: tuple[RoutePreview, ...],
) -> tuple[RouteSweepSegment, ...]:
    """
    Split exact curves where another logical route terminates inside a route.
    """
    junction_points = _route_junction_points(routes)
    segments: list[RouteSweepSegment] = []
    for route_index, route in enumerate(routes):
        route_curves = _split_route_curves(route, junction_points)
        segment_count = len(route_curves)
        for segment_index, curves in enumerate(route_curves):
            segment_route = RoutePreview(
                route.wire_id,
                route.wire_number,
                (curves[0].start, *(curve.end for curve in curves)),
                curves,
            )
            segments.append(
                RouteSweepSegment(
                    segment_route,
                    route_index,
                    segment_index,
                    segment_count,
                )
            )
    return tuple(segments)


def _route_junction_points(routes: tuple[RoutePreview, ...]) -> tuple[Vector3, ...]:
    """
    Find route endpoints that coincide with any boundary on another route.
    """
    for route in routes:
        if not route.curves:
            raise ValueError(f"{route.wire_number} contains no curves for solid generation.")
    candidates: list[Vector3] = []
    for route_index, route in enumerate(routes):
        for point in (route.curves[0].start, route.curves[-1].end):
            incident_routes = {
                candidate_index
                for candidate_index, candidate in enumerate(routes)
                if candidate_index != route_index
                and any(
                    magnitude(difference(point, boundary)) <= JUNCTION_TOLERANCE_MM
                    for boundary in _route_curve_boundaries(candidate)
                )
            }
            if not incident_routes or any(
                magnitude(difference(point, candidate)) <= JUNCTION_TOLERANCE_MM
                for candidate in candidates
            ):
                continue
            candidates.append(point)
    return tuple(candidates)


def _route_curve_boundaries(route: RoutePreview) -> tuple[Vector3, ...]:
    """
    Return every exact boundary in one already-faired route.
    """
    return (route.curves[0].start,) + tuple(curve.end for curve in route.curves)


def _split_route_curves(
    route: RoutePreview,
    junction_points: tuple[Vector3, ...],
) -> tuple[tuple[CubicBezier, ...], ...]:
    """
    Partition a route after curves ending at an interior junction point.
    """
    partitions: list[tuple[CubicBezier, ...]] = []
    start_index = 0
    for curve_index, curve in enumerate(route.curves[:-1]):
        if not any(
            magnitude(difference(curve.end, junction)) <= JUNCTION_TOLERANCE_MM
            for junction in junction_points
        ):
            continue
        partitions.append(route.curves[start_index : curve_index + 1])
        start_index = curve_index + 1
    partitions.append(route.curves[start_index:])
    return tuple(partitions)


def _orient_group_routes(
    routes: tuple[RoutePreview, ...],
) -> tuple[
    tuple[RoutePreview, ...],
    tuple[Optional[int], ...],
    tuple[Optional[int], ...],
]:
    """
    Orient construction routes away from one stable junction root.
    """
    junctions = _shared_route_endpoints(routes)
    if not junctions:
        if len(routes) != 1:
            raise RuntimeError("Wire-group route legs do not form one connected tree.")
        return routes, (None,), (None,)
    endpoint_junctions = tuple(
        (
            _junction_at(route.curves[0].start, junctions),
            _junction_at(route.curves[-1].end, junctions),
        )
        for route in routes
    )
    oriented: list[Optional[RoutePreview]] = [None] * len(routes)
    start_junctions: list[Optional[int]] = [None] * len(routes)
    end_junctions: list[Optional[int]] = [None] * len(routes)
    pending = [0]
    visited_junctions = {0}
    while pending:
        junction_index = pending.pop(0)
        for route_index in junctions[junction_index][1]:
            if oriented[route_index] is not None:
                continue
            start_junction, end_junction = endpoint_junctions[route_index]
            if start_junction == junction_index:
                oriented[route_index] = routes[route_index]
                next_junction = end_junction
            elif end_junction == junction_index:
                oriented[route_index] = _reverse_route(routes[route_index])
                next_junction = start_junction
            else:
                raise RuntimeError("Wire-group route topology changed during construction.")
            start_junctions[route_index] = junction_index
            end_junctions[route_index] = next_junction
            if next_junction is not None:
                if next_junction in visited_junctions:
                    raise RuntimeError("Wire-group route legs contain a cycle.")
                visited_junctions.add(next_junction)
                pending.append(next_junction)
    if any(route is None for route in oriented):
        raise RuntimeError("Wire-group route legs do not form one connected tree.")
    return (
        tuple(route for route in oriented if route is not None),
        tuple(start_junctions),
        tuple(end_junctions),
    )


def _junction_at(
    point: Vector3,
    junctions: tuple[tuple[Vector3, tuple[int, ...]], ...],
) -> Optional[int]:
    """
    Resolve an endpoint to its shared junction index when present.
    """
    return next(
        (
            index
            for index, (junction, _route_indices) in enumerate(junctions)
            if magnitude(difference(point, junction)) <= JUNCTION_TOLERANCE_MM
        ),
        None,
    )


def _reverse_route(route: RoutePreview) -> RoutePreview:
    """
    Reverse only the construction traversal of one exact routed leg.
    """
    return RoutePreview(
        route.wire_id,
        route.wire_number,
        tuple(reversed(route.points)),
        tuple(
            CubicBezier(curve.end, curve.control_b, curve.control_a, curve.start)
            for curve in reversed(route.curves)
        ),
    )
