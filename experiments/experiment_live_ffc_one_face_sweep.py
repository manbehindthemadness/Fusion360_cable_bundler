"""
Probe the saved FFC route with a single fitted-profile sweep.

Run through Fusion ``Python.Run`` with no command active. The saved source is
read only; each attempt lives in a new unsaved scratch left open for review.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.fusion.cable_solid_parts import ribbon_builder
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point
from cable_bundler.fusion.solid_ribbon import SolidRibbonPlan, SolidRibbonSection
from cable_bundler.routing import Vector3
from cable_bundler.routing.geometry import cross
from experiments.experiment_live_ffc_correspondence import _live_plan


def _midpoint(station: SolidRibbonSection) -> Vector3:
    """
    Locate the common centerline without changing lane order.
    """
    first, last = station.centers[0], station.centers[-1]
    return Vector3((first.x + last.x) / 2.0, (first.y + last.y) / 2.0, (first.z + last.z) / 2.0)


def _center_lanes(plan: SolidRibbonPlan, count: int) -> SolidRibbonPlan:
    """
    Keep the same planned centerline while reducing only the profile width.

    Diagnostic subsets are not valid replacement contact plans; their saved
    identities remain associated with the selected central lanes only.
    """
    total = len(plan.sections[0].centers)
    if count < 1 or count > total or (total - count) % 2:
        raise ValueError("The diagnostic FFC subset must be centered on the original lanes.")
    first = (total - count) // 2
    last = first + count
    sections = tuple(
        SolidRibbonSection(
            station.centers[first:last], station.normal, station.width, station.lobe_width_mm
        )
        for station in plan.sections
    )
    return SolidRibbonPlan(
        sections,
        plan.lanes[first:last],
        (plan.contact_ids[0][first:last], plan.contact_ids[1][first:last]),
        (plan.attachment_ids[0][first:last], plan.attachment_ids[1][first:last]),
        plan.contact_signature,
    )


def _station_subset(plan: SolidRibbonPlan, indices: tuple[int, ...]) -> SolidRibbonPlan:
    """
    Diagnose whether an ending-lead backtrack causes the sweep failure.
    """
    return SolidRibbonPlan(
        tuple(plan.sections[index] for index in indices),
        tuple(tuple(lane[index] for index in indices) for lane in plan.lanes),
        plan.contact_ids,
        plan.attachment_ids,
        plan.contact_signature,
    )


def _outline(
    lines: int, dimensions: FfcDimensions, thickness_mm: float
) -> tuple[tuple[float, float], ...]:
    """
    Sample smooth lands and grooves with the designated seam at the left edge.
    """
    half_width = lines * dimensions.pitch_mm / 2.0
    half_height = thickness_mm / 2.0
    top: list[tuple[float, float]] = [(-half_width, half_height)]
    for index in range(lines):
        center = (index - (lines - 1) / 2.0) * dimensions.pitch_mm
        half_trace = dimensions.trace_width_mm / 2.0
        top.extend(
            (center + fraction * half_trace, half_height)
            for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0)
        )
        if index < lines - 1:
            right_land = center + half_trace
            top.extend(
                (
                    right_land + dimensions.spacing_mm * fraction,
                    half_height - thickness_mm * 0.05 * depth_fraction,
                )
                for fraction, depth_fraction in ((0.25, 0.5), (0.5, 1.0), (0.75, 0.5))
            )
    top.append((half_width, half_height))
    bottom = [(across, -height) for across, height in reversed(top)]
    return ((-half_width, 0.0), *top, (half_width, 0.0), *bottom)


def _spline_path(
    component: adsk.fusion.Component,
    plan: SolidRibbonPlan,
    transform: adsk.core.Matrix3D,
    edge_offset_mm: float,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.Path]:
    """
    Interpolate the ordered station centers or one corresponding width edge.
    """
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.is3D = True
    sketch.name = "FFC sweep centerline" if not edge_offset_mm else "FFC sweep bank rail"
    points = adsk.core.ObjectCollection.create()
    previous: Vector3 | None = None
    for station in plan.sections:
        point = _midpoint(station).translated(station.width, edge_offset_mm)
        if (
            previous is not None
            and math.dist((point.x, point.y, point.z), (previous.x, previous.y, previous.z)) < 0.001
        ):
            continue
        points.add(sketch.modelToSketchSpace(fusion_point(point, transform)))
        previous = point
    if points.count < 2:
        raise RuntimeError("The FFC route has fewer than two distinct sweep stations.")
    spline = sketch.sketchCurves.sketchFittedSplines.add(points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the FFC sweep spine.")
    path = component.features.createPath(spline, False)
    if path is None:
        raise RuntimeError("Fusion could not create the FFC sweep path.")
    sketch.isLightBulbOn = False
    return sketch, path


def _profile(
    component: adsk.fusion.Component,
    plan: SolidRibbonPlan,
    dimensions: FfcDimensions,
    thickness_mm: float,
    transform: adsk.core.Matrix3D,
) -> tuple[adsk.fusion.Sketch, adsk.core.Point3D]:
    """
    Fit one closed section at the first contact bank and retain its seam point.
    """
    station = plan.sections[0]
    plane_input = component.constructionPlanes.createInput()
    guide = ribbon_builder.RibbonGuidePlane(_midpoint(station), station.normal)
    if not plane_input.setByPlane(ribbon_builder._direct_guide_plane(guide, transform)):
        raise RuntimeError("Fusion could not orient the first FFC contact section.")
    plane = component.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion could not make the FFC section plane.")
    plane.isLightBulbOn = False
    sketch = component.sketches.add(plane)
    sketch.name = "One-face FFC profile"
    fit_points = adsk.core.ObjectCollection.create()
    height_axis = cross(station.normal, station.width)
    origin = _midpoint(station)
    for across, height in _outline(len(station.centers), dimensions, thickness_mm):
        world = origin.translated(station.width, across).translated(height_axis, height)
        fit_points.add(sketch.modelToSketchSpace(fusion_point(world, transform)))
    spline = sketch.sketchCurves.sketchFittedSplines.add(fit_points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the FFC outline.")
    spline.isClosed = True
    if sketch.profiles.count != 1:
        raise RuntimeError("The fitted FFC outline did not form one profile.")
    profile = sketch.profiles.item(0)
    if profile.profileLoops.count != 1 or profile.profileLoops.item(0).profileCurves.count != 1:
        raise RuntimeError("Fusion split the fitted FFC outline.")
    sketch.isLightBulbOn = False
    return sketch, spline.fitPoints.item(0).worldGeometry


def _section_audit(
    body: adsk.fusion.BRepBody, plan: SolidRibbonPlan, transform: adsk.core.Matrix3D
) -> list[dict[str, int]]:
    """
    Reject hidden folding by intersecting three interior planned sections.
    """
    rows: list[dict[str, int]] = []
    for index in tuple(
        dict.fromkeys(
            (len(plan.sections) // 4, len(plan.sections) // 2, 3 * len(plan.sections) // 4)
        )
    ):
        station = plan.sections[index]
        point = fusion_point(_midpoint(station), transform)
        normal = adsk.core.Vector3D.create(station.normal.x, station.normal.y, station.normal.z)
        plane = adsk.core.Plane.create(point, normal)
        section = adsk.fusion.TemporaryBRepManager.get().planeIntersection(body, plane)
        if section is None:
            raise RuntimeError(f"The sweep has no section at station {index}.")
        rows.append({"station": index, "wires": section.wires.count, "edges": section.edges.count})
    return rows


def _case(
    design: adsk.fusion.Design,
    plan: SolidRibbonPlan,
    dimensions: FfcDimensions,
    thickness_mm: float,
    guide_rail: bool,
) -> dict[str, object]:
    """
    Build and audit one banked or unbanked candidate in an isolated component.
    """
    transform = adsk.core.Matrix3D.create()
    component = design.rootComponent.occurrences.addNewComponent(transform).component
    component.name = "FFC one-face sweep with rail" if guide_rail else "FFC one-face sweep free"
    row: dict[str, object] = {"guide_rail": guide_rail}
    try:
        _path_sketch, path = _spline_path(component, plan, transform, 0.0)
        profile_sketch, seam = _profile(component, plan, dimensions, thickness_mm, transform)
        profile = profile_sketch.profiles.item(0)
        row["profile_edges"] = profile.profileLoops.item(0).profileCurves.count
        row["profile_area_mm2"] = profile.areaProperties().area * 100.0
        sweep_input = component.features.sweepFeatures.createInput(
            profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        if guide_rail:
            _rail_sketch, rail = _spline_path(
                component,
                plan,
                transform,
                -len(plan.sections[0].centers) * dimensions.pitch_mm / 2.0,
            )
            sweep_input.guideRail = rail
            sweep_input.profileScaling = (
                adsk.fusion.SweepProfileScalingOptions.SweepProfileNoScalingOption
            )
        feature = component.features.sweepFeatures.add(sweep_input)
        if feature is None or feature.bodies.count != 1:
            code, detail = adsk.core.Application.get().getLastError()
            raise RuntimeError(f"Fusion rejected the sweep ({code}: {detail}).")
        body = feature.bodies.item(0)
        if not body.isSolid or body.faces.count != 3 or body.volume <= 0.0:
            raise RuntimeError(
                f"The sweep lacks a three-face one-side solid (faces={body.faces.count})."
            )
        sections = _section_audit(body, plan, transform)
        end = _midpoint(plan.sections[-1])
        expected = fusion_point(
            end.translated(
                plan.sections[-1].width, -len(plan.sections[-1].centers) * dimensions.pitch_mm / 2.0
            ),
            transform,
        )
        end_seam_gap_mm = min(
            seam_vertex.geometry.distanceTo(expected) * 10.0 for seam_vertex in body.vertices
        )
        row.update(
            {
                "result": "clean"
                if all(item["wires"] == 1 and item["edges"] == 1 for item in sections)
                else "section_split",
                "faces": body.faces.count,
                "volume_cm3": body.volume,
                "sections": sections,
                "expected_end_seam_vertex_gap_mm": end_seam_gap_mm,
                "start_seam": [seam.x, seam.y, seam.z],
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    return row


def _circle_case(
    design: adsk.fusion.Design, plan: SolidRibbonPlan, radius_mm: float
) -> dict[str, object]:
    """
    Separate spine validity from ribbon width, banking, and fitted contour.
    """
    transform = adsk.core.Matrix3D.create()
    component = design.rootComponent.occurrences.addNewComponent(transform).component
    component.name = f"FFC spine circular control r{radius_mm:g}mm"
    row: dict[str, object] = {"radius_mm": radius_mm}
    try:
        _path_sketch, path = _spline_path(component, plan, transform, 0.0)
        first = plan.sections[0]
        plane_input = component.constructionPlanes.createInput()
        guide = ribbon_builder.RibbonGuidePlane(_midpoint(first), first.normal)
        if not plane_input.setByPlane(ribbon_builder._direct_guide_plane(guide, transform)):
            raise RuntimeError("Fusion could not orient the circular control plane.")
        plane = component.constructionPlanes.add(plane_input)
        if plane is None:
            raise RuntimeError("Fusion could not make the circular control plane.")
        sketch = component.sketches.add(plane)
        center = sketch.modelToSketchSpace(fusion_point(_midpoint(first), transform))
        if sketch.sketchCurves.sketchCircles.addByCenterRadius(center, radius_mm / 10.0) is None:
            raise RuntimeError("Fusion could not draw the circular control section.")
        sweep_input = component.features.sweepFeatures.createInput(
            sketch.profiles.item(0), path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
        )
        sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        feature = component.features.sweepFeatures.add(sweep_input)
        if feature is None or feature.bodies.count != 1:
            code, detail = adsk.core.Application.get().getLastError()
            raise RuntimeError(f"Fusion rejected the circular control ({code}: {detail}).")
        body = feature.bodies.item(0)
        row.update(
            {
                "result": "solid" if body.isSolid else "non_solid",
                "faces": body.faces.count,
                "sections": _section_audit(body, plan, transform),
            }
        )
        sketch.isLightBulbOn = False
        plane.isLightBulbOn = False
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    return row


def run(_context: object) -> None:
    """
    Measure the actual saved FFC plan without modifying its document.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the FFC sweep probe.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("Open a saved Wire creation tester design before this probe.")
    design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if design is None:
        raise RuntimeError("The saved FFC source is not a Fusion design.")
    modified_before = source.isModified
    plan, thickness_mm, dimensions, group_id = _live_plan(design)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the one-face sweep scratch.")
    report: dict[str, object] = {
        "source": source.name,
        "group_id": group_id,
        "traces": len(plan.sections[0].centers),
        "stations": len(plan.sections),
        "thickness_mm": thickness_mm,
        "pitch_mm": dimensions.pitch_mm,
        "trace_width_mm": dimensions.trace_width_mm,
        "spacing_mm": dimensions.spacing_mm,
        "source_modified_before": modified_before,
        "cases": {},
    }
    try:
        scratch_design = adsk.fusion.Design.cast(application.activeProduct)
        if scratch_design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        scratch_design.designType = adsk.fusion.DesignTypes.DirectDesignType
        lane_counts = tuple(
            count for count in (1, 3, 5, 9, 13, 17, 19) if count <= len(plan.sections[0].centers)
        )
        for count in lane_counts:
            subset = _center_lanes(plan, count)
            report["cases"][f"free_{count}"] = _case(
                scratch_design, subset, dimensions, thickness_mm, False
            )
        report["cases"][f"rail_{len(plan.sections[0].centers)}"] = _case(
            scratch_design, plan, dimensions, thickness_mm, True
        )
        for radius_mm in (0.05, 0.25, 0.75):
            report["cases"][f"circle_r{radius_mm:g}"] = _circle_case(
                scratch_design, plan, radius_mm
            )
        trimmed_indices = (*range(len(plan.sections) - 4), len(plan.sections) - 1)
        trimmed = _station_subset(plan, trimmed_indices)
        report["trimmed_station_indices"] = list(trimmed_indices)
        report["cases"]["trimmed_circle_r0.05"] = _circle_case(scratch_design, trimmed, 0.05)
        for count in lane_counts:
            subset = _center_lanes(trimmed, count)
            report["cases"][f"trimmed_free_{count}"] = _case(
                scratch_design, subset, dimensions, thickness_mm, False
            )
            report["cases"][f"trimmed_rail_{count}"] = _case(
                scratch_design, subset, dimensions, thickness_mm, True
            )
        application.activeViewport.fit()
    finally:
        report["source_modified_after"] = source.isModified
        report["scratch_open"] = scratch.isValid
        output = (
            Path(ribbon_builder.__file__).resolve().parents[3]
            / "artifacts/verification/live_ffc_one_face_sweep.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("LIVE_FFC_ONE_FACE_SWEEP=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
