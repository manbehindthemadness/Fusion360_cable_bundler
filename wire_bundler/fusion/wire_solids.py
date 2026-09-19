"""
Build persistent wire-group solids from the exact curves used by previews.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ..application import WireGroupRouteLeg
from ..domain import (
    HarnessDefinition,
    WireAppearanceReference,
    WireColor,
    WireGroupDefinition,
    WireMaterialSettings,
    WireStripe,
    validate_harness,
)
from ..routing import (
    CubicBezier,
    RoutePreview,
    StripeContinuation,
    StripeMeshResult,
    Vector3,
    build_continuous_stripe_mesh,
    tightest_bend,
)
from ..routing.geometry import cross, difference, magnitude
from .harness_gateway import ATTRIBUTE_GROUP
from .route_preview import solve_wire_group_centerlines

GENERATED_WIRE_GROUP_ATTRIBUTE = "generated_wire_group"
GENERATED_STRIPE_GROUP_ID = "kev0.wire_bundler.generated_wire_stripes"
_JUNCTION_TOLERANCE_MM = 1e-6


@dataclass(frozen=True)
class _RouteSweepSegment:
    """
    Retain logical-route ownership for one junction-bounded sweep segment.
    """

    route: RoutePreview
    source_route_index: int
    segment_index: int
    segment_count: int


def generate_wire_group_solids(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
    replace_existing: bool = False,
    notices: Optional[list[str]] = None,
) -> int:
    """
    Build one multi-body component per wire group before replacing managed output.
    """
    issues = validate_harness(definition)
    if issues:
        raise ValueError(
            "Cannot generate wire groups: " + "; ".join(issue.message for issue in issues)
        )
    if not definition.wire_groups:
        raise ValueError("Create at least one wire group before generating solids.")
    previous = generated_wire_group_occurrences(harness)
    if previous and not replace_existing:
        raise ValueError(
            "Generated solids already exist; confirm rebuilding before replacing them."
        )
    routes, legs = solve_wire_group_centerlines(design, definition, notices)
    routes_by_id = {route.wire_id: route for route in routes}
    if not routes or set(routes_by_id) != {leg.route_id for leg in legs}:
        raise ValueError("Every wire group must have complete route geometry before generation.")
    legs_by_group: dict[UUID, list[tuple[WireGroupRouteLeg, RoutePreview]]] = {}
    for leg in legs:
        legs_by_group.setdefault(leg.wire_group_id, []).append((leg, routes_by_id[leg.route_id]))
    local_transform = _world_to_harness(design, harness)
    created: list[adsk.fusion.Occurrence] = []
    try:
        for group_index, group in enumerate(definition.wire_groups):
            group_legs = legs_by_group.get(group.wire_group_id, [])
            if not group_legs:
                raise ValueError(f"Wire Group {group_index + 1} has no route legs.")
            occurrence = harness.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            if occurrence is None:
                raise RuntimeError(
                    f"Fusion could not create a component for Wire Group {group_index + 1}."
                )
            created.append(occurrence)
            try:
                build_wire_group_solid(
                    occurrence.component,
                    group,
                    group_index,
                    tuple(route for _leg, route in group_legs),
                    local_transform,
                    definition.harness_id,
                    definition.wire_group_materials(group),
                    design,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Wire Group {group_index + 1} could not be generated: {error}"
                ) from error
        for occurrence in previous:
            if not occurrence.deleteMe():
                raise RuntimeError("Fusion could not remove old generated wire-group geometry.")
    except Exception as error:
        for occurrence in reversed(created):
            if occurrence.isValid and not occurrence.deleteMe():
                raise RuntimeError(
                    "Fusion could not clean incomplete grouped-wire geometry; undo this command."
                ) from error
        raise
    return len(created)


def generated_wire_group_occurrences(
    harness: adsk.fusion.Component,
) -> tuple[adsk.fusion.Occurrence, ...]:
    """
    Find direct children explicitly marked as generated wire-group output.
    """
    return tuple(
        occurrence
        for occurrence in harness.occurrences
        if occurrence.component.attributes.itemByName(
            ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE
        )
        is not None
    )


def generated_wire_group_bodies(
    root: adsk.fusion.Component,
    harness: adsk.fusion.Component,
    wire_group_ids: tuple[UUID, ...],
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Resolve root-context bodies for persistent wire-group identities.

    Malformed metadata is ignored so palette hover remains a harmless,
    best-effort operation.
    """
    selected_ids = {str(group_id) for group_id in wire_group_ids}
    bodies: list[adsk.fusion.BRepBody] = []
    for occurrence in generated_wire_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE)
        if attribute is None:
            continue
        try:
            group_id = json.loads(attribute.value).get("wire_group_id")
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
        if group_id not in selected_ids:
            continue
        bodies.extend(_root_context_bodies(root, component))
    return tuple(bodies)


def _root_context_bodies(
    root: adsk.fusion.Component,
    component: adsk.fusion.Component,
) -> tuple[adsk.fusion.BRepBody, ...]:
    """
    Return every body proxy for a generated component in root assembly context.
    """
    bodies: list[adsk.fusion.BRepBody] = []
    root_occurrences = root.allOccurrencesByComponent(component)
    for occurrence_index in range(root_occurrences.count):
        root_occurrence = root_occurrences.item(occurrence_index)
        if root_occurrence is None:
            continue
        for body_index in range(root_occurrence.bRepBodies.count):
            body = root_occurrence.bRepBodies.item(body_index)
            if body is not None:
                bodies.append(body)
    return tuple(bodies)


def clear_wire_solids(harness: adsk.fusion.Component) -> int:
    """
    Delete direct child components marked as generated wire output.

    Callers should invoke this inside a native Fusion command transaction so a
    failed deletion rolls the complete operation back and Undo can restore it.
    """
    occurrences = generated_wire_group_occurrences(harness)
    for occurrence in occurrences:
        if not occurrence.deleteMe():
            raise RuntimeError("Fusion could not delete a generated wire component.")
    return len(occurrences)


def apply_wire_group_materials(
    design: adsk.fusion.Design,
    harness: adsk.fusion.Component,
    definition: HarnessDefinition,
) -> int:
    """
    Apply resolved materials to existing generated wire-group components.

    Material changes do not rebuild route solids. Stored component-local leg
    curves are reused to replace stripe presentation over the grouped bodies.
    """
    groups = {group.wire_group_id: group for group in definition.wire_groups}
    applied = 0
    for occurrence in generated_wire_group_occurrences(harness):
        component = occurrence.component
        attribute = component.attributes.itemByName(ATTRIBUTE_GROUP, GENERATED_WIRE_GROUP_ATTRIBUTE)
        if attribute is None:
            continue
        try:
            metadata = json.loads(attribute.value)
            group_id = UUID(metadata["wire_group_id"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("A generated wire group has invalid identity metadata.") from error
        group = groups.get(group_id)
        if group is None:
            continue
        materials = definition.wire_group_materials(group)
        bodies = component.bRepBodies
        if bodies.count == 0:
            raise RuntimeError(f"Generated Wire Group {group_id} has no bodies to color.")
        appearance = _wire_appearance(design, materials.main_color, materials.appearance)
        for body_index in range(bodies.count):
            body = bodies.item(body_index)
            if body is not None:
                body.appearance = appearance
        routes = _group_routes_from_metadata(metadata)
        if not routes and materials.stripes:
            raise RuntimeError(
                "Generated wire-group metadata has no routes for applying stripe patterns."
            )
        _replace_group_stripe_graphics(
            component,
            routes,
            materials.stripes,
            group.diameter_mm / 2.0,
            group_id,
        )
        metadata.update(_material_metadata(materials))
        attribute.value = json.dumps(metadata, sort_keys=True)
        applied += 1
    return applied


def _world_to_harness(
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


def _point(point: Vector3, transform: adsk.core.Matrix3D) -> adsk.core.Point3D:
    """
    Convert solver millimeters into Fusion centimeters and harness-local coordinates.
    """
    result = adsk.core.Point3D.create(point.x / 10, point.y / 10, point.z / 10)
    if not result.transformBy(transform):
        raise RuntimeError("Could not transform a wire control point.")
    return result


def _route_in_component_space(
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
        transformed = _point(point, transform)
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
    return RoutePreview(route.wire_id, route.wire_number, points, curves)


def _route_metadata(route: RoutePreview) -> list[list[list[float]]]:
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
        raise RuntimeError("Generated wire route metadata is malformed.")
    curves: list[CubicBezier] = []
    for encoded_curve in encoded:
        if not isinstance(encoded_curve, list) or len(encoded_curve) != 4:
            raise RuntimeError("Generated wire route metadata is malformed.")
        points: list[Vector3] = []
        for encoded_point in encoded_curve:
            if not isinstance(encoded_point, list) or len(encoded_point) != 3:
                raise RuntimeError("Generated wire route metadata is malformed.")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in encoded_point
            ):
                raise RuntimeError("Generated wire route metadata is malformed.")
            points.append(Vector3(*(float(value) for value in encoded_point)))
        curves.append(CubicBezier(*points))
    if any(left.end != right.start for left, right in zip(curves, curves[1:])):
        raise RuntimeError("Generated wire route metadata is discontinuous.")
    route_points = (curves[0].start, *(curve.end for curve in curves))
    return RoutePreview(route_id, label, route_points, tuple(curves))


def _group_routes_from_metadata(metadata: dict[str, object]) -> tuple[RoutePreview, ...]:
    """
    Restore every exact component-local leg owned by a generated wire group.
    """
    encoded_legs = metadata.get("route_legs")
    if not isinstance(encoded_legs, list):
        raise RuntimeError("Generated wire-group route metadata is malformed.")
    routes: list[RoutePreview] = []
    for encoded_leg in encoded_legs:
        if not isinstance(encoded_leg, dict):
            raise RuntimeError("Generated wire-group route metadata is malformed.")
        try:
            route_id = UUID(encoded_leg["route_id"])
            label = encoded_leg["label"]
            encoded = encoded_leg["route_curves_mm"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Generated wire-group route metadata is malformed.") from error
        if not isinstance(label, str):
            raise RuntimeError("Generated wire-group route metadata is malformed.")
        routes.append(_route_from_encoded(route_id, label, encoded))
    return tuple(routes)


def _replace_group_stripe_graphics(
    component: adsk.fusion.Component,
    routes: tuple[RoutePreview, ...],
    stripes: tuple[WireStripe, ...],
    wire_radius_mm: float,
    wire_group_id: UUID,
) -> int:
    """
    Replace all leg-owned stripe meshes for one multi-body wire group.
    """
    groups = component.customGraphicsGroups
    for group_index in range(groups.count - 1, -1, -1):
        group = groups.item(group_index)
        if group is None or (
            group.id != GENERATED_STRIPE_GROUP_ID
            and not group.id.startswith(f"{GENERATED_STRIPE_GROUP_ID}:")
            and not group.name.endswith(" Solid Stripes")
        ):
            continue
        for child_index in range(group.count - 1, -1, -1):
            child = group.item(child_index)
            if child is not None and child.deleteMe() is False:
                raise RuntimeError("Fusion could not delete an obsolete wire-group stripe.")
        if group.deleteMe() is False:
            raise RuntimeError("Fusion could not delete obsolete wire-group stripe graphics.")
    if not stripes:
        return 0
    group = groups.add()
    if group is None:
        raise RuntimeError("Fusion did not create stripe graphics for a wire group.")
    group.id = f"{GENERATED_STRIPE_GROUP_ID}:{wire_group_id}"
    group.name = "Wire Group Solid Stripes"
    segments, start_junctions, end_junctions = _prepare_group_sweep_segments(routes)
    created = 0
    for stripe_index, stripe in enumerate(stripes):
        decorated_segments = _build_continuous_segment_stripes(
            segments,
            start_junctions,
            end_junctions,
            stripe,
            wire_radius_mm,
        )
        for segment, result in decorated_segments:
            if not result.vertices or not result.triangle_indices:
                continue
            coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
                [
                    coordinate / 10.0
                    for point in result.vertices
                    for coordinate in (point.x, point.y, point.z)
                ]
            )
            if coordinates is None:
                raise RuntimeError("Fusion did not create wire-group stripe coordinates.")
            stripe_mesh = group.addMesh(coordinates, list(result.triangle_indices), [], [])
            if stripe_mesh is None:
                raise RuntimeError("Fusion did not draw a wire-group stripe.")
            stripe_mesh.name = (
                f"Wire Group Leg {segment.source_route_index + 1}"
                + (f" Segment {segment.segment_index + 1}" if segment.segment_count > 1 else "")
                + f" Stripe {stripe_index + 1}"
            )
            stripe_mesh.cullMode = adsk.fusion.CustomGraphicsCullModes.CustomGraphicsCullNone
            stripe_color = adsk.core.Color.create(
                stripe.color.red,
                stripe.color.green,
                stripe.color.blue,
                255,
            )
            stripe_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(stripe_color)
            if stripe_effect is None:
                raise RuntimeError("Fusion did not create a wire-group stripe color.")
            stripe_mesh.color = stripe_effect
            created += 1
    return created


def _build_continuous_segment_stripes(
    segments: tuple[_RouteSweepSegment, ...],
    start_junctions: tuple[Optional[int], ...],
    end_junctions: tuple[Optional[int], ...],
    stripe: WireStripe,
    wire_radius_mm: float,
) -> tuple[tuple[_RouteSweepSegment, StripeMeshResult], ...]:
    """
    Propagate one stripe's boundary state through an oriented segment tree.
    """
    if not (len(segments) == len(start_junctions) == len(end_junctions)):
        raise RuntimeError("Wire-group stripe topology is inconsistent.")
    roots = {
        junction
        for junction in start_junctions
        if junction is not None and junction not in end_junctions
    }
    if len(segments) > 1 and len(roots) != 1:
        raise RuntimeError("Wire-group stripe segments do not have one root junction.")
    root_junction = next(iter(roots), None)
    junction_states: dict[int, StripeContinuation] = {}
    decorated: list[tuple[_RouteSweepSegment, StripeMeshResult]] = []
    pending = list(range(len(segments)))
    while pending:
        progressed = False
        for segment_index in pending:
            start_junction = start_junctions[segment_index]
            if (
                start_junction is not None
                and start_junction != root_junction
                and start_junction not in junction_states
            ):
                continue
            continuation = None if start_junction is None else junction_states.get(start_junction)
            result = build_continuous_stripe_mesh(
                segments[segment_index].route,
                stripe,
                wire_radius_mm,
                continuation,
            )
            if result.start is None or result.end is None:
                raise RuntimeError("Wire-group stripe segment has no continuation state.")
            if start_junction is not None:
                junction_states.setdefault(start_junction, result.start)
            end_junction = end_junctions[segment_index]
            if end_junction is not None:
                junction_states[end_junction] = result.end
            decorated.append((segments[segment_index], result))
            pending.remove(segment_index)
            progressed = True
            break
        if not progressed:
            raise RuntimeError("Wire-group stripe segments do not form one connected tree.")
    return tuple(decorated)


def _is_straight(curve: CubicBezier) -> bool:
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


def build_wire_group_solid(
    component: adsk.fusion.Component,
    group: WireGroupDefinition,
    group_index: int,
    routes: tuple[RoutePreview, ...],
    transform: adsk.core.Matrix3D,
    harness_id: UUID,
    materials: WireMaterialSettings,
    design: adsk.fusion.Design,
) -> None:
    """
    Sweep every deterministic group leg from its own path-normal profile.
    """
    if not routes:
        raise ValueError("A wire group requires at least one routed leg.")
    construction_segments, _start_junctions, _end_junctions = _prepare_group_sweep_segments(routes)
    local_routes = tuple(_route_in_component_space(route, transform) for route in routes)
    bodies: list[adsk.fusion.BRepBody] = []
    leg_lengths = [0.0] * len(routes)
    for segment in construction_segments:
        route = segment.route
        leg_number = segment.source_route_index + 1
        section_name = f"Wire Group Leg {leg_number} Segment {segment.segment_index + 1} Diameter"
        body, length_mm = _build_route_sweep(
            component,
            route,
            group.diameter_mm,
            transform,
            f"Wire Group Leg {leg_number} Segment {segment.segment_index + 1} Centerline",
            section_name,
            f"Wire Group Leg {leg_number} Segment {segment.segment_index + 1} Sweep",
        )
        body.name = f"Wire Group {group_index + 1} Leg {leg_number}"
        if segment.segment_count > 1:
            body.name += f" Segment {segment.segment_index + 1}"
        bodies.append(body)
        leg_lengths[segment.source_route_index] += length_mm
    if component.bRepBodies.count != len(construction_segments):
        raise RuntimeError("Fusion did not retain one solid body per wire-group segment.")
    total_length_mm = sum(leg_lengths)
    component.name = f"Wire Group {group_index + 1}_{total_length_mm:.2f}mm"
    appearance = _wire_appearance(design, materials.main_color, materials.appearance)
    for body in bodies:
        body.appearance = appearance
    _replace_group_stripe_graphics(
        component,
        local_routes,
        materials.stripes,
        group.diameter_mm / 2.0,
        group.wire_group_id,
    )
    metadata = json.dumps(
        {
            "harness_id": str(harness_id),
            "wire_group_id": str(group.wire_group_id),
            "diameter_mm": group.diameter_mm,
            "length_mm": total_length_mm,
            "route_legs": [
                {
                    "route_id": str(route.wire_id),
                    "label": route.wire_number,
                    "length_mm": length_mm,
                    "route_curves_mm": _route_metadata(route),
                }
                for route, length_mm in zip(local_routes, leg_lengths)
            ],
            **_material_metadata(materials),
        },
        sort_keys=True,
    )
    if (
        component.attributes.add(
            ATTRIBUTE_GROUP,
            GENERATED_WIRE_GROUP_ATTRIBUTE,
            metadata,
        )
        is None
    ):
        raise RuntimeError("Fusion could not store the generated wire-group identity.")


def _shared_route_endpoints(
    routes: tuple[RoutePreview, ...],
    tolerance_mm: float = _JUNCTION_TOLERANCE_MM,
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


def _prepare_group_sweep_segments(
    routes: tuple[RoutePreview, ...],
) -> tuple[
    tuple[_RouteSweepSegment, ...],
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
        _RouteSweepSegment(
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
) -> tuple[_RouteSweepSegment, ...]:
    """
    Split exact curves where another logical route terminates inside a route.
    """
    junction_points = _route_junction_points(routes)
    segments: list[_RouteSweepSegment] = []
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
                _RouteSweepSegment(
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
                    magnitude(difference(point, boundary)) <= _JUNCTION_TOLERANCE_MM
                    for boundary in _route_curve_boundaries(candidate)
                )
            }
            if not incident_routes or any(
                magnitude(difference(point, candidate)) <= _JUNCTION_TOLERANCE_MM
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
            magnitude(difference(curve.end, junction)) <= _JUNCTION_TOLERANCE_MM
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
            if magnitude(difference(point, junction)) <= _JUNCTION_TOLERANCE_MM
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


def _build_route_sweep(
    component: adsk.fusion.Component,
    route: RoutePreview,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
    centerline_name: str,
    section_name: str,
    sweep_name: str,
) -> tuple[adsk.fusion.BRepBody, float]:
    """
    Create one route sweep from a path-normal circular profile.
    """
    if not route.curves:
        raise ValueError("The smooth route contains no curves.")
    stage = "create centerline sketch"
    try:
        sketch = component.sketches.add(component.xYConstructionPlane)
        if sketch is None:
            raise RuntimeError("Fusion did not create the wire centerline sketch.")
        sketch.name = centerline_name
        curves = adsk.core.ObjectCollection.create()
        length_mm = 0.0
        for index, curve in enumerate(route.curves):
            stage = f"create centerline segment {index + 1}"
            points = [
                sketch.modelToSketchSpace(_point(point, transform))
                for point in (curve.start, curve.control_a, curve.control_b, curve.end)
            ]
            if _is_straight(curve):
                entity = sketch.sketchCurves.sketchLines.addByTwoPoints(points[0], points[3])
            else:
                entity = sketch.sketchCurves.sketchControlPointSplines.add(
                    points, adsk.fusion.SplineDegrees.SplineDegreeThree
                )
            if entity is None or not curves.add(entity):
                raise RuntimeError("Fusion could not create a wire centerline segment.")
            length_mm += entity.length * 10
        stage = "join centerline path"
        path = component.features.createPath(curves, False)
        if path is None:
            raise RuntimeError("Fusion could not join the ordered centerline segments.")
        stage = "define cross-section plane"
        plane_input = component.constructionPlanes.createInput()
        if not plane_input.setByDistanceOnPath(
            curves.item(0), adsk.core.ValueInput.createByReal(0)
        ):
            raise RuntimeError("Fusion could not orient the wire cross-section.")
        stage = "create cross-section plane"
        plane = component.constructionPlanes.add(plane_input)
        if plane is None:
            raise RuntimeError("Fusion did not create the wire cross-section plane.")
        plane.name = section_name
        stage = "create diameter sketch"
        section = component.sketches.add(plane)
        if section is None:
            raise RuntimeError("Fusion did not create the wire cross-section sketch.")
        section.name = section_name
        center = section.modelToSketchSpace(_point(route.curves[0].start, transform))
        circle = section.sketchCurves.sketchCircles.addByCenterRadius(center, diameter_mm / 20)
        if circle is None or section.profiles.count != 1:
            raise RuntimeError("Fusion could not create one circular sweep profile.")
        sweep_profile = section.profiles.item(0)
        if sweep_profile is None:
            raise RuntimeError("Fusion did not retain the circular sweep profile.")
        sweeps = component.features.sweepFeatures
        stage = "define sweep"
        sweep_input = sweeps.createInput(
            sweep_profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        stage = "create solid sweep"
        sweep = sweeps.add(sweep_input)
        if sweep is None or sweep.bodies.count != 1:
            raise RuntimeError("Fusion did not produce one wire solid.")
        body = sweep.bodies.item(0)
        if not body.isSolid or not math.isfinite(body.volume) or body.volume <= 0:
            raise RuntimeError("Fusion produced an invalid or empty wire solid.")
        sweep.name = sweep_name
        sketch.isLightBulbOn = False
        section.isLightBulbOn = False
        plane.isLightBulbOn = False
        return body, length_mm
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        if stage == "create solid sweep":
            bend = tightest_bend(route)
            if bend is not None:
                diagnostic = (
                    f"tightest sampled bend radius {bend.radius_mm:.3f} mm on centerline "
                    f"curve {bend.curve_index + 1} at t={bend.parameter:.3f}; "
                    f"wire radius {diameter_mm / 2:.3f} mm"
                )
                raise RuntimeError(f"{stage}: {error}; route diagnostic: {diagnostic}") from error
        raise RuntimeError(f"{stage}: {error}") from error


def _material_metadata(materials: WireMaterialSettings) -> dict[str, object]:
    """
    Serialize the resolved material values stored with generated output.
    """
    return {
        "insulation_material": materials.insulation_material,
        "main_color": materials.main_color.hex_rgb,
        "appearance": (
            None
            if materials.appearance is None
            else {
                "library_id": materials.appearance.library_id,
                "library_name": materials.appearance.library_name,
                "appearance_id": materials.appearance.appearance_id,
                "appearance_name": materials.appearance.appearance_name,
            }
        ),
        "conductor_material": materials.conductor_material,
        "manufacturer": materials.manufacturer,
        "part_number": materials.part_number,
        "notes": materials.notes,
        "stripes": [
            {
                "color": stripe.color.hex_rgb,
                "color_name": stripe.color.name,
                "width_mm": stripe.width_mm,
                "pattern": stripe.pattern.value,
                "angle_deg": stripe.angle_deg,
                "repeat_mm": stripe.repeat_mm,
            }
            for stripe in materials.stripes
        ],
    }


def _wire_appearance(
    design: adsk.fusion.Design,
    color: WireColor,
    reference: Optional[WireAppearanceReference] = None,
) -> adsk.core.Appearance:
    """
    Return a document-owned library appearance or opaque stored insulation color.

    Fusion's released appearance API requires copying a library appearance into
    the design before changing its ``opaque_albedo`` property.
    """
    name = (
        f"Wire Bundler {reference.library_name} · {reference.appearance_name} "
        f"[{reference.appearance_id}]"
        if reference is not None
        else f"Wire Bundler Insulation {color.hex_rgb}"
    )
    appearance = design.appearances.itemByName(name)
    if appearance is not None:
        return appearance
    application = adsk.core.Application.get()
    if reference is not None:
        library = application.materialLibraries.itemById(reference.library_id)
        if library is None:
            raise RuntimeError(
                f"Fusion appearance library '{reference.library_name}' is unavailable."
            )
        source = library.appearances.itemById(reference.appearance_id)
        if source is None:
            raise RuntimeError(
                f"Fusion appearance '{reference.appearance_name}' is unavailable in "
                f"'{reference.library_name}'."
            )
        appearance = design.appearances.addByCopy(source, name)
        if appearance is None:
            raise RuntimeError("Fusion could not copy the selected wire appearance.")
        return appearance
    library = application.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    if library is None:
        raise RuntimeError("Fusion's built-in appearance library is unavailable.")
    generic = library.appearances.itemById("Prism-129")
    if generic is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    appearance = design.appearances.addByCopy(generic, name)
    if appearance is None:
        raise RuntimeError("Fusion could not create the wire insulation appearance.")
    color_property = appearance.appearanceProperties.itemById("opaque_albedo")
    if color_property is None:
        raise RuntimeError("Fusion's wire appearance has no editable color property.")
    color_property.value = adsk.core.Color.create(color.red, color.green, color.blue, 255)
    return appearance
