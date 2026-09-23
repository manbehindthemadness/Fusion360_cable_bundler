"""
Coordinate transforms and persistent route metadata for generated solids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional
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


@dataclass(frozen=True)
class ConnectionBranchRoute:
    """
    Restore one generated connection branch and its material-owner identity.
    """

    route: RoutePreview
    diameter_mm: float
    attachment_id: Optional[UUID]
    pullback_mm: float = 0.0
    pullback_requested_mm: float = 0.0
    pullback_diameter_mm: float = 0.75
    insulation_body_count: int = 1
    pullback_body_count: int = 0
    weld_body_count: int = 0
    weld_diameter_mm: float = 0.0
    weld_conductor_diameter_mm: float = 0.0
    weld_length_mm: float = 0.0


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
    routes.extend(branch.route for branch in connection_branches_from_metadata(metadata))
    return tuple(routes)


def connection_branches_from_metadata(
    metadata: dict[str, object],
) -> tuple[ConnectionBranchRoute, ...]:
    """
    Restore generated branch routes, diameters, and optional saved attachment IDs.
    """
    encoded_branches = metadata.get("connection_branches", [])
    if not isinstance(encoded_branches, list):
        raise RuntimeError("Generated cable-group branch metadata is malformed.")
    branches: list[ConnectionBranchRoute] = []
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
        raw_diameter = encoded_branch.get("diameter_mm", metadata.get("diameter_mm", 1.0))
        if isinstance(raw_diameter, bool) or not isinstance(raw_diameter, (int, float)):
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        diameter_mm = float(raw_diameter)
        raw_attachment_id = encoded_branch.get("attachment_id")
        if raw_attachment_id is not None and not isinstance(raw_attachment_id, str):
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        try:
            attachment_id = None if raw_attachment_id is None else UUID(raw_attachment_id)
        except ValueError as error:
            raise RuntimeError("Generated cable-group branch metadata is malformed.") from error
        if not math.isfinite(diameter_mm) or diameter_mm <= 0.0:
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        raw_pullback = encoded_branch.get("pullback_mm", 0.0)
        raw_pullback_requested = encoded_branch.get("pullback_requested_mm", raw_pullback)
        raw_pullback_diameter = encoded_branch.get(
            "pullback_diameter_mm",
            diameter_mm * 0.75,
        )
        insulation_body_count = encoded_branch.get("insulation_body_count", 1)
        pullback_body_count = encoded_branch.get("pullback_body_count", 0)
        weld_body_count = encoded_branch.get("weld_body_count", 0)
        raw_weld_diameter = encoded_branch.get("weld_diameter_mm", 0.0)
        raw_weld_conductor_diameter = encoded_branch.get(
            "weld_conductor_diameter_mm",
            0.0,
        )
        raw_weld_length = encoded_branch.get("weld_length_mm", 0.0)
        if (
            isinstance(raw_pullback, bool)
            or not isinstance(raw_pullback, (int, float))
            or not math.isfinite(raw_pullback)
            or raw_pullback < 0.0
            or isinstance(raw_pullback_requested, bool)
            or not isinstance(raw_pullback_requested, (int, float))
            or not math.isfinite(raw_pullback_requested)
            or raw_pullback_requested < 0.0
            or isinstance(raw_pullback_diameter, bool)
            or not isinstance(raw_pullback_diameter, (int, float))
            or not math.isfinite(raw_pullback_diameter)
            or raw_pullback_diameter <= 0.0
            or raw_pullback_diameter > diameter_mm
            or isinstance(insulation_body_count, bool)
            or insulation_body_count not in (0, 1)
            or isinstance(pullback_body_count, bool)
            or pullback_body_count not in (0, 1)
            or isinstance(weld_body_count, bool)
            or weld_body_count not in (0, 1)
            or isinstance(raw_weld_diameter, bool)
            or not isinstance(raw_weld_diameter, (int, float))
            or not math.isfinite(raw_weld_diameter)
            or raw_weld_diameter < 0.0
            or isinstance(raw_weld_conductor_diameter, bool)
            or not isinstance(raw_weld_conductor_diameter, (int, float))
            or not math.isfinite(raw_weld_conductor_diameter)
            or raw_weld_conductor_diameter < 0.0
            or isinstance(raw_weld_length, bool)
            or not isinstance(raw_weld_length, (int, float))
            or not math.isfinite(raw_weld_length)
            or raw_weld_length < 0.0
            or (
                weld_body_count == 1
                and (
                    raw_weld_diameter <= 0.0
                    or raw_weld_conductor_diameter <= 0.0
                    or raw_weld_length <= 0.0
                )
            )
            or insulation_body_count + pullback_body_count + weld_body_count < 1
        ):
            raise RuntimeError("Generated cable-group branch metadata is malformed.")
        branches.append(
            ConnectionBranchRoute(
                _route_from_encoded(route_id, label, encoded),
                diameter_mm,
                attachment_id,
                float(raw_pullback),
                float(raw_pullback_requested),
                float(raw_pullback_diameter),
                insulation_body_count,
                pullback_body_count,
                weld_body_count,
                float(raw_weld_diameter),
                float(raw_weld_conductor_diameter),
                float(raw_weld_length),
            )
        )
    return tuple(branches)
