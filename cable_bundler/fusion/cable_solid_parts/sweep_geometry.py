"""Split, orient, and classify routed curves for solid sweeps."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

# noinspection PyUnresolvedReferences
# noinspection PyUnresolvedReferences
from ...routing import (
    CubicBezier,
    RoutePreview,
    Vector3,
)
from ...routing.geometry import cross, difference, lerp, magnitude
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


@dataclass(frozen=True)
class RoutePullbackSplit:
    """
    Partition a target-facing route span without changing its total centerline.

    ``pullback`` begins at the connection target. ``insulation`` continues from
    its endpoint toward the parent cable; either route is absent when the split
    consumes none or all of the original route.
    """

    insulation: Optional[RoutePreview]
    pullback: Optional[RoutePreview]
    pullback_length_mm: float


@dataclass(frozen=True)
class RouteEndpointPullbackSplit:
    """
    Partition independent pullback spans from both ends of one route.
    """

    insulation: Optional[RoutePreview]
    start_pullback: Optional[RoutePreview]
    end_pullback: Optional[RoutePreview]
    start_length_mm: float
    end_length_mm: float


def split_route_for_pullback(route: RoutePreview, distance_mm: float) -> RoutePullbackSplit:
    """
    Split a route by arc length measured from its target-facing start.

    The requested distance is clamped to the available centerline length. The
    original identity and exact cubic path are retained across the two results.
    """
    if (
        isinstance(distance_mm, bool)
        or not isinstance(distance_mm, (int, float))
        or not math.isfinite(distance_mm)
        or distance_mm < 0.0
    ):
        raise ValueError("Pullback distance must be finite and nonnegative.")
    if not route.curves:
        raise ValueError("A pullback route requires at least one curve.")
    if distance_mm <= 1e-9:
        return RoutePullbackSplit(route, None, 0.0)

    curve_lengths = tuple(_curve_arc_length(curve) for curve in route.curves)
    total_length = sum(curve_lengths)
    if distance_mm >= total_length - 1e-9:
        return RoutePullbackSplit(None, route, total_length)

    remaining_distance = float(distance_mm)
    for curve_index, (curve, curve_length) in enumerate(zip(route.curves, curve_lengths)):
        if remaining_distance >= curve_length - 1e-9:
            remaining_distance -= curve_length
            continue
        parameter = _curve_parameter_at_length(curve, remaining_distance, curve_length)
        before, after = _split_cubic(curve, parameter)
        pullback_curves = (*route.curves[:curve_index], before)
        insulation_curves = (after, *route.curves[curve_index + 1 :])
        return RoutePullbackSplit(
            _route_with_curves(route, insulation_curves),
            _route_with_curves(route, pullback_curves),
            float(distance_mm),
        )
    raise RuntimeError("Pullback route splitting did not locate its requested distance.")


def split_route_endpoint_pullbacks(
    route: RoutePreview,
    start_distance_mm: float,
    end_distance_mm: float,
) -> RouteEndpointPullbackSplit:
    """
    Split target-facing spans from both route ends without overlap.

    When the requests overlap, both are reduced proportionally so neither
    endpoint wins the available centerline. The exact original path is retained.
    """
    for distance_mm in (start_distance_mm, end_distance_mm):
        if (
            isinstance(distance_mm, bool)
            or not isinstance(distance_mm, (int, float))
            or not math.isfinite(distance_mm)
            or distance_mm < 0.0
        ):
            raise ValueError("Pullback distance must be finite and nonnegative.")
    requested_total = start_distance_mm + end_distance_mm
    route_length = sum(_curve_arc_length(curve) for curve in route.curves)
    if requested_total > route_length and requested_total > 0.0:
        scale = route_length / requested_total
        start_distance_mm *= scale
        end_distance_mm *= scale
    start_split = split_route_for_pullback(route, start_distance_mm)
    if start_split.insulation is None or end_distance_mm <= 1e-9:
        return RouteEndpointPullbackSplit(
            start_split.insulation,
            start_split.pullback,
            None,
            start_split.pullback_length_mm,
            0.0,
        )
    reversed_insulation = _reverse_route(start_split.insulation)
    end_split = split_route_for_pullback(reversed_insulation, end_distance_mm)
    return RouteEndpointPullbackSplit(
        None if end_split.insulation is None else _reverse_route(end_split.insulation),
        start_split.pullback,
        None if end_split.pullback is None else _reverse_route(end_split.pullback),
        start_split.pullback_length_mm,
        end_split.pullback_length_mm,
    )


def _route_with_curves(
    source: RoutePreview,
    curves: tuple[CubicBezier, ...],
) -> RoutePreview:
    """
    Preserve route identity while replacing its exact contiguous cubic span.
    """
    points = (curves[0].start, *(curve.end for curve in curves))
    return RoutePreview(source.cable_id, source.cable_number, points, curves)


def _split_cubic(curve: CubicBezier, parameter: float) -> tuple[CubicBezier, CubicBezier]:
    """
    Split one cubic exactly with De Casteljau interpolation.
    """
    start_a = lerp(curve.start, curve.control_a, parameter)
    middle = lerp(curve.control_a, curve.control_b, parameter)
    end_b = lerp(curve.control_b, curve.end, parameter)
    left_b = lerp(start_a, middle, parameter)
    right_a = lerp(middle, end_b, parameter)
    split = lerp(left_b, right_a, parameter)
    return (
        CubicBezier(curve.start, start_a, left_b, split),
        CubicBezier(split, right_a, end_b, curve.end),
    )


def _curve_parameter_at_length(
    curve: CubicBezier,
    distance_mm: float,
    curve_length_mm: float,
) -> float:
    """
    Locate an arc-length position on one cubic with bounded bisection.
    """
    lower = 0.0
    upper = 1.0
    for _iteration in range(48):
        midpoint = (lower + upper) / 2.0
        if _curve_arc_length(curve, midpoint) < distance_mm:
            lower = midpoint
        else:
            upper = midpoint
    parameter = (lower + upper) / 2.0
    if not 0.0 < parameter < 1.0 or curve_length_mm <= 0.0:
        raise RuntimeError("Pullback curve produced an invalid split parameter.")
    return parameter


def _curve_arc_length(curve: CubicBezier, end_parameter: float = 1.0) -> float:
    """
    Integrate cubic speed accurately enough to place a millimeter pullback split.
    """
    if not 0.0 <= end_parameter <= 1.0:
        raise ValueError("Curve length parameter must be between zero and one.")
    if end_parameter == 0.0:
        return 0.0

    def speed(parameter: float) -> float:
        return magnitude(curve.derivative(parameter))

    start = speed(0.0)
    middle = speed(end_parameter / 2.0)
    end = speed(end_parameter)
    estimate = end_parameter * (start + 4.0 * middle + end) / 6.0
    return _adaptive_simpson(
        speed,
        0.0,
        end_parameter,
        start,
        middle,
        end,
        estimate,
        1e-8,
        16,
    )


def _adaptive_simpson(
    function: Callable[[float], float],
    start: float,
    end: float,
    start_value: float,
    middle_value: float,
    end_value: float,
    estimate: float,
    tolerance: float,
    depth: int,
) -> float:
    """
    Refine one Simpson interval until its arc-length estimate converges.
    """
    midpoint = (start + end) / 2.0
    left_midpoint = (start + midpoint) / 2.0
    right_midpoint = (midpoint + end) / 2.0
    left_midpoint_value = function(left_midpoint)
    right_midpoint_value = function(right_midpoint)
    left = (midpoint - start) * (start_value + 4.0 * left_midpoint_value + middle_value) / 6.0
    right = (end - midpoint) * (middle_value + 4.0 * right_midpoint_value + end_value) / 6.0
    refined = left + right
    if depth <= 0 or abs(refined - estimate) <= 15.0 * tolerance:
        return refined + (refined - estimate) / 15.0
    return _adaptive_simpson(
        function,
        start,
        midpoint,
        start_value,
        left_midpoint_value,
        middle_value,
        left,
        tolerance / 2.0,
        depth - 1,
    ) + _adaptive_simpson(
        function,
        midpoint,
        end,
        middle_value,
        right_midpoint_value,
        end_value,
        right,
        tolerance / 2.0,
        depth - 1,
    )


def is_straight(curve: CubicBezier) -> bool:
    """
    Identify monotone collinear cubic spans that Fusion can represent as sketch lines.
    """
    chord = difference(curve.end, curve.start)
    length = magnitude(chord)
    if length <= 1e-9:
        raise ValueError("A cable curve has coincident endpoints.")
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
            raise ValueError(f"{route.cable_number} contains no curves for solid generation.")
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
                route.cable_id,
                route.cable_number,
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
            raise ValueError(f"{route.cable_number} contains no curves for solid generation.")
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
            raise RuntimeError("Cable-group route legs do not form one connected tree.")
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
                raise RuntimeError("Cable-group route topology changed during construction.")
            start_junctions[route_index] = junction_index
            end_junctions[route_index] = next_junction
            if next_junction is not None:
                if next_junction in visited_junctions:
                    raise RuntimeError("Cable-group route legs contain a cycle.")
                visited_junctions.add(next_junction)
                pending.append(next_junction)
    if any(route is None for route in oriented):
        raise RuntimeError("Cable-group route legs do not form one connected tree.")
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
        route.cable_id,
        route.cable_number,
        tuple(reversed(route.points)),
        tuple(
            CubicBezier(curve.end, curve.control_b, curve.control_a, curve.start)
            for curve in reversed(route.curves)
        ),
    )
