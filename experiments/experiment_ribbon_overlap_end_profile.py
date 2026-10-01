"""
Compare a ribbon end-profile projection with native 3D containment.

Run read-only through Fusion MCP or ``Python.Run`` in Text Commands while the
saved ``Wire creation tester v107`` document is active and no command is open.
The probe does not change or save the design. It uses at most three branches
and stops after 30 seconds of classification work.
"""

from __future__ import annotations

import json
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
from cable_bundler.routing import RoutePreview
from experiments.experiment_ribbon_overlap_line_probe import _inside_end_plane, _probe_point

_MAX_PROBE_SECONDS = 30.0
_DIAMETER_FRACTIONS = (0.05, 0.25, 0.5, 0.75, 1.0)


def _local_plane_normal(
    plane: RibbonGuidePlane, transform: adsk.core.Matrix3D
) -> tuple[adsk.core.Point3D, tuple[float, float, float]]:
    """
    Transform the authored guide plane into the ribbon component's coordinates.
    """
    origin = fusion_point(plane.origin, transform)
    tip = fusion_point(plane.origin.translated(plane.normal, 10.0), transform)
    delta = (tip.x - origin.x, tip.y - origin.y, tip.z - origin.z)
    length = sum(value * value for value in delta) ** 0.5
    if length <= 1e-12:
        raise ValueError("The ribbon guide plane has no local normal.")
    return origin, tuple(value / length for value in delta)


def _end_face(
    body: adsk.fusion.BRepBody,
    plane: RibbonGuidePlane,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.fusion.BRepFace, float]:
    """
    Select the planar cap closest to the branch's authored ribbon end plane.
    """
    origin, normal = _local_plane_normal(plane, transform)
    candidates: list[tuple[float, adsk.fusion.BRepFace]] = []
    for face in body.faces:
        if face.geometry.objectType != adsk.core.Plane.classType():
            continue
        sample = face.pointOnFace
        distance = abs(
            (sample.x - origin.x) * normal[0]
            + (sample.y - origin.y) * normal[1]
            + (sample.z - origin.z) * normal[2]
        )
        candidates.append((distance, face))
    if not candidates:
        raise RuntimeError("The saved ribbon has no planar end face.")
    distance, face = min(candidates, key=lambda item: item[0])
    if distance > 0.01:
        raise RuntimeError("No ribbon end face matches the authored guide plane.")
    return face, distance * 10.0


def _project_to_face(point: adsk.core.Point3D, face: adsk.fusion.BRepFace) -> adsk.core.Point3D:
    """
    Orthogonally project a probe point onto the exact planar end profile.
    """
    plane = adsk.core.Plane.cast(face.geometry)
    if plane is None:
        raise RuntimeError("The selected ribbon end face is not planar.")
    origin = plane.origin
    normal = plane.normal
    norm_squared = normal.x**2 + normal.y**2 + normal.z**2
    if norm_squared <= 1e-20:
        raise RuntimeError("The ribbon end face has no usable normal.")
    scale = (
        (point.x - origin.x) * normal.x
        + (point.y - origin.y) * normal.y
        + (point.z - origin.z) * normal.z
    ) / norm_squared
    return adsk.core.Point3D.create(
        point.x - scale * normal.x,
        point.y - scale * normal.y,
        point.z - scale * normal.z,
    )


def _benchmark_branch(
    body: adsk.fusion.BRepBody,
    route: RoutePreview,
    plane: RibbonGuidePlane,
    cap_mm: float,
    saved_mm: float,
    transform: adsk.core.Matrix3D,
    deadline: float,
) -> dict[str, object]:
    """
    Compare planar profile membership and 3D membership on fitter samples.
    """
    face, face_offset_mm = _end_face(body, plane, transform)
    axis = route_tail_axis(route)
    first, second = _radial_axes(axis)
    diameters = sorted(
        {max(0.01, cap_mm * fraction) for fraction in _DIAMETER_FRACTIONS} | {saved_mm}
    )
    tested = 0
    false_inside = 0
    false_outside = 0
    on_surface = 0
    profile_ms = 0.0
    containment_ms = 0.0
    by_station: dict[int, dict[str, int]] = {}
    timed_out = False
    for diameter_mm in diameters:
        for station in range(8):
            fraction = station / 7.0
            for angle in (None, *range(16)):
                if perf_counter() >= deadline:
                    timed_out = True
                    break
                sample = _probe_point(route, axis, first, second, fraction, angle, diameter_mm)
                if not _inside_end_plane(sample, plane, axis):
                    continue
                point = fusion_point(sample, transform)
                started = perf_counter()
                projected = _project_to_face(point, face)
                profile_inside = face.isPointOnFace(projected)
                profile_ms += (perf_counter() - started) * 1000.0
                started = perf_counter()
                containment = body.pointContainment(point)
                containment_ms += (perf_counter() - started) * 1000.0
                on = adsk.fusion.PointContainment.PointOnPointContainment
                if containment == on:
                    on_surface += 1
                    continue
                actual_inside = (
                    containment == adsk.fusion.PointContainment.PointInsidePointContainment
                )
                tested += 1
                station_counts = by_station.setdefault(
                    station, {"tested": 0, "false_inside": 0, "false_outside": 0}
                )
                station_counts["tested"] += 1
                if profile_inside and not actual_inside:
                    false_inside += 1
                    station_counts["false_inside"] += 1
                elif not profile_inside and actual_inside:
                    false_outside += 1
                    station_counts["false_outside"] += 1
            if timed_out:
                break
        if timed_out:
            break
    return {
        "cap_diameter_mm": cap_mm,
        "saved_diameter_mm": saved_mm,
        "end_face_offset_mm": round(face_offset_mm, 6),
        "diameters_mm": diameters,
        "tested": tested,
        "on_surface": on_surface,
        "false_inside": false_inside,
        "false_outside": false_outside,
        "profile_ms": round(profile_ms, 1),
        "containment_ms": round(containment_ms, 1),
        "by_station": by_station,
        "timed_out": timed_out,
    }


def run(_context: object) -> None:
    """
    Replay profile-versus-solid checks without modifying the active design.
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
        deadline = perf_counter() + _MAX_PROBE_SECONDS
        samples: list[dict[str, object]] = []
        transform = world_to_harness(design, harness)
        for index in sorted({0, len(branches) // 2, len(branches) - 1}):
            branch = branches[index]
            plane = planes.get(branch.start_connection_id)
            if plane is None:
                raise RuntimeError("The saved branch has no fitted guide plane.")
            sample = _benchmark_branch(
                body,
                by_id[branch.route_id],
                plane,
                branch.diameter_mm or group.diameter_mm,
                saved_by_id[branch.route_id],
                transform,
                deadline,
            )
            samples.append({"route_id": str(branch.route_id), **sample})
            if sample["timed_out"]:
                break
        print(
            "RIBBON_END_PROFILE_PROBE="
            + json.dumps(
                {
                    "document": document.name,
                    "samples": samples,
                    "document_modified_before": modified_before,
                    "document_modified_after": document.isModified,
                },
                sort_keys=True,
            )
        )
        return
    raise RuntimeError("The active design has no generated Cable Group 5 ribbon.")


if __name__ == "__main__":
    run(None)
