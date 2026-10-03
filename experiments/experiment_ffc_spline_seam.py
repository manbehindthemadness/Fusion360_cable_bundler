"""
Probe one-face FFC sweep and seam transport with a periodic fitted outline.

Run through Fusion ``Python.Run`` with no command active. This makes a new
unsaved scratch and leaves it open; earlier documents are not edited.
The isolated sweep does not exercise the production multi-section FFC loft.
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
from experiments.experiment_discrete_spline_seam import _seam_report
from experiments.experiment_ph_fusion_sweep import _path_sketch
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates
from experiments.experiment_product_profile_sweeps import _section_report

FFC = FfcDimensions(2.0, 1.5, 0.5)
THICKNESS_MM = 0.5
CASES = tuple(
    (lines, separation, twist)
    for lines, separations in ((1, (5.0,)), (3, (5.0, 10.0)), (5, (10.0, 20.0)))
    for separation in separations
    for twist in (0.0, 90.0, 180.0)
)


def _outline_points(lines: int) -> tuple[tuple[float, float], ...]:
    """
    Fit the FFC lands and shallow spacing grooves with one closed curve.

    The first point, at the first outer edge's mid-thickness, designates
    the longitudinal seam. Spacing relief is smooth rather than an exact V.
    """
    if lines < 1:
        raise ValueError("An FFC outline needs at least one trace.")
    half_width = lines * FFC.pitch_mm / 2.0
    half_height = THICKNESS_MM / 2.0
    groove_depth = THICKNESS_MM * 0.05
    top: list[tuple[float, float]] = [(-half_width, half_height)]
    for index in range(lines):
        center = (index - (lines - 1) / 2.0) * FFC.pitch_mm
        half_trace = FFC.trace_width_mm / 2.0
        top.extend(
            (center + fraction * half_trace, half_height)
            for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0)
        )
        if index < lines - 1:
            right_land = center + half_trace
            top.extend(
                (
                    right_land + FFC.spacing_mm * fraction,
                    half_height - groove_depth * depth_fraction,
                )
                for fraction, depth_fraction in ((0.25, 0.5), (0.5, 1.0), (0.75, 0.5))
            )
    top.append((half_width, half_height))
    bottom = [(across, -height) for across, height in reversed(top)]
    return ((-half_width, 0.0), *top, (half_width, 0.0), *bottom)


def _profile(
    root: adsk.fusion.Component,
    path: adsk.fusion.Path,
    name: str,
    lines: int,
    offset_y_cm: float,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane, adsk.core.Point3D]:
    """
    Draw one periodic fitted spline through the FFC contour samples.
    """
    plane_input = root.constructionPlanes.createInput()
    if not plane_input.setByPath(
        path,
        adsk.fusion.PathDistanceTypes.ProportionalPathDistanceType,
        adsk.core.ValueInput.createByReal(0.0),
    ):
        raise RuntimeError("Fusion could not place the FFC section plane.")
    plane = root.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion did not create the FFC section plane.")
    plane.name = f"{name} section plane"
    sketch = root.sketches.add(plane)
    if sketch is None:
        raise RuntimeError("Fusion did not create the FFC section sketch.")
    sketch.name = f"{name} one-spline FFC outline"
    fit_points = adsk.core.ObjectCollection.create()
    for across_mm, height_mm in _outline_points(lines):
        world = adsk.core.Point3D.create(0.0, offset_y_cm + across_mm / 10.0, height_mm / 10.0)
        fit_points.add(sketch.modelToSketchSpace(world))
    spline = sketch.sketchCurves.sketchFittedSplines.add(fit_points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the FFC outline.")
    spline.isClosed = True
    if not spline.isClosed or sketch.profiles.count != 1:
        raise RuntimeError("The FFC fitted outline did not make one closed profile.")
    profile = sketch.profiles.item(0)
    if profile.profileLoops.count != 1 or profile.profileLoops.item(0).profileCurves.count != 1:
        raise RuntimeError("Fusion split the FFC fitted outline into multiple curves.")
    seam_point = spline.fitPoints.item(0).worldGeometry
    return sketch, plane, seam_point


def _case(
    root: adsk.fusion.Component,
    lines: int,
    separation_mm: float,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Audit one fitted FFC profile on the controlled PH reversal.
    """
    name = f"ffc_fit_{lines}_h{separation_mm:g}_twist{twist_degrees:g}"
    row: dict[str, object] = {
        "name": name,
        "lines": lines,
        "trace_width_mm": FFC.trace_width_mm,
        "spacing_mm": FFC.spacing_mm,
        "pitch_mm": FFC.pitch_mm,
        "thickness_mm": THICKNESS_MM,
        "nominal_width_mm": lines * FFC.pitch_mm,
        "separation_mm": separation_mm,
        "twist_degrees": twist_degrees,
    }
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation_mm), 25.0 + 0j, -25.0 + 0j)
    )[0]
    path_sketch, path_spline = _path_sketch(root, name, curve.controls, offset_y_cm)
    path = root.features.createPath(path_spline, False)
    section, plane, seam_point = _profile(root, path, name, lines, offset_y_cm)
    profile = section.profiles.item(0)
    row["profile_edges"] = profile.profileLoops.item(0).profileCurves.count
    row["profile_area_mm2"] = profile.areaProperties().area * 100.0
    sweep_input = root.features.sweepFeatures.createInput(
        profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    if twist_degrees:
        sweep_input.twistAngle = adsk.core.ValueInput.createByString(f"{twist_degrees} deg")
    feature = root.features.sweepFeatures.add(sweep_input)
    if feature is None or feature.bodies.count != 1:
        raise RuntimeError("Fusion did not make one fitted FFC sweep.")
    feature.name = name
    body = feature.bodies.item(0)
    row.update(
        {
            "result": "solid" if body.isSolid else "non_solid",
            "body_face_count": body.faces.count,
            "body_edge_count": body.edges.count,
            "body_volume_mm3": body.volume * 1000.0,
        }
    )
    row["seam"] = _seam_report(
        feature,
        seam_point,
        lines * FFC.pitch_mm / 2.0,
        separation_mm,
        twist_degrees,
        offset_y_cm,
    )
    if body.isSolid:
        row["midpoint_section"] = _section_report(body, curve, offset_y_cm)
    path_sketch.isLightBulbOn = False
    section.isLightBulbOn = False
    plane.isLightBulbOn = False
    return row


def run(_context: object) -> None:
    """
    Execute the one-spline FFC matrix in a separate unsaved Fusion design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the FFC seam-test scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch document is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    for index, (lines, separation, twist) in enumerate(CASES):
        try:
            row = _case(design.rootComponent, lines, separation, twist, index * 8.0)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row = {
                "name": f"ffc_fit_{lines}_h{separation:g}_twist{twist:g}",
                "lines": lines,
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
    output = root_path / "artifacts/verification/ffc_spline_seam.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FFC_SPLINE_SEAM="
        + json.dumps(
            {"cases": len(rows), "solids": sum(row["result"] == "solid" for row in rows)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
