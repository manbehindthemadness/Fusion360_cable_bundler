"""
Test whether an explicit endpoint tangent seats the live FFC sweep cap.

Run through Fusion's local script runner with the saved Wire creation tester
document open. All features and exact contact-face copies are placed in a
new unsaved scratch that remains open; the saved source is only read.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point
from cable_bundler.fusion.solid_ribbon import SOLID_RIBBON_LEAD_FRACTIONS, SolidRibbonPlan
from cable_bundler.routing import Vector3
from experiments.experiment_ffc_interface_contacts import (
    _add_contacts,
    _contact_copies,
    _definition_for_plan,
)
from experiments.experiment_live_ffc_correspondence import _live_plan
from experiments.experiment_live_ffc_one_face_sweep import (
    _midpoint,
    _profile,
    _section_audit,
    _spline_path,
    _station_subset,
)

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_end_tangent.json"
HANDLE_LENGTH_MM = 3.0
MODES = ("baseline", "center_tangent", "center_and_rail_tangent")


def _coordinates(point: adsk.core.Point3D) -> tuple[float, float, float]:
    """
    Convert a Fusion point to model millimeters.
    """
    return point.x * 10.0, point.y * 10.0, point.z * 10.0


def _constrain_end(
    sketch: adsk.fusion.Sketch,
    endpoint: Vector3,
    tangent: Vector3,
    transform: adsk.core.Matrix3D,
    handle_length_mm: float = HANDLE_LENGTH_MM,
) -> dict[str, object]:
    """
    Aim the final fitted-spline tangent handle along the contact normal.

    The free handle point is placed upstream of the contact; its length is
    fixed for this experiment rather than inferred from the route solver.
    """
    splines = sketch.sketchCurves.sketchFittedSplines
    if splines.count != 1:
        raise RuntimeError("Expected one centerline/rail spline.")
    spline = splines.item(0)
    fit = spline.fitPoints.item(spline.fitPoints.count - 1)
    handle = spline.activateTangentHandle(fit)
    if handle is None:
        raise RuntimeError("Fusion did not activate the end tangent handle.")
    target = endpoint.translated(tangent, -handle_length_mm)
    target_world = fusion_point(target, transform)
    start = handle.startSketchPoint
    end = handle.endSketchPoint
    if start is None or end is None:
        raise RuntimeError("The tangent handle has no movable endpoint.")
    fit_world = fit.worldGeometry
    moving = end if start.worldGeometry.distanceTo(fit_world) < 1e-6 else start
    current = moving.worldGeometry
    translation = adsk.core.Vector3D.create(
        target_world.x - current.x,
        target_world.y - current.y,
        target_world.z - current.z,
    )
    if not moving.move(translation):
        raise RuntimeError("Fusion could not move the tangent handle endpoint.")
    actual = moving.worldGeometry
    error_mm = actual.distanceTo(target_world) * 10.0
    if error_mm > 0.001:
        raise RuntimeError(f"End tangent handle missed its target by {error_mm:g} mm.")
    return {
        "fit_point_mm": _coordinates(fit_world),
        "handle_point_mm": _coordinates(actual),
        "handle_error_mm": error_mm,
        "handle_length_mm": handle_length_mm,
    }


def _end_audit(feature: adsk.fusion.SweepFeature, plan: SolidRibbonPlan) -> dict[str, object]:
    """
    Measure cap planarity and full-width separation from the target plane.
    """
    if feature.bodies.count != 1 or feature.endFaces.count != 1:
        raise RuntimeError("The FFC sweep did not provide one body and end cap.")
    cap = feature.endFaces.item(0)
    plane = adsk.core.Plane.cast(cap.geometry)
    if plane is None:
        raise RuntimeError("The FFC end cap is not planar.")
    station = plan.sections[-1]
    target = _midpoint(station)
    center = _coordinates(cap.centroid)
    delta = (center[0] - target.x, center[1] - target.y, center[2] - target.z)
    normal = station.normal
    signed_gap = delta[0] * normal.x + delta[1] * normal.y + delta[2] * normal.z
    cap_normal = plane.normal
    normal_dot = cap_normal.x * normal.x + cap_normal.y * normal.y + cap_normal.z * normal.z
    bounds = cap.boundingBox
    return {
        "target_center_mm": (target.x, target.y, target.z),
        "cap_center_mm": center,
        "signed_center_gap_mm": signed_gap,
        "absolute_center_gap_mm": abs(signed_gap),
        "cap_contact_normal_dot": normal_dot,
        "cap_bounds_mm": {
            "min": _coordinates(bounds.minPoint),
            "max": _coordinates(bounds.maxPoint),
        },
    }


def _case(
    design: adsk.fusion.Design,
    plan: SolidRibbonPlan,
    dimensions: FfcDimensions,
    thickness_mm: float,
    mode: str,
    *,
    rebuild_path: bool = False,
    use_rail: bool = True,
    handle_length_mm: float = HANDLE_LENGTH_MM,
) -> dict[str, object]:
    """
    Sweep the same trimmed route while changing only end-tangent control.
    """
    transform = adsk.core.Matrix3D.create()
    component = design.rootComponent.occurrences.addNewComponent(transform).component
    component.name = f"FFC contact-cap tangent · {mode}"
    row: dict[str, object] = {"mode": mode, "component": component.name}
    try:
        center_sketch, path = _spline_path(component, plan, transform, 0.0)
        if mode != "baseline":
            row["center_handle"] = _constrain_end(
                center_sketch,
                _midpoint(plan.sections[-1]),
                plan.sections[-1].normal,
                transform,
                handle_length_mm,
            )
        if rebuild_path:
            center_spline = center_sketch.sketchCurves.sketchFittedSplines.item(0)
            path = component.features.createPath(center_spline, False)
            if path is None:
                raise RuntimeError("Fusion could not rebuild the constrained center path.")
        profile_sketch, _seam = _profile(component, plan, dimensions, thickness_mm, transform)
        rail_sketch, rail = _spline_path(
            component,
            plan,
            transform,
            -len(plan.sections[0].centers) * dimensions.pitch_mm / 2.0,
        )
        if mode in (
            "center_and_rail_tangent",
            "rebuilt_center_and_rail",
            "rebuilt_both_short",
            "rebuilt_both_long",
            "full_route_both_tangents",
            "drop_reversing_end_station",
            "drop_two_end_stations",
            "contacts_and_main_route",
        ):
            endpoint = _midpoint(plan.sections[-1]).translated(
                plan.sections[-1].width,
                -len(plan.sections[-1].centers) * dimensions.pitch_mm / 2.0,
            )
            row["rail_handle"] = _constrain_end(
                rail_sketch,
                endpoint,
                plan.sections[-1].normal,
                transform,
                handle_length_mm,
            )
        if rebuild_path and use_rail:
            rail_spline = rail_sketch.sketchCurves.sketchFittedSplines.item(0)
            rail = component.features.createPath(rail_spline, False)
            if rail is None:
                raise RuntimeError("Fusion could not rebuild the constrained bank rail.")
        sweep_input = component.features.sweepFeatures.createInput(
            profile_sketch.profiles.item(0),
            path,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        if use_rail:
            sweep_input.guideRail = rail
        sweep_input.profileScaling = (
            adsk.fusion.SweepProfileScalingOptions.SweepProfileNoScalingOption
        )
        feature = component.features.sweepFeatures.add(sweep_input)
        if feature is None or feature.bodies.count != 1:
            code, detail = adsk.core.Application.get().getLastError()
            raise RuntimeError(f"Fusion rejected the constrained FFC sweep ({code}: {detail}).")
        body = feature.bodies.item(0)
        if not body.isSolid or body.faces.count != 3:
            raise RuntimeError("The constrained FFC sweep is not a one-face solid.")
        sections = _section_audit(body, plan, transform)
        row.update(
            {
                "result": "clean"
                if all(item["wires"] == 1 and item["edges"] == 1 for item in sections)
                else "section_split",
                "body_faces": body.faces.count,
                "sections": sections,
                "end_cap": _end_audit(feature, plan),
            }
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        row.update({"result": "failed", "error": str(error)})
    return row


def run(_context: object) -> None:
    """
    Retain three controlled end-tangent candidates and exact contact faces.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("Open the saved FFC source design first.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The source is not a Fusion design.")
    modified_before = source.isModified
    plan, thickness_mm, dimensions, group_id = _live_plan(source_design)
    indices = (*range(len(plan.sections) - 4), len(plan.sections) - 1)
    trimmed = _station_subset(plan, indices)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the endpoint-tangent scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The new scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows = [_case(design, trimmed, dimensions, thickness_mm, mode) for mode in MODES]
    definition = _definition_for_plan(source_design, group_id)
    contacts = _add_contacts(design, _contact_copies(source_design, definition, plan))
    application.activeViewport.fit()
    report = {
        "source": source.name,
        "source_modified_before": modified_before,
        "source_modified_after": source.isModified,
        "scratch": scratch.name,
        "cases": rows,
        "copied_contacts": len(contacts),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_END_TANGENT="
        + json.dumps(
            {
                "cases": [(row["mode"], row["result"]) for row in rows],
                "end_gaps_mm": [
                    row["end_cap"]["absolute_center_gap_mm"] if "end_cap" in row else None
                    for row in rows
                ],
                "source_modified_after": source.isModified,
                "report": str(OUTPUT),
            }
        )
    )


def run_retry(_context: object) -> None:
    """
    Retry only the two constrained candidates in the already-open scratch.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC tangent scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or not any(
        occurrence.component.name.startswith("FFC contact-cap tangent · baseline")
        for occurrence in design.rootComponent.occurrences
    ):
        raise RuntimeError("The active scratch is not the FFC tangent experiment.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    modified_before = source.isModified
    plan, thickness_mm, dimensions, _group_id = _live_plan(source_design)
    indices = (*range(len(plan.sections) - 4), len(plan.sections) - 1)
    trimmed = _station_subset(plan, indices)
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    report["first_attempt_errors"] = report["cases"][1:]
    report["cases"] = [
        report["cases"][0],
        *(_case(design, trimmed, dimensions, thickness_mm, mode) for mode in MODES[1:]),
    ]
    application.activeViewport.fit()
    report["source_modified_after"] = source.isModified
    if source.isModified != modified_before:
        raise RuntimeError("The saved FFC source changed during the retry.")
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_END_TANGENT_RETRY="
        + json.dumps(
            {
                "cases": [(row["mode"], row["result"]) for row in report["cases"]],
                "end_gaps_mm": [
                    row["end_cap"]["absolute_center_gap_mm"] if "end_cap" in row else None
                    for row in report["cases"]
                ],
                "report": str(OUTPUT),
            }
        )
    )


def run_repath(_context: object) -> None:
    """
    Compare rebuilt paths with and without the bank rail in the open scratch.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC tangent scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or not any(
        occurrence.component.name.startswith("FFC contact-cap tangent · baseline")
        for occurrence in design.rootComponent.occurrences
    ):
        raise RuntimeError("The active scratch is not the FFC tangent experiment.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    modified_before = source.isModified
    plan, thickness_mm, dimensions, _group_id = _live_plan(source_design)
    indices = (*range(len(plan.sections) - 4), len(plan.sections) - 1)
    trimmed = _station_subset(plan, indices)
    candidates = (
        ("rebuilt_center", True, HANDLE_LENGTH_MM),
        ("rebuilt_center_and_rail", True, HANDLE_LENGTH_MM),
        ("rebuilt_center_no_rail", False, HANDLE_LENGTH_MM),
        ("rebuilt_both_short", True, 1.0),
        ("rebuilt_both_long", True, 6.0),
    )
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    prior_rows = report.get("rebuilt_path_cases", [])
    completed = {row["mode"] for row in prior_rows}
    new_rows = [
        _case(
            design,
            trimmed,
            dimensions,
            thickness_mm,
            mode,
            rebuild_path=True,
            use_rail=use_rail,
            handle_length_mm=handle_length_mm,
        )
        for mode, use_rail, handle_length_mm in candidates
        if mode not in completed
    ]
    if source.isModified != modified_before:
        raise RuntimeError("The saved FFC source changed during the experiment.")
    rows = [*prior_rows, *new_rows]
    report["rebuilt_path_cases"] = rows
    report["source_modified_after"] = source.isModified
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.fit()
    print(
        "FFC_END_REPATH="
        + json.dumps(
            {
                "cases": [
                    (
                        row["mode"],
                        row["result"],
                        row.get("end_cap", {}).get("absolute_center_gap_mm"),
                        row.get("end_cap", {}).get("cap_contact_normal_dot"),
                        row.get("error"),
                    )
                    for row in rows
                ],
                "source_modified_after": source.isModified,
                "report": str(OUTPUT),
            }
        )
    )


def run_full_route(_context: object) -> None:
    """
    Try the complete live plan with both paths rebuilt after tangent control.
    """
    application = adsk.core.Application.get()
    scratch = application.activeDocument
    if scratch is None or scratch.isSaved or scratch.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC tangent scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or not any(
        occurrence.component.name.startswith("FFC contact-cap tangent · baseline")
        for occurrence in design.rootComponent.occurrences
    ):
        raise RuntimeError("The active scratch is not the FFC tangent experiment.")
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    modified_before = source.isModified
    plan, thickness_mm, dimensions, _group_id = _live_plan(source_design)
    candidates = (
        (
            "drop_reversing_end_station",
            tuple(index for index in range(len(plan.sections)) if index != 36),
        ),
        (
            "drop_two_end_stations",
            tuple(index for index in range(len(plan.sections)) if index not in (36, 37)),
        ),
        (
            "contacts_and_main_route",
            (
                0,
                *range(
                    len(SOLID_RIBBON_LEAD_FRACTIONS),
                    len(plan.sections) - len(SOLID_RIBBON_LEAD_FRACTIONS),
                ),
                len(plan.sections) - 1,
            ),
        ),
    )
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    prior_rows = report.get("conditioned_end_cases", [])
    completed = {row["mode"] for row in prior_rows}
    rows = [
        _case(
            design,
            _station_subset(plan, indices),
            dimensions,
            thickness_mm,
            name,
            rebuild_path=True,
        )
        for name, indices in candidates
        if name not in completed
    ]
    if source.isModified != modified_before:
        raise RuntimeError("The saved FFC source changed during the full-route experiment.")
    report["conditioned_end_cases"] = [*prior_rows, *rows]
    report["source_modified_after"] = source.isModified
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    application.activeViewport.fit()
    print(
        "FFC_FULL_ROUTE_TANGENT="
        + json.dumps(
            {
                "cases": [(row["mode"], row["result"], row.get("error")) for row in rows],
                "source_modified_after": source.isModified,
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    run(None)
