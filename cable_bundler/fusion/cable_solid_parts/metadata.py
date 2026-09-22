"""Coordinate transforms and persistent route metadata for generated solids."""

from __future__ import annotations

import math
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...routing import (
    CubicBezier,
    RoutePreview,
    Vector3,
)


def world_to_harness(
    design: adsk.fusion.Design, harness: adsk.fusion.Component
) -> adsk.core.Matrix3D:
    """
    Convert model-space preview coordinates into the unique harness placement.
    """
    if harness == design.rootComponent:
        return adsk.core.Matrix3D.create()
    placements = design.rootComponent.allOccurrencesByComponent(harness)
    if placements.count != 1:
        raise ValueError("Solid generation requires a single placement of the harness component.")
    transform = placements.item(0).transform2.copy()
    if not transform.invert():
        raise ValueError("Harness placement could not be inverted.")
    return transform


def fusion_point(point: Vector3, transform: adsk.core.Matrix3D) -> adsk.core.Point3D:
    """
    Convert solver millimeters into Fusion centimeters and harness-local coordinates.
    """
    result = adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
    if not result.transformBy(transform):
        raise RuntimeError("Could not transform a cable control point.")
    return result


def route_in_component_space(
    route: RoutePreview,
    transform: adsk.core.Matrix3D,
) -> RoutePreview:
    """
    Transform exact model-space curves into the generated component's coordinates.
    """

    def local(point: Vector3) -> Vector3:
        """
        Convert one model-space point into component-local millimeters.
        """
        transformed = fusion_point(point, transform)
        return Vector3(transformed.x * 10.0, transformed.y * 10.0, transformed.z * 10.0)

    curves = tuple(
        CubicBezier(
            local(curve.start),
            local(curve.control_a),
            local(curve.control_b),
            local(curve.end),
        )
        for curve in route.curves
    )
    points = (curves[0].start, *(curve.end for curve in curves))
    return RoutePreview(route.cable_id, route.cable_number, points, curves)


def route_metadata(route: RoutePreview) -> list[list[list[float]]]:
    """
    Serialize component-local curve controls used by a generated stripe overlay.
    """
    return [
        [
            [point.x, point.y, point.z]
            for point in (curve.start, curve.control_a, curve.control_b, curve.end)
        ]
        for curve in route.curves
    ]


def _route_from_encoded(
    route_id: UUID,
    label: str,
    encoded: object,
) -> RoutePreview:
    """
    Decode one component-local route from generated metadata.
    """
    if not isinstance(encoded, list) or not encoded:
        raise RuntimeError("Generated cable route metadata is malformed.")
    curves: list[CubicBezier] = []
    for encoded_curve in encoded:
        if not isinstance(encoded_curve, list) or len(encoded_curve) != 4:
            raise RuntimeError("Generated cable route metadata is malformed.")
        points: list[Vector3] = []
        for encoded_point in encoded_curve:
            if not isinstance(encoded_point, list) or len(encoded_point) != 3:
                raise RuntimeError("Generated cable route metadata is malformed.")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in encoded_point
            ):
                raise RuntimeError("Generated cable route metadata is malformed.")
            points.append(Vector3(*(float(value) for value in encoded_point)))
        curves.append(CubicBezier(*points))
    if any(left.end != right.start for left, right in zip(curves, curves[1:])):
        raise RuntimeError("Generated cable route metadata is discontinuous.")
    route_points = (curves[0].start, *(curve.end for curve in curves))
    return RoutePreview(route_id, label, route_points, tuple(curves))


def group_routes_from_metadata(metadata: dict[str, object]) -> tuple[RoutePreview, ...]:
    """
    Restore every exact component-local leg owned by a generated cable group.
    """
    encoded_legs = metadata.get("route_legs")
    if not isinstance(encoded_legs, list):
        raise RuntimeError("Generated cable-group route metadata is malformed.")
    routes: list[RoutePreview] = []
    for encoded_leg in encoded_legs:
        if not isinstance(encoded_leg, dict):
            raise RuntimeError("Generated cable-group route metadata is malformed.")
        try:
            route_id = UUID(encoded_leg["route_id"])
            label = encoded_leg["label"]
            encoded = encoded_leg["route_curves_mm"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Generated cable-group route metadata is malformed.") from error
        if not isinstance(label, str):
            raise RuntimeError("Generated cable-group route metadata is malformed.")
        routes.append(_route_from_encoded(route_id, label, encoded))
    return tuple(routes)


def group_geometry_routes_from_metadata(
    metadata: dict[str, object],
) -> tuple[RoutePreview, ...]:
    """
    Restore every main and reduced-diameter branch route stored for one group.
    """
    routes = list(group_routes_from_metadata(metadata))
    encoded_branches = metadata.get("connection_branches", [])
    if not isinstance(encoded_branches, list):
        raise RuntimeError("Generated cable-group branch metadata is malformed.")
    for encoded_branch in encoded_branches:
        if not isinstance(encoded_branch, dict):
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        try:
            route_id = UUID(encoded_branch["route_id"])
            label = encoded_branch["label"]
            encoded = encoded_branch["route_curves_mm"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Generated cable-group branch metadata is malformed.") from error
        if not isinstance(label, str):
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        routes.append(_route_from_encoded(route_id, label, encoded))
    return tuple(routes)
