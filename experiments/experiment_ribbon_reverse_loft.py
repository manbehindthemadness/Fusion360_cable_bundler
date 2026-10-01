"""
Test every Group 5 root as a reverse-sampled loft in unsaved scratch designs.

Run through Fusion Text Commands ``Python.Run`` with the saved
``Wire creation tester v107`` document active and no command open. The source
document is read-only; all construction occurs in a new document that is
closed without saving, including when the experiment raises.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain import loads
from cable_bundler.fusion import cable_solids
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point, world_to_harness
from cable_bundler.fusion.cable_solid_parts.sweep_geometry import route_tail_axis
from cable_bundler.fusion.ribbon_geometry import ribbon_route_shape
from cable_bundler.routing import RoutePreview, Vector3
from cable_bundler.routing.geometry import difference, magnitude, unit
from cable_bundler.routing.ribbon import RibbonFrame
from cable_bundler.routing.ribbon_shape import RibbonEndFit
from experiments.experiment_ribbon_overlap_end_profile import _end_face, _project_to_face

_RING_SAMPLES = 24
_INWARD_OVERLAP_MM = 0.02
_MIN_ROOT_RADIUS_MM = 0.05


@dataclass(frozen=True)
class _SourceCase:
    """
    Hold one saved root and the source geometry needed for a scratch loft.
    """

    body: adsk.fusion.BRepBody
    face: adsk.fusion.BRepFace
    route: RoutePreview
    center: adsk.core.Point3D
    cap_diameter_mm: float
    saved_diameter_mm: float
    root_offset_mm: float
    route_id: str
    transform: adsk.core.Matrix3D
    line_index: int
    ribbon_lines: int
    ribbon_diameter_mm: float
    end_frame: RibbonFrame
    lane_centers: tuple[Vector3, ...]
    end_fit: RibbonEndFit


def _source_cases(design: adsk.fusion.Design) -> tuple[_SourceCase, ...]:
    """
    Resolve every saved Group 5 root and its ribbon end profile once.
    """
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
            raise RuntimeError("The saved ribbon has no owning harness definition.")
        group = next(group for group in definition.cable_groups if group.cable_group_id == group_id)
        body = next(
            (
                candidate
                for candidate in occurrence.component.bRepBodies
                if "Discrete Ribbon" in candidate.name and candidate.isValid and candidate.isSolid
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
            UUID(branch["route_id"]): branch for branch in metadata["connection_branches"]
        }
        root_attachments = {
            (connection.connection_id, attachment.attachment_id)
            for connection in definition.connections
            for attachment in connection.attachments
            if attachment.parent_attachment_id is None
        }
        transform = world_to_harness(design, harness)
        cases: list[_SourceCase] = []
        branches = sorted(
            (
                leg
                for leg in legs
                if leg.cable_group_id == group_id
                and leg.is_connection_branch
                and (leg.start_connection_id, leg.attachment_id) in root_attachments
            ),
            key=lambda leg: str(leg.route_id),
        )
        for branch in branches:
            guide = planes.get(branch.start_connection_id)
            if guide is None:
                raise RuntimeError("A saved root has no ribbon end plane.")
            face, _offset_mm = _end_face(body, guide, transform)
            route = by_id[branch.route_id]
            saved_branch = saved_by_id[branch.route_id]
            line_number = int(saved_branch["ribbon_line_number"])
            fit = (
                shape.shape.start_fit
                if branch.start_connection_id == main.start_connection_id
                else shape.shape.end_fit
            )
            if fit is None or not 1 <= line_number <= len(fit.centers):
                raise RuntimeError("A saved root has no matching fitted ribbon lane center.")
            lane_center = fit.centers[line_number - 1]
            at_start = branch.start_connection_id == main.start_connection_id
            section_index = 0 if at_start else -1
            cases.append(
                _SourceCase(
                    body=body,
                    face=face,
                    route=route,
                    center=fusion_point(lane_center, transform),
                    cap_diameter_mm=branch.diameter_mm or group.diameter_mm,
                    saved_diameter_mm=float(saved_branch["diameter_mm"]),
                    root_offset_mm=magnitude(difference(lane_center, route.curves[-1].end)),
                    route_id=str(branch.route_id),
                    transform=transform,
                    line_index=line_number - 1,
                    ribbon_lines=group.ribbon_lines,
                    ribbon_diameter_mm=group.diameter_mm,
                    end_frame=shape.shape.frames[section_index],
                    lane_centers=tuple(lane[section_index] for lane in shape.shape.lanes),
                    end_fit=fit,
                )
            )
        if not cases:
            raise RuntimeError("The saved ribbon has no connection branches.")
        return tuple(cases)
    raise RuntimeError("The active design has no generated Cable Group 5 ribbon.")


def _root_radius(
    face: adsk.fusion.BRepFace, center: adsk.core.Point3D, cap_diameter_mm: float
) -> tuple[float, float]:
    """
    Fit a sampled planar circle with a 20% margin; this is not a proof of clearance.
    """
    plane = adsk.core.Plane.cast(face.geometry)
    if plane is None:
        raise RuntimeError("The ribbon end profile is not planar.")
    center = _project_to_face(center, face)
    normal = plane.normal
    nx, ny, nz = normal.x, normal.y, normal.z
    reference = (0.0, 0.0, 1.0) if abs(nz) < 0.9 else (1.0, 0.0, 0.0)
    first = (
        ny * reference[2] - nz * reference[1],
        nz * reference[0] - nx * reference[2],
        nx * reference[1] - ny * reference[0],
    )
    first_length = math.sqrt(sum(value * value for value in first))
    first = tuple(value / first_length for value in first)
    second = (
        ny * first[2] - nz * first[1],
        nz * first[0] - nx * first[2],
        nx * first[1] - ny * first[0],
    )
    if not face.isPointOnFace(center):
        raise RuntimeError("The branch root center misses the ribbon end profile.")

    def fits(radius_mm: float) -> bool:
        """
        Require every sampled perimeter point to stay on the end face.
        """
        for index in range(_RING_SAMPLES):
            angle = 2.0 * math.pi * index / _RING_SAMPLES
            point = adsk.core.Point3D.create(
                center.x
                + radius_mm * (first[0] * math.cos(angle) + second[0] * math.sin(angle)) / 10.0,
                center.y
                + radius_mm * (first[1] * math.cos(angle) + second[1] * math.sin(angle)) / 10.0,
                center.z
                + radius_mm * (first[2] * math.cos(angle) + second[2] * math.sin(angle)) / 10.0,
            )
            if not face.isPointOnFace(point):
                return False
        return True

    low_mm = 0.0
    high_mm = cap_diameter_mm / 2.0
    for _step in range(8):
        middle_mm = (low_mm + high_mm) / 2.0
        if fits(middle_mm):
            low_mm = middle_mm
        else:
            high_mm = middle_mm
    return low_mm * 0.8, low_mm


def _profile(
    component: adsk.fusion.Component,
    center: adsk.core.Point3D,
    normal: adsk.core.Vector3D,
    radius_mm: float,
) -> adsk.fusion.Profile:
    """
    Draw one circular section on a direct-modeling plane in scratch space.
    """
    plane = adsk.core.Plane.create(center, normal)
    plane_input = component.constructionPlanes.createInput()
    if not plane_input.setByPlane(plane):
        raise RuntimeError("Fusion rejected a reverse-loft section plane.")
    construction = component.constructionPlanes.add(plane_input)
    if construction is None:
        raise RuntimeError("Fusion could not create a reverse-loft section plane.")
    sketch = component.sketches.add(construction)
    if sketch is None:
        raise RuntimeError("Fusion could not create a reverse-loft section sketch.")
    sketch_center = sketch.modelToSketchSpace(center)
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(sketch_center, radius_mm / 10.0)
    if circle is None or sketch.profiles.count != 1:
        raise RuntimeError("Fusion could not create a circular reverse-loft section.")
    return sketch.profiles.item(0)


def _reverse_samples(route: RoutePreview) -> tuple[tuple[Vector3, Vector3], ...]:
    """
    Sample each cubic from the ribbon end back toward the external target.
    """
    samples: list[tuple[Vector3, Vector3]] = []
    for curve in reversed(route.curves):
        for parameter in (1.0, 0.75, 0.5, 0.25, 0.0):
            point = curve.point(parameter)
            if (
                samples
                and magnitude(
                    Vector3(
                        point.x - samples[-1][0].x,
                        point.y - samples[-1][0].y,
                        point.z - samples[-1][0].z,
                    )
                )
                < 1e-6
            ):
                continue
            samples.append((point, unit(curve.derivative(parameter))))
    return tuple(samples)


def _scratch_loft(
    application: adsk.core.Application,
    source_body: adsk.fusion.BRepBody,
    source_face: adsk.fusion.BRepFace,
    route: RoutePreview,
    center: adsk.core.Point3D,
    cap_diameter_mm: float,
    transform: adsk.core.Matrix3D,
) -> tuple[dict[str, object], adsk.fusion.BRepBody]:
    """
    Build and union a candidate in a new unsaved direct-modeling document.
    """
    experiment_started = perf_counter()
    manager = adsk.fusion.TemporaryBRepManager.get()
    body_copy = manager.copy(source_body)
    if body_copy is None:
        raise RuntimeError("Fusion could not copy the saved ribbon into scratch space.")
    started = perf_counter()
    radius_mm, planar_limit_mm = _root_radius(source_face, center, cap_diameter_mm)
    profile_fit_ms = (perf_counter() - started) * 1000.0
    if radius_mm < _MIN_ROOT_RADIUS_MM:
        raise RuntimeError(
            f"The end face has no usable lane-local circular origin "
            f"(sampled radius {planar_limit_mm:.5f} mm)."
        )
    cap_plane = adsk.core.Plane.cast(source_face.geometry)
    if cap_plane is None:
        raise RuntimeError("The ribbon end face has no plane geometry.")
    samples = _reverse_samples(route)
    axis = route_tail_axis(route)
    local_end = fusion_point(route.curves[-1].end, transform)
    local_axis_tip = fusion_point(route.curves[-1].end.translated(axis, 10.0), transform)
    inward = adsk.core.Vector3D.create(
        local_axis_tip.x - local_end.x,
        local_axis_tip.y - local_end.y,
        local_axis_tip.z - local_end.z,
    )
    inward.normalize()
    origin = _project_to_face(center, source_face)
    origin.translateBy(
        adsk.core.Vector3D.create(
            inward.x * _INWARD_OVERLAP_MM / 10.0,
            inward.y * _INWARD_OVERLAP_MM / 10.0,
            inward.z * _INWARD_OVERLAP_MM / 10.0,
        )
    )
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the isolated scratch design.")
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        component = design.rootComponent
        ribbon = component.bRepBodies.add(body_copy)
        if ribbon is None:
            raise RuntimeError("Fusion could not import the ribbon copy into scratch space.")
        sections = [_profile(component, origin, cap_plane.normal, radius_mm)]
        sampled_sections = samples[1:]
        for point, tangent in sampled_sections:
            local_point = fusion_point(point, transform)
            local_tip = fusion_point(point.translated(tangent, 10.0), transform)
            normal = adsk.core.Vector3D.create(
                local_tip.x - local_point.x,
                local_tip.y - local_point.y,
                local_tip.z - local_point.z,
            )
            if not normal.normalize():
                raise RuntimeError("A sampled route section has no tangent.")
            sections.append(_profile(component, local_point, normal, cap_diameter_mm / 2.0))
        loft_input = component.features.loftFeatures.createInput(
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        if loft_input is None:
            raise RuntimeError("Fusion could not define the reverse loft.")
        for section in sections:
            loft_input.loftSections.add(section)
        loft_input.isSolid = True
        started = perf_counter()
        loft = component.features.loftFeatures.add(loft_input)
        loft_ms = (perf_counter() - started) * 1000.0
        candidates = (
            []
            if loft is None
            else [
                candidate
                for candidate in loft.bodies
                if candidate.entityToken != ribbon.entityToken
            ]
        )
        if len(candidates) != 1:
            body_count = None if loft is None else loft.bodies.count
            raise RuntimeError(
                f"Fusion did not produce one distinct reverse-loft body "
                f"({len(sections)} sections, {len(samples)} route samples, "
                f"{body_count} feature bodies, {len(candidates)} distinct bodies)."
            )
        branch = candidates[0]
        branch_volume = branch.volume
        started = perf_counter()
        target = manager.copy(ribbon)
        tool = manager.copy(branch)
        if target is None or tool is None:
            raise RuntimeError("Fusion could not copy loft bodies for union validation.")
        union_ok = manager.booleanOperation(target, tool, adsk.fusion.BooleanTypes.UnionBooleanType)
        union_ms = (perf_counter() - started) * 1000.0
        started = perf_counter()
        intersection = manager.copy(ribbon)
        intersection_tool = manager.copy(branch)
        if intersection is None or intersection_tool is None:
            raise RuntimeError("Fusion could not copy loft bodies for overlap validation.")
        intersection_ok = manager.booleanOperation(
            intersection, intersection_tool, adsk.fusion.BooleanTypes.IntersectionBooleanType
        )
        intersection_ms = (perf_counter() - started) * 1000.0
        transient_branch = manager.copy(branch)
        if transient_branch is None:
            raise RuntimeError("Fusion could not preserve the branch for pairwise validation.")
        result = {
            "root_radius_mm": round(radius_mm, 5),
            "planar_limit_radius_mm": round(planar_limit_mm, 5),
            "profile_fit_ms": round(profile_fit_ms, 1),
            "sections": len(sections),
            "route_samples": len(samples),
            "loft_ms": round(loft_ms, 1),
            "branch_valid": branch.isValid and branch.isSolid and branch_volume > 0,
            "branch_volume_cm3": round(branch_volume, 6),
            "union_ms": round(union_ms, 1),
            "union_ok": union_ok,
            "union_lumps": target.lumps.count if union_ok else None,
            "intersection_ms": round(intersection_ms, 1),
            "intersection_ok": intersection_ok,
            "intersection_volume_cm3": round(intersection.volume, 9) if intersection_ok else None,
            "scratch_ms_before_close": round((perf_counter() - experiment_started) * 1000.0, 1),
        }
        return result, transient_branch
    finally:
        if not scratch.close(False):
            raise RuntimeError("Fusion could not close the unsaved scratch design.")


def _boxes_overlap(left: adsk.fusion.BRepBody, right: adsk.fusion.BRepBody) -> bool:
    """
    Reject distant branch pairs before native Boolean intersection checks.
    """
    first = left.boundingBox
    second = right.boundingBox
    return all(
        getattr(first.minPoint, coordinate) <= getattr(second.maxPoint, coordinate)
        and getattr(second.minPoint, coordinate) <= getattr(first.maxPoint, coordinate)
        for coordinate in ("x", "y", "z")
    )


def _pairwise_overlaps(
    branches: list[tuple[str, adsk.fusion.BRepBody]],
    ribbon: adsk.fusion.BRepBody,
) -> dict[str, object]:
    """
    Separate branch intersections hidden by the ribbon from exposed collisions.
    """
    started = perf_counter()
    manager = adsk.fusion.TemporaryBRepManager.get()
    candidates = 0
    overlaps: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for index, (left_id, left) in enumerate(branches):
        for right_id, right in branches[index + 1 :]:
            if not _boxes_overlap(left, right):
                continue
            candidates += 1
            try:
                target = manager.copy(left)
                tool = manager.copy(right)
                if target is None or tool is None:
                    raise RuntimeError("Fusion could not copy a branch pair.")
                if not manager.booleanOperation(
                    target, tool, adsk.fusion.BooleanTypes.IntersectionBooleanType
                ):
                    raise RuntimeError("Fusion rejected a branch-pair intersection.")
                volume_cm3 = target.volume
                if volume_cm3 > 1e-9:
                    exposed = manager.copy(target)
                    ribbon_copy = manager.copy(ribbon)
                    if exposed is None or ribbon_copy is None:
                        raise RuntimeError("Fusion could not copy a branch overlap and ribbon.")
                    if not manager.booleanOperation(
                        exposed, ribbon_copy, adsk.fusion.BooleanTypes.DifferenceBooleanType
                    ):
                        raise RuntimeError("Fusion rejected ribbon subtraction from an overlap.")
                    overlaps.append(
                        {
                            "left_route_id": left_id,
                            "right_route_id": right_id,
                            "volume_cm3": round(volume_cm3, 9),
                            "exposed_volume_cm3": round(exposed.volume, 9),
                        }
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                failures.append(
                    {
                        "left_route_id": left_id,
                        "right_route_id": right_id,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
    return {
        "pair_count": len(branches) * (len(branches) - 1) // 2,
        "aabb_candidates": candidates,
        "overlap_count": len(overlaps),
        "exposed_overlap_count": sum(
            1 for overlap in overlaps if overlap["exposed_volume_cm3"] > 1e-9
        ),
        "overlaps": overlaps,
        "failure_count": len(failures),
        "failures": failures,
        "pairwise_ms": round((perf_counter() - started) * 1000.0, 1),
    }


def run(_context: object) -> None:
    """
    Record each scratch loft independently, retaining failures for the batch report.
    """
    experiment_started = perf_counter()
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
    cases = _source_cases(design)
    results: list[dict[str, object]] = []
    transient_branches: list[tuple[str, adsk.fusion.BRepBody]] = []
    for case in cases:
        item: dict[str, object] = {
            "route_id": case.route_id,
            "cap_diameter_mm": case.cap_diameter_mm,
            "saved_diameter_mm": case.saved_diameter_mm,
            "root_offset_mm": round(case.root_offset_mm, 5),
        }
        try:
            result, transient = _scratch_loft(
                application,
                case.body,
                case.face,
                case.route,
                case.center,
                case.cap_diameter_mm,
                case.transform,
            )
            item.update(result)
            if (
                result["branch_valid"]
                and result["union_ok"]
                and result["union_lumps"] == 1
                and result["intersection_ok"]
                and result["intersection_volume_cm3"] > 0
            ):
                transient_branches.append((case.route_id, transient))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            item["error"] = f"{type(error).__name__}: {error}"
        results.append(item)
        print("RIBBON_REVERSE_LOFT_BRANCH=" + json.dumps(item, sort_keys=True))
    pairwise = _pairwise_overlaps(transient_branches, cases[0].body)
    print(
        "RIBBON_REVERSE_LOFT_PROBE="
        + json.dumps(
            {
                "source_document": document.name,
                "branch_count": len(cases),
                "passed": sum(
                    1
                    for item in results
                    if item.get("branch_valid")
                    and item.get("union_ok")
                    and item.get("union_lumps") == 1
                    and item.get("intersection_ok")
                    and item.get("intersection_volume_cm3", 0) > 0
                ),
                "wall_ms": round((perf_counter() - experiment_started) * 1000.0, 1),
                "pairwise": pairwise,
                "source_modified_before": modified_before,
                "source_modified_after": document.isModified,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
