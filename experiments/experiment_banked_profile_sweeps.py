"""
Compare bank-aware profile-extreme predictions with Fusion solid sweeps.

Run with Fusion ``Python.Run`` while no command is active. This creates a new
unsaved experiment design and leaves both it and the source document open.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_banked_profile_extremes import SHAPES, ProfileShape
from experiments.experiment_ph_fusion_sweep import _path_sketch
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates


def _profile(
    root: adsk.fusion.Component,
    name: str,
    shape: ProfileShape,
    bank_degrees: float,
    offset_y_cm: float,
) -> adsk.fusion.Sketch:
    """
    Sketch a circle or prebanked polygon normal to the initial path tangent.
    """
    sketch = root.sketches.add(root.yZConstructionPlane)
    sketch.name = f"{name} profile"
    if shape.circle_radius_mm > 0.0:
        center = sketch.modelToSketchSpace(adsk.core.Point3D.create(0.0, offset_y_cm, 0.0))
        sketch.sketchCurves.sketchCircles.addByCenterRadius(center, shape.circle_radius_mm / 10.0)
    else:
        angle = math.radians(bank_degrees)
        world_points = [
            adsk.core.Point3D.create(
                0.0,
                offset_y_cm + (normal * math.cos(angle) - vertical * math.sin(angle)) / 10.0,
                (normal * math.sin(angle) + vertical * math.cos(angle)) / 10.0,
            )
            for normal, vertical in shape.vertices_mm
        ]
        points = [sketch.modelToSketchSpace(point) for point in world_points]
        for index, point in enumerate(points):
            sketch.sketchCurves.sketchLines.addByTwoPoints(point, points[(index + 1) % len(points)])
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{name}: expected one closed profile, got {sketch.profiles.count}.")
    return sketch


def _sweep(
    root: adsk.fusion.Component,
    row: dict[str, object],
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Build a new-body perpendicular sweep for one preregistered profile case.
    """
    name = str(row["name"])
    separation = float(row["separation_mm"])
    bank = float(row["bank_degrees"])
    shape_name = str(row["shape"])
    shape = next(item for item in SHAPES if item.name == shape_name)
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation), 25.0 + 0j, -25.0 + 0j)
    )[0]
    path_sketch, spline = _path_sketch(root, name, curve.controls, offset_y_cm)
    profile_sketch = _profile(root, name, shape, bank, offset_y_cm)
    path = root.features.createPath(spline, False)
    sweep_input = root.features.sweepFeatures.createInput(
        profile_sketch.profiles.item(0),
        path,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    twist = float(row.get("twist_degrees", 0.0))
    if twist:
        sweep_input.twistAngle = adsk.core.ValueInput.createByString(f"{twist} deg")
    feature = root.features.sweepFeatures.add(sweep_input)
    if feature is None:
        raise RuntimeError("Fusion did not return a sweep feature.")
    feature.name = f"{name} bank sweep"
    path_sketch.isLightBulbOn = False
    profile_sketch.isLightBulbOn = False
    bodies = [feature.bodies.item(index) for index in range(feature.bodies.count)]
    return {
        "result": "solid" if len(bodies) == 1 and bodies[0].isSolid else "non_single_solid",
        "body_count": len(bodies),
        "body_volumes_cm3": [body.volume for body in bodies],
        "body_face_counts": [body.faces.count for body in bodies],
    }


def run(_context: object) -> None:
    """
    Execute fixed cases in an isolated design and retain all observations.
    """
    application = adsk.core.Application.get()
    active_command = str(application.userInterface.activeCommand)
    if active_command != "SelectCommand":
        raise RuntimeError(f"Finish the active Fusion command before this probe: {active_command}.")
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    plan_path = root_path / "artifacts/verification/banked_profile_extremes_math.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    planned = plan.get("cases") if isinstance(plan, dict) else None
    if not isinstance(planned, list) or len(planned) != 36:
        raise ValueError("Expected the 36-case preregistered bank-extreme plan.")
    source_name = application.activeDocument.name
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the bank-extreme scratch design.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The experiment scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    results: list[dict[str, object]] = []
    for index, planned_case in enumerate(planned):
        if not isinstance(planned_case, dict):
            raise ValueError("The bank-extreme plan contains a malformed case.")
        entry: dict[str, object] = dict(planned_case)
        results.append(entry)
        try:
            entry.update(_sweep(design.rootComponent, entry, index * 8.0))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            entry["result"] = "failed"
            entry["error"] = str(error)
    application.activeViewport.fit()
    report = {"source_document": source_name, "scratch_document": scratch.name, "cases": results}
    output = root_path / "artifacts/verification/banked_profile_extremes_fusion.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "BANKED_PROFILE_SWEEPS="
        + json.dumps(
            {"cases": len(results), "solids": sum(row["result"] == "solid" for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
