"""
Probe a per-lane ribbon-end lobe as a reverse-loft exit profile.

Run through Fusion Text Commands ``Python.Run`` with ``Wire creation tester
v107`` active and no command open. All trials share one disposable, unsaved
scratch design; the source document is only read.
"""

from __future__ import annotations

import json
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point
from cable_bundler.fusion.cable_solid_parts.ribbon_builder import _lane_section_point
from cable_bundler.fusion.cable_solid_parts.sweep_geometry import route_tail_axis
from experiments.experiment_ribbon_overlap_end_profile import _project_to_face
from experiments.experiment_ribbon_reverse_loft import (
    _pairwise_overlaps,
    _profile,
    _reverse_samples,
    _source_cases,
    _SourceCase,
)

_INWARD_OVERLAP_MM = 0.02


def _lobe_profile(
    component: adsk.fusion.Component,
    origin: adsk.core.Point3D,
    normal: adsk.core.Vector3D,
    case: _SourceCase,
) -> adsk.fusion.Profile:
    """
    Close the authored top/bottom lane arcs with internal seam lines.

    The ribbon has one joined cap face, so this sketch partitions one lane's
    portion of it rather than selecting a pre-existing separate BRep face.
    """
    plane_input = component.constructionPlanes.createInput()
    plane = adsk.core.Plane.create(origin, normal)
    if not plane_input.setByPlane(plane):
        raise RuntimeError("Fusion rejected the lane-lobe section plane.")
    construction = component.constructionPlanes.add(plane_input)
    if construction is None:
        raise RuntimeError("Fusion could not construct the lane-lobe plane.")
    sketch = component.sketches.add(construction)
    if sketch is None:
        raise RuntimeError("Fusion could not sketch the lane lobe.")
    diameter = case.ribbon_diameter_mm
    radius = diameter / 2.0
    valley = radius * 0.60
    half_width = case.ribbon_lines * diameter / 2.0
    left_x = -half_width + case.line_index * diameter
    right_x = left_x + diameter
    middle_x = (left_x + right_x) / 2.0

    def point(across_mm: float, height_mm: float) -> adsk.core.Point3D:
        """
        Reuse the ribbon loft's exact lane/edge interpolation in scratch space.
        """
        projected = _lane_section_point(
            sketch,
            case.end_frame,
            case.lane_centers,
            case.end_fit.normals,
            case.end_fit,
            across_mm,
            height_mm,
            diameter,
            case.transform,
        )
        return adsk.core.Point3D.create(projected.x, projected.y, 0.0)

    top_left = point(left_x, valley)
    top_mid = point(middle_x, radius)
    top_right = point(right_x, valley)
    bottom_right = point(right_x, -valley)
    bottom_mid = point(middle_x, -radius)
    bottom_left = point(left_x, -valley)
    arcs = sketch.sketchCurves.sketchArcs
    lines = sketch.sketchCurves.sketchLines
    if arcs.addByThreePoints(top_left, top_mid, top_right) is None:
        raise RuntimeError("Fusion could not draw the top lane lobe.")
    if lines.addByTwoPoints(top_right, bottom_right) is None:
        raise RuntimeError("Fusion could not close the right lane seam.")
    if arcs.addByThreePoints(bottom_right, bottom_mid, bottom_left) is None:
        raise RuntimeError("Fusion could not draw the bottom lane lobe.")
    if lines.addByTwoPoints(bottom_left, top_left) is None:
        raise RuntimeError("Fusion could not close the left lane seam.")
    if sketch.profiles.count != 1:
        raise RuntimeError(
            f"The lane-lobe sketch has {sketch.profiles.count} profiles instead of one."
        )
    return sketch.profiles.item(0)


def _trial(
    component: adsk.fusion.Component, case: _SourceCase
) -> tuple[dict[str, object], adsk.fusion.BRepBody, adsk.fusion.BRepBody, adsk.fusion.BRepBody]:
    """
    Build and validate one loft, returning its transient and persistent bodies.
    """
    started_all = perf_counter()
    manager = adsk.fusion.TemporaryBRepManager.get()
    ribbon_copy = manager.copy(case.body)
    if ribbon_copy is None:
        raise RuntimeError("Fusion could not copy the source ribbon.")
    cap_plane = adsk.core.Plane.cast(case.face.geometry)
    if cap_plane is None:
        raise RuntimeError("The source ribbon end is not planar.")
    axis = route_tail_axis(case.route)
    local_end = fusion_point(case.route.curves[-1].end, case.transform)
    local_tip = fusion_point(case.route.curves[-1].end.translated(axis, 10.0), case.transform)
    inward = adsk.core.Vector3D.create(
        local_tip.x - local_end.x,
        local_tip.y - local_end.y,
        local_tip.z - local_end.z,
    )
    if not inward.normalize():
        raise RuntimeError("The branch has no inward loft direction.")
    origin = _project_to_face(case.center, case.face)
    origin.translateBy(
        adsk.core.Vector3D.create(
            inward.x * _INWARD_OVERLAP_MM / 10.0,
            inward.y * _INWARD_OVERLAP_MM / 10.0,
            inward.z * _INWARD_OVERLAP_MM / 10.0,
        )
    )
    samples = _reverse_samples(case.route)
    pre_import_ms = (perf_counter() - started_all) * 1000.0
    started = perf_counter()
    ribbon = component.bRepBodies.add(ribbon_copy)
    if ribbon is None:
        raise RuntimeError("Fusion could not import the ribbon copy.")
    ribbon_import_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    root = _lobe_profile(component, origin, cap_plane.normal, case)
    root_profile_ms = (perf_counter() - started) * 1000.0
    sections = [root]
    started = perf_counter()
    for point, tangent in samples[1:]:
        local_point = fusion_point(point, case.transform)
        local_tip = fusion_point(point.translated(tangent, 10.0), case.transform)
        normal = adsk.core.Vector3D.create(
            local_tip.x - local_point.x,
            local_tip.y - local_point.y,
            local_tip.z - local_point.z,
        )
        if not normal.normalize():
            raise RuntimeError("A sampled route section has no tangent.")
        sections.append(_profile(component, local_point, normal, case.cap_diameter_mm / 2.0))
    circular_profiles_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    loft_input = component.features.loftFeatures.createInput(
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    if loft_input is None:
        raise RuntimeError("Fusion could not define the lane-lobe loft.")
    for section in sections:
        loft_input.loftSections.add(section)
    loft_input.isSolid = True
    loft_setup_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    loft = component.features.loftFeatures.add(loft_input)
    loft_ms = (perf_counter() - started) * 1000.0
    candidates = (
        []
        if loft is None
        else [body for body in loft.bodies if body.entityToken != ribbon.entityToken]
    )
    if len(candidates) != 1:
        raise RuntimeError(f"The lane-lobe loft produced {len(candidates)} distinct bodies.")
    branch = candidates[0]
    started = perf_counter()
    target = manager.copy(ribbon)
    tool = manager.copy(branch)
    overlap = manager.copy(ribbon)
    overlap_tool = manager.copy(branch)
    if target is None or tool is None or overlap is None or overlap_tool is None:
        raise RuntimeError("Fusion could not copy bodies for Boolean validation.")
    boolean_copy_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    union_ok = manager.booleanOperation(target, tool, adsk.fusion.BooleanTypes.UnionBooleanType)
    union_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    overlap_ok = manager.booleanOperation(
        overlap, overlap_tool, adsk.fusion.BooleanTypes.IntersectionBooleanType
    )
    overlap_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    transient = manager.copy(branch)
    if transient is None:
        raise RuntimeError("Fusion could not preserve the lobe branch for pairwise checks.")
    transient_copy_ms = (perf_counter() - started) * 1000.0
    result: dict[str, object] = {
        "route_id": case.route_id,
        "line_index": case.line_index,
        "sections": len(sections),
        "pre_import_ms": round(pre_import_ms, 1),
        "ribbon_import_ms": round(ribbon_import_ms, 1),
        "root_profile_ms": round(root_profile_ms, 1),
        "circular_profiles_ms": round(circular_profiles_ms, 1),
        "loft_setup_ms": round(loft_setup_ms, 1),
        "loft_ms": round(loft_ms, 1),
        "branch_valid": branch.isValid and branch.isSolid and branch.volume > 0,
        "union_ok": union_ok,
        "union_lumps": target.lumps.count if union_ok else None,
        "boolean_copy_ms": round(boolean_copy_ms, 1),
        "union_ms": round(union_ms, 1),
        "overlap_ok": overlap_ok,
        "overlap_volume_cm3": round(overlap.volume, 9) if overlap_ok else None,
        "overlap_ms": round(overlap_ms, 1),
        "transient_copy_ms": round(transient_copy_ms, 1),
    }
    result["trial_total_ms"] = round((perf_counter() - started_all) * 1000.0, 1)
    return result, transient, ribbon, branch


def run(_context: object) -> None:
    """
    Probe every saved root, including the failed circular-origin case.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Wire creation tester v107":
        raise RuntimeError("Open Wire creation tester v107 before this probe.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    modified_before = document.isModified
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    started = perf_counter()
    source_started = perf_counter()
    cases = _source_cases(design)
    source_cases_ms = (perf_counter() - source_started) * 1000.0
    results: list[dict[str, object]] = []
    transient_branches: list[tuple[str, adsk.fusion.BRepBody]] = []
    document_started = perf_counter()
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not open the shared scratch design.")
    document_open_ms = (perf_counter() - document_started) * 1000.0
    try:
        scratch_design = adsk.fusion.Design.cast(application.activeProduct)
        if scratch_design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        scratch_design.designType = adsk.fusion.DesignTypes.DirectDesignType
        component = scratch_design.rootComponent
        for case in cases:
            try:
                result, transient, _ribbon, _branch = _trial(component, case)
                results.append(result)
                if (
                    result["branch_valid"]
                    and result["union_ok"]
                    and result["union_lumps"] == 1
                    and result["overlap_ok"]
                    and result["overlap_volume_cm3"] > 0
                ):
                    transient_branches.append((case.route_id, transient))
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                results.append(
                    {"route_id": case.route_id, "error": f"{type(error).__name__}: {error}"}
                )
    finally:
        close_started = perf_counter()
        if not scratch.close(False):
            raise RuntimeError("Fusion could not close the unsaved shared scratch design.")
        document_close_ms = (perf_counter() - close_started) * 1000.0
    pairwise = _pairwise_overlaps(transient_branches, cases[0].body)
    phase_names = (
        "pre_import_ms",
        "ribbon_import_ms",
        "root_profile_ms",
        "circular_profiles_ms",
        "loft_setup_ms",
        "loft_ms",
        "boolean_copy_ms",
        "union_ms",
        "overlap_ms",
        "transient_copy_ms",
    )
    phase_totals_ms = {
        name: round(sum(float(result.get(name, 0.0)) for result in results), 1)
        for name in phase_names
    }
    trial_total_ms = sum(float(result.get("trial_total_ms", 0.0)) for result in results)
    wall_ms = (perf_counter() - started) * 1000.0
    print(
        "RIBBON_LOBE_EXIT_PROBE="
        + json.dumps(
            {
                "source_document": document.name,
                "scratch_mode": "shared_document",
                "source_modified_before": modified_before,
                "source_modified_after": document.isModified,
                "passed": len(transient_branches),
                "source_cases_ms": round(source_cases_ms, 1),
                "document_open_ms": round(document_open_ms, 1),
                "document_close_ms": round(document_close_ms, 1),
                "trial_total_ms": round(trial_total_ms, 1),
                "phase_totals_ms": phase_totals_ms,
                "pairwise": pairwise,
                "unattributed_ms": round(
                    wall_ms
                    - source_cases_ms
                    - document_open_ms
                    - document_close_ms
                    - trial_total_ms
                    - float(pairwise["pairwise_ms"]),
                    1,
                ),
                "wall_ms": round(wall_ms, 1),
                "results": results,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
