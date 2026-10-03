"""
Sweep planar PH quintic benchmark paths in an unsaved Fusion scratch design.

Run with ``Python.Run`` while no command is active. Leave the result open;
write machine-readable observations under ignored artifacts/verification.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_ph_quintic import benchmark_cases, ph_hermite_candidates


def _path_sketch(
    root: adsk.fusion.Component,
    name: str,
    controls_mm: tuple[complex, ...],
    offset_y_cm: float,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.SketchControlPointSpline]:
    """
    Add the exact six-control-point polynomial PH Bézier path on the XY plane.
    """
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = f"{name} PH path"
    points: list[adsk.core.Point3D] = []
    for control in controls_mm:
        world = adsk.core.Point3D.create(
            control.real / 10.0, offset_y_cm + control.imag / 10.0, 0.0
        )
        points.append(sketch.modelToSketchSpace(world))
    spline = sketch.sketchCurves.sketchControlPointSplines.add(
        points, adsk.fusion.SplineDegrees.SplineDegreeFive
    )
    if spline is None:
        raise RuntimeError("Fusion did not construct the degree-five control-point spline.")
    return sketch, spline


def _sweep_case(
    root: adsk.fusion.Component,
    name: str,
    controls_mm: tuple[complex, ...],
    offset_y_cm: float,
    wire_radius_mm: float,
    ribbon_width_mm: float | None = None,
) -> dict[str, object]:
    """
    Make one circular or rectangular sweep; retain its input sketches.
    """
    sketch, spline = _path_sketch(root, name, controls_mm, offset_y_cm)
    profile_sketch = root.sketches.add(root.yZConstructionPlane)
    profile_sketch.name = f"{name} profile"
    if ribbon_width_mm is None:
        center = profile_sketch.modelToSketchSpace(adsk.core.Point3D.create(0.0, offset_y_cm, 0.0))
        profile_sketch.sketchCurves.sketchCircles.addByCenterRadius(center, wire_radius_mm / 10.0)
    else:
        half_thickness_cm = 0.025
        half_width_cm = ribbon_width_mm / 20.0
        corners = (
            (offset_y_cm - half_thickness_cm, -half_width_cm),
            (offset_y_cm + half_thickness_cm, -half_width_cm),
            (offset_y_cm + half_thickness_cm, half_width_cm),
            (offset_y_cm - half_thickness_cm, half_width_cm),
        )
        sketch_points = tuple(
            profile_sketch.modelToSketchSpace(adsk.core.Point3D.create(0.0, y, z))
            for y, z in corners
        )
        for index in range(4):
            profile_sketch.sketchCurves.sketchLines.addByTwoPoints(
                sketch_points[index], sketch_points[(index + 1) % 4]
            )
    if profile_sketch.profiles.count != 1:
        raise RuntimeError(f"Expected one sweep profile; found {profile_sketch.profiles.count}.")
    path = root.features.createPath(spline, False)
    sweep_input = root.features.sweepFeatures.createInput(
        profile_sketch.profiles.item(0),
        path,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep = root.features.sweepFeatures.add(sweep_input)
    if sweep is None:
        raise RuntimeError("Fusion sweep returned no feature.")
    sweep.name = f"{name} PH sweep"
    bodies = [sweep.bodies.item(index) for index in range(sweep.bodies.count)]
    sketch.isLightBulbOn = False
    profile_sketch.isLightBulbOn = False
    return {
        "result": "solid" if len(bodies) == 1 and bodies[0].isSolid else "non_single_solid",
        "body_count": len(bodies),
        "body_volumes_cm3": [body.volume for body in bodies],
        "body_face_counts": [body.faces.count for body in bodies],
    }


def run(_context: object) -> None:
    """
    Create seven separated cases, including two mathematically rejected controls.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create an unsaved PH sweep scratch design.")
    report: dict[str, object] = {"document": scratch.name, "cases": []}
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The active scratch is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        for case_index, case in enumerate(benchmark_cases()):
            entry: dict[str, object] = {"name": case.name, "branch": 0}
            report["cases"].append(entry)
            try:
                curve = ph_hermite_candidates(case)[0]
                entry.update(
                    _sweep_case(
                        root,
                        case.name,
                        curve.controls,
                        case_index * 15.0,
                        case.wire_radius_mm,
                    )
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                entry["result"] = "failed"
                entry["error"] = str(error)
        cases_by_name = {case.name: case for case in benchmark_cases()}
        for index, case_name in enumerate(("hairpin_180", "tight_hairpin_180")):
            case = cases_by_name[case_name]
            name = f"{case_name}_ribbon_10x0p5"
            entry = {"name": name, "branch": 0, "profile_mm": [10.0, 0.5]}
            report["cases"].append(entry)
            try:
                curve = ph_hermite_candidates(case)[0]
                entry.update(
                    _sweep_case(
                        root,
                        name,
                        curve.controls,
                        (7 + index) * 15.0,
                        case.wire_radius_mm,
                        ribbon_width_mm=10.0,
                    )
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                entry["result"] = "failed"
                entry["error"] = str(error)
        application.activeViewport.fit()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["fatal_error"] = str(error)
    finally:
        report["active_document"] = application.activeDocument.name
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / "artifacts/verification/ph_fusion_sweep.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("PH_FUSION_SWEEP=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
