"""
Probe production cable-section sketches on isolated PH reversal sweeps.

Run through Fusion ``Python.Run`` with no command active. Creates a new
unsaved scratch, leaves prior documents unchanged, and writes an ignored
report. The ribbon and FFC sketches use the production section builder.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from cable_bundler.domain.ffc import FfcDimensions
from cable_bundler.fusion.cable_solid_parts.ribbon_builder import _add_solid_section
from cable_bundler.fusion.solid_ribbon import SolidRibbonSection
from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ph_fusion_sweep import _path_sketch
from experiments.experiment_ph_quintic import HermiteCase, PhQuintic, ph_hermite_candidates

SHAPES = ("circle", "lobed_one", "lobed_three", "ffc_one", "ffc_three")
SEPARATIONS_MM = (5.0, 10.0)
TWISTS_DEGREES = (0.0, 90.0, 180.0)
FFC = FfcDimensions(2.0, 1.5, 0.5)


def _profile(
    root: adsk.fusion.Component,
    name: str,
    shape: str,
    offset_y_cm: float,
) -> adsk.fusion.Sketch:
    """
    Construct the production ribbon/FFC section or a circular wire control.
    """
    if shape == "circle":
        sketch = root.sketches.add(root.yZConstructionPlane)
        sketch.name = f"{name} circular section"
        center = sketch.modelToSketchSpace(adsk.core.Point3D.create(0.0, offset_y_cm, 0.0))
        if sketch.sketchCurves.sketchCircles.addByCenterRadius(center, 0.05) is None:
            raise RuntimeError("Fusion did not draw the circular section.")
    else:
        count = 1 if shape.endswith("one") else 3
        centers = tuple(
            Vector3(0.0, offset_y_cm * 10.0 + 2.0 * (index - (count - 1) / 2.0), 0.0)
            for index in range(count)
        )
        station = SolidRibbonSection(
            centers=centers,
            normal=Vector3(1.0, 0.0, 0.0),
            width=Vector3(0.0, 1.0, 0.0),
            lobe_width_mm=1.0,
        )
        ffc = FFC if shape.startswith("ffc") else None
        sketch, plane = _add_solid_section(
            root, station, 0.5 if ffc is not None else 1.0, adsk.core.Matrix3D.create(), ffc
        )
        sketch.name = f"{name} production section"
        plane.name = f"{name} section plane"
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{name}: expected one profile, got {sketch.profiles.count}.")
    return sketch


def _section_report(
    body: adsk.fusion.BRepBody,
    curve: PhQuintic,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Intersect one solid with the plane normal to its PH midpoint tangent.
    """
    midpoint = curve.point_at(0.5)
    tangent = curve.derivative_at(0.5)
    speed = abs(tangent)
    if speed <= 0.0:
        raise RuntimeError("The PH midpoint has zero speed.")
    plane = adsk.core.Plane.create(
        adsk.core.Point3D.create(midpoint.real / 10.0, offset_y_cm + midpoint.imag / 10.0, 0.0),
        adsk.core.Vector3D.create(tangent.real / speed, tangent.imag / speed, 0.0),
    )
    section = adsk.fusion.TemporaryBRepManager.get().planeIntersection(body, plane)
    if section is None:
        raise RuntimeError("Fusion returned no temporary midpoint section.")
    bounds = section.boundingBox
    return {
        "wire_count": section.wires.count,
        "edge_count": section.edges.count,
        "vertex_count": section.vertices.count,
        "bounds_mm": {
            "min": [bounds.minPoint.x * 10.0, bounds.minPoint.y * 10.0, bounds.minPoint.z * 10.0],
            "max": [bounds.maxPoint.x * 10.0, bounds.maxPoint.y * 10.0, bounds.maxPoint.z * 10.0],
        },
    }


def _case(
    root: adsk.fusion.Component,
    shape: str,
    separation_mm: float,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Record the sweep, input profile, and temporary midpoint section.
    """
    name = f"product_{shape}_h{separation_mm:g}_twist{twist_degrees:g}"
    row: dict[str, object] = {
        "name": name,
        "shape": shape,
        "separation_mm": separation_mm,
        "twist_degrees": twist_degrees,
    }
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation_mm), 25.0 + 0j, -25.0 + 0j)
    )[0]
    path_sketch, spline = _path_sketch(root, name, curve.controls, offset_y_cm)
    section_sketch = _profile(root, name, shape, offset_y_cm)
    profile = section_sketch.profiles.item(0)
    profile_edges = profile.profileLoops.item(0).profileCurves.count
    area_mm2 = profile.areaProperties().area * 100.0
    nominal_volume_mm3 = area_mm2 * curve.exact_length_mm()
    row.update(
        {
            "profile_edges": profile_edges,
            "profile_area_mm2": area_mm2,
            "path_length_mm": curve.exact_length_mm(),
            "nominal_volume_mm3": nominal_volume_mm3,
        }
    )
    path = root.features.createPath(spline, False)
    sweep_input = root.features.sweepFeatures.createInput(
        profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    if twist_degrees:
        sweep_input.twistAngle = adsk.core.ValueInput.createByString(f"{twist_degrees} deg")
    feature = root.features.sweepFeatures.add(sweep_input)
    if feature is None:
        raise RuntimeError("Fusion returned no sweep feature.")
    feature.name = f"{name} sweep"
    path_sketch.isLightBulbOn = False
    section_sketch.isLightBulbOn = False
    if feature.bodies.count != 1:
        row.update({"result": "non_single_body", "body_count": feature.bodies.count})
        return row
    body = feature.bodies.item(0)
    measured_volume_mm3 = body.volume * 1000.0
    row.update(
        {
            "result": "solid" if body.isSolid else "non_solid",
            "body_face_count": body.faces.count,
            "body_volume_mm3": measured_volume_mm3,
            "relative_volume_error": (measured_volume_mm3 - nominal_volume_mm3)
            / nominal_volume_mm3,
        }
    )
    if body.isSolid:
        row["midpoint_section"] = _section_report(body, curve, offset_y_cm)
    return row


def run(_context: object) -> None:
    """
    Run the preregistered shape matrix in a separate unsaved design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the product-profile scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch document is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    for separation in SEPARATIONS_MM:
        for shape in SHAPES:
            for twist in TWISTS_DEGREES:
                offset_y_cm = len(rows) * 8.0
                try:
                    row = _case(design.rootComponent, shape, separation, twist, offset_y_cm)
                except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                    row = {
                        "name": f"product_{shape}_h{separation:g}_twist{twist:g}",
                        "shape": shape,
                        "separation_mm": separation,
                        "twist_degrees": twist,
                        "result": "failed",
                        "error": str(error),
                    }
                rows.append(row)
    application.activeViewport.fit()
    report = {
        "source_document": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "scratch_document": scratch.name,
        "cases": rows,
    }
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    output = root_path / "artifacts/verification/product_profile_sweeps.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PRODUCT_PROFILE_SWEEPS="
        + json.dumps(
            {"cases": len(rows), "solids": sum(row["result"] == "solid" for row in rows)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
