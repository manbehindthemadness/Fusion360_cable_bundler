"""
Benchmark safe end-profile-first ordering against the current ribbon fitter.

Run read-only through Fusion MCP or ``Python.Run`` in Text Commands while the
saved ``Wire creation tester v107`` document is active with no open command.
Every final in/out decision still uses ``BRepBody.pointContainment``. This
experiment neither creates geometry nor saves the design.
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
from cable_bundler.fusion.cable_solid_parts import ribbon_overlap
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point, world_to_harness
from cable_bundler.fusion.cable_solid_parts.sweep_geometry import route_tail_axis
from cable_bundler.fusion.ribbon_geometry import RibbonGuidePlane, ribbon_route_shape
from cable_bundler.routing import RoutePreview, Vector3
from experiments.experiment_ribbon_overlap_end_profile import _end_face, _project_to_face
from experiments.experiment_ribbon_overlap_line_probe import _inside_end_plane, _probe_point


class _CountingBody:
    """
    Count exact containment queries without changing the saved ribbon body.
    """

    def __init__(self, body: adsk.fusion.BRepBody) -> None:
        """
        Retain the native body for one deterministic fitting replay.
        """
        self.body = body
        self.queries = 0

    def pointContainment(self, point: adsk.core.Point3D) -> int:
        """
        Forward and count one native point-in-solid query.
        """
        self.queries += 1
        return self.body.pointContainment(point)


def _sorted_overlap_escapes(
    body: _CountingBody,
    face: adsk.fusion.BRepFace,
    route: RoutePreview,
    plane: RibbonGuidePlane,
    diameter_mm: float,
    transform: adsk.core.Matrix3D,
    profile_stats: dict[str, float],
) -> bool:
    """
    Check identical sample points, prioritizing 2D-profile predicted escapes.
    """
    axis = route_tail_axis(route)
    first, second = ribbon_overlap._radial_axes(axis)
    points: list[tuple[bool, Vector3]] = []
    for station in range(8):
        fraction = station / 7.0
        for angle in (None, *range(16)):
            point = _probe_point(route, axis, first, second, fraction, angle, diameter_mm)
            if not _inside_end_plane(point, plane, axis):
                continue
            started = perf_counter()
            projected = _project_to_face(fusion_point(point, transform), face)
            likely_inside = face.isPointOnFace(projected)
            profile_stats["calls"] += 1
            profile_stats["milliseconds"] += (perf_counter() - started) * 1000.0
            points.append((likely_inside, point))
    if not points:
        raise ValueError("A ribbon connection has no overlap inside its end plane.")
    points.sort(key=lambda item: item[0])
    for _likely_inside, point in points:
        result = body.pointContainment(fusion_point(point, transform))
        if result == adsk.fusion.PointContainment.PointOutsidePointContainment:
            return True
        if result not in (
            adsk.fusion.PointContainment.PointInsidePointContainment,
            adsk.fusion.PointContainment.PointOnPointContainment,
        ):
            raise RuntimeError("Fusion returned an unknown ribbon overlap classification.")
    return False


def _fitted_diameter_sorted(
    body: _CountingBody,
    face: adsk.fusion.BRepFace,
    route: RoutePreview,
    plane: RibbonGuidePlane,
    cap_mm: float,
    transform: adsk.core.Matrix3D,
    profile_stats: dict[str, float],
) -> float:
    """
    Replay the production bisection with only its exact-query order changed.
    """
    if not math.isfinite(cap_mm) or cap_mm <= 0.0:
        raise ValueError("A ribbon connection needs a positive end-face diameter.")

    def escapes(diameter_mm: float) -> bool:
        """
        Probe one candidate diameter with a cheap ordering prediction.
        """
        return _sorted_overlap_escapes(
            body, face, route, plane, diameter_mm, transform, profile_stats
        )

    if not escapes(cap_mm):
        return cap_mm
    if escapes(ribbon_overlap._MINIMUM_DIAMETER_MM):
        raise ValueError("A ribbon line has no usable circular connection overlap.")
    lower_mm = ribbon_overlap._MINIMUM_DIAMETER_MM
    upper_mm = cap_mm
    for _step in range(ribbon_overlap._MAXIMUM_BISECTION_STEPS):
        if upper_mm - lower_mm <= ribbon_overlap._DIAMETER_PRECISION_MM:
            break
        candidate_mm = (lower_mm + upper_mm) / 2.0
        if escapes(candidate_mm):
            upper_mm = candidate_mm
        else:
            lower_mm = candidate_mm
    return lower_mm


def run(_context: object) -> None:
    """
    Compare output, query count, and time on three representative saved roots.
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
        samples: list[dict[str, object]] = []
        transform = world_to_harness(design, harness)
        for index in sorted({0, len(branches) // 2, len(branches) - 1}):
            branch = branches[index]
            plane = planes.get(branch.start_connection_id)
            if plane is None:
                raise RuntimeError("The saved branch has no fitted guide plane.")
            face, _offset_mm = _end_face(body, plane, transform)
            route = by_id[branch.route_id]
            cap_mm = branch.diameter_mm or group.diameter_mm
            original = _CountingBody(body)
            started = perf_counter()
            original_mm = ribbon_overlap.fitted_ribbon_overlap_diameter(
                original, route, plane, cap_mm, transform
            )
            original_ms = (perf_counter() - started) * 1000.0
            ordered = _CountingBody(body)
            profile_stats = {"calls": 0.0, "milliseconds": 0.0}
            started = perf_counter()
            ordered_mm = _fitted_diameter_sorted(
                ordered, face, route, plane, cap_mm, transform, profile_stats
            )
            ordered_ms = (perf_counter() - started) * 1000.0
            samples.append(
                {
                    "route_id": str(branch.route_id),
                    "saved_diameter_mm": saved_by_id[branch.route_id],
                    "original_diameter_mm": original_mm,
                    "ordered_diameter_mm": ordered_mm,
                    "diameter_difference_mm": ordered_mm - original_mm,
                    "original_containment_calls": original.queries,
                    "ordered_containment_calls": ordered.queries,
                    "profile_calls": int(profile_stats["calls"]),
                    "profile_ms": round(profile_stats["milliseconds"], 1),
                    "original_ms": round(original_ms, 1),
                    "ordered_ms": round(ordered_ms, 1),
                }
            )
        print(
            "RIBBON_ORDERING_PROBE="
            + json.dumps(
                {
                    "document": document.name,
                    "samples": samples,
                    "all_exact": all(sample["diameter_difference_mm"] == 0.0 for sample in samples),
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
