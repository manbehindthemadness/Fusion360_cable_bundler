"""
Benchmark line/face intersections against the saved ribbon's containment rule.

Run through the optional Fusion MCP executor with ``readOnly=true``, or use
``Python.Run`` in Fusion Text Commands, while the saved ``Wire creation tester
v107`` design is active and no command is open. The probe neither creates
geometry nor saves the document. It stops after three representative branches
or 30 seconds of live probes.
"""

from __future__ import annotations

import json
import math
from time import perf_counter
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion import cable_solids
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point, world_to_harness
from cable_bundler.fusion.cable_solid_parts.ribbon_overlap import _radial_axes
from cable_bundler.fusion.cable_solid_parts.sweep_geometry import route_tail_axis
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane, ribbon_route_shape
from cable_bundler.routing import RoutePreview, Vector3
from cable_bundler.routing.geometry import difference, dot, unit

_MINIMUM_DIAMETER_MM = 0.01
_MAX_INTERSECTION_SECONDS = 30.0
_FACE_BOX_MARGIN_CM = 0.0005
_HIT_MERGE_TOLERANCE = 1e-5


def _probe_point(
    route: RoutePreview,
    axis: Vector3,
    first: Vector3,
    second: Vector3,
    fraction: float,
    angle: int | None,
    diameter_mm: float,
) -> Vector3:
    """
    Reproduce one center or ring sample from the production overlap fitter.
    """
    center = route.curves[-1].end.translated(axis, diameter_mm * 0.5 * fraction)
    if angle is None:
        return center
    radius_mm = diameter_mm * 0.5 + max(0.01, diameter_mm * 0.01)
    radians = 2.0 * math.pi * angle / 16
    return center.translated(first, radius_mm * math.cos(radians)).translated(
        second, radius_mm * math.sin(radians)
    )


def _inside_end_plane(point: Vector3, plane: RibbonGuidePlane, axis: Vector3) -> bool:
    """
    Match the production fitter's inward end-plane eligibility check.
    """
    inward = unit(plane.normal)
    if dot(inward, axis) < 0.0:
        inward = Vector3(-inward.x, -inward.y, -inward.z)
    return dot(difference(point, plane.origin), inward) > 1e-6


def _box_intersects_segment(
    box: adsk.core.BoundingBox3D,
    start: adsk.core.Point3D,
    end: adsk.core.Point3D,
) -> bool:
    """
    Conservatively reject faces outside the finite probe trajectory.
    """
    return all(
        min(a, b) - _FACE_BOX_MARGIN_CM <= high and max(a, b) + _FACE_BOX_MARGIN_CM >= low
        for a, b, low, high in (
            (start.x, end.x, box.minPoint.x, box.maxPoint.x),
            (start.y, end.y, box.minPoint.y, box.maxPoint.y),
            (start.z, end.z, box.minPoint.z, box.maxPoint.z),
        )
    )


def _segment_parameter(
    start: adsk.core.Point3D,
    end: adsk.core.Point3D,
    hit: adsk.core.Point3D,
) -> float:
    """
    Project a surface hit onto the finite diameter-trajectory segment.
    """
    delta = (end.x - start.x, end.y - start.y, end.z - start.z)
    offset = (hit.x - start.x, hit.y - start.y, hit.z - start.z)
    length_squared = sum(component * component for component in delta)
    return sum(a * b for a, b in zip(delta, offset)) / length_squared


def _segment_hits(
    faces: tuple[adsk.fusion.BRepFace, ...],
    start: adsk.core.Point3D,
    end: adsk.core.Point3D,
) -> tuple[list[float], int, float]:
    """
    Intersect one finite trajectory with candidate bounded B-Rep faces.

    Surface intersection uses the underlying untrimmed surface; the face test
    then rejects hits outside the actual topological boundary.
    """
    line = adsk.core.Line3D.create(start, end)
    if line is None:
        raise RuntimeError("Fusion could not construct a probe line.")
    hits: list[float] = []
    calls = 0
    started = perf_counter()
    for face in faces:
        if not _box_intersects_segment(face.boundingBox, start, end):
            continue
        intersections = line.intersectWithSurface(face.geometry)
        calls += 1
        if intersections is None:
            raise RuntimeError("Fusion could not intersect a ribbon face.")
        for hit in intersections:
            parameter = _segment_parameter(start, end, hit)
            if -_HIT_MERGE_TOLERANCE <= parameter <= 1.0 + _HIT_MERGE_TOLERANCE:
                if face.isPointOnFace(hit):
                    hits.append(parameter)
    hits.sort()
    unique_hits: list[float] = []
    for hit in hits:
        if not unique_hits or hit - unique_hits[-1] > _HIT_MERGE_TOLERANCE:
            unique_hits.append(hit)
    return unique_hits, calls, (perf_counter() - started) * 1000.0


def _classification(
    body: adsk.fusion.BRepBody,
    point: Vector3,
    transform: adsk.core.Matrix3D,
) -> int:
    """
    Return the ribbon body's existing native point classification.
    """
    return body.pointContainment(fusion_point(point, transform))


def _benchmark_branch(
    body: adsk.fusion.BRepBody,
    route: RoutePreview,
    plane: RibbonGuidePlane,
    cap_mm: float,
    transform: adsk.core.Matrix3D,
    deadline: float,
) -> dict[str, object]:
    """
    Compare crossing parity with containment on bounded diameter trajectories.
    """
    axis = route_tail_axis(route)
    first, second = _radial_axes(axis)
    faces = tuple(body.faces)
    intervals = [(_MINIMUM_DIAMETER_MM, min(1.0, cap_mm))]
    if cap_mm > 1.0:
        intervals.append((1.0, cap_mm))
    segments = 0
    stationary_segments = 0
    face_calls = 0
    intersection_ms = 0.0
    containment_ms = 0.0
    containment_calls = 0
    crossings = 0
    disagreements = 0
    ambiguous = 0
    timed_out = False
    for station in range(8):
        fraction = station / 7.0
        for angle in (None, *range(16)):
            for minimum_mm, maximum_mm in intervals:
                if maximum_mm <= minimum_mm:
                    continue
                if perf_counter() >= deadline:
                    timed_out = True
                    break
                start_point = _probe_point(route, axis, first, second, fraction, angle, minimum_mm)
                end_point = _probe_point(route, axis, first, second, fraction, angle, maximum_mm)
                start = fusion_point(start_point, transform)
                end = fusion_point(end_point, transform)
                distance_squared = (
                    (end.x - start.x) ** 2 + (end.y - start.y) ** 2 + (end.z - start.z) ** 2
                )
                if distance_squared <= 1e-20:
                    stationary_segments += 1
                    continue
                hits, calls, elapsed_ms = _segment_hits(faces, start, end)
                segments += 1
                face_calls += calls
                intersection_ms += elapsed_ms
                crossings += len(hits)
                low_fraction, high_fraction = 0.25, 0.75
                low_mm = minimum_mm + (maximum_mm - minimum_mm) * low_fraction
                high_mm = minimum_mm + (maximum_mm - minimum_mm) * high_fraction
                low_point = _probe_point(route, axis, first, second, fraction, angle, low_mm)
                high_point = _probe_point(route, axis, first, second, fraction, angle, high_mm)
                if not all(
                    _inside_end_plane(point, plane, axis) for point in (low_point, high_point)
                ):
                    ambiguous += 1
                    continue
                validation_started = perf_counter()
                low = _classification(body, low_point, transform)
                high = _classification(body, high_point, transform)
                containment_ms += (perf_counter() - validation_started) * 1000.0
                containment_calls += 2
                on = adsk.fusion.PointContainment.PointOnPointContainment
                if low == on or high == on:
                    ambiguous += 1
                    continue
                crossing_count = sum(low_fraction < hit < high_fraction for hit in hits)
                if (low != high) != bool(crossing_count % 2):
                    disagreements += 1
            if timed_out:
                break
        if timed_out:
            break
    return {
        "segments": segments,
        "stationary_segments": stationary_segments,
        "face_count": len(faces),
        "face_intersection_calls": face_calls,
        "intersection_ms": round(intersection_ms, 1),
        "containment_validation_calls": containment_calls,
        "containment_validation_ms": round(containment_ms, 1),
        "boundary_crossings": crossings,
        "parity_disagreements": disagreements,
        "ambiguous": ambiguous,
        "timed_out": timed_out,
    }


def run(_context: object) -> None:
    """
    Probe three saved branches and report whether the document stayed untouched.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Wire creation tester v107":
        raise RuntimeError("Open the saved Wire creation tester v107 design first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before probing geometry.")
    modified_before = document.isModified
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    definitions = tuple(
        (adsk.fusion.Component.cast(attribute.parent), loads(attribute.value))
        for attribute in design.findAttributes("kev0.cable_bundler", "harness_definition")
    )
    for occurrence in design.rootComponent.allOccurrences:
        if "Cable Group 5" not in occurrence.component.name:
            continue
        attribute = occurrence.component.attributes.itemByName(
            "kev0.cable_bundler", "generated_cable_group"
        )
        if attribute is None:
            continue
        metadata = json.loads(attribute.value)
        group_id = UUID(metadata["cable_group_id"])
        harness, definition = next(
            (
                (component, saved)
                for component, saved in definitions
                if component is not None
                and any(group.cable_group_id == group_id for group in saved.cable_groups)
            ),
            (None, None),
        )
        if harness is None or definition is None:
            raise RuntimeError("The generated ribbon has no owning harness definition.")
        group = next(group for group in definition.cable_groups if group.cable_group_id == group_id)
        body = next(
            (
                body
                for body in occurrence.component.bRepBodies
                if "Discrete Ribbon" in body.name and body.isValid and body.isSolid
            ),
            None,
        )
        if body is None:
            raise RuntimeError("The saved ribbon body is unavailable.")
        _routes, legs, by_id = cable_solids._solve_complete_group_routes(design, definition, None)
        main = next(
            leg for leg in legs if leg.cable_group_id == group_id and not leg.is_connection_branch
        )
        shape = ribbon_route_shape(
            design, definition, main, by_id[main.route_id], group.ribbon_lines, group.diameter_mm
        )
        planes = {
            main.start_connection_id: shape.guide_planes[0],
            main.end_connection_id: shape.guide_planes[1],
        }
        saved_by_id = {
            UUID(branch["route_id"]): float(branch["diameter_mm"])
            for branch in metadata["connection_branches"]
        }
        branches = sorted(
            (leg for leg in legs if leg.cable_group_id == group_id and leg.is_connection_branch),
            key=lambda leg: saved_by_id[leg.route_id],
        )
        if not branches:
            raise RuntimeError("The saved ribbon has no connection branches.")
        deadline = perf_counter() + _MAX_INTERSECTION_SECONDS
        samples: list[dict[str, object]] = []
        transform = world_to_harness(design, harness)
        for index in sorted({0, len(branches) // 2, len(branches) - 1}):
            branch = branches[index]
            plane = planes.get(branch.start_connection_id)
            if plane is None:
                raise RuntimeError("The saved branch has no fitted guide plane.")
            result = _benchmark_branch(
                body,
                by_id[branch.route_id],
                plane,
                branch.diameter_mm or group.diameter_mm,
                transform,
                deadline,
            )
            samples.append({"route_id": str(branch.route_id), **result})
            if result["timed_out"]:
                break
        report = "RIBBON_LINE_PROBE=" + json.dumps(
            {
                "document": document.name,
                "samples": samples,
                "document_modified_before": modified_before,
                "document_modified_after": document.isModified,
            },
            sort_keys=True,
        )
        print(report)
        return
    raise RuntimeError("The active design has no generated Cable Group 5 ribbon.")


if __name__ == "__main__":
    run(None)
