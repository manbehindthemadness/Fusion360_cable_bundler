"""
Probe mirrored FFC texture mapping across trace count, pitch, width, and thickness.

Run through the local Fusion MCP script runner with the calibrated unsaved FFC
scratch active. This creates a separate unsaved test design, leaves both
documents open, and writes only ignored verification artifacts on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_perimeter_stripes import _pattern

REFERENCE_PITCH_MM = 2.506666666666669
REFERENCE_THICKNESS_MM = 1.5
REFERENCE_CELL_SCALE_CM = 8.282368421052632 / 39.0
REFERENCE_OFFSET_CM = 0.118
SOURCE_APPEARANCE = "FFC mirrored perimeter stripe test"
PATH_LENGTH_CM = 4.0
OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_texture_matrix"


@dataclass(frozen=True)
class Case:
    """
    One controlled straight sweep and its trace dimensions, in millimeters.
    """

    name: str
    count: int
    pitch_mm: float
    trace_width_mm: float
    thickness_mm: float


CASES = (
    Case("single_thin", 1, 2.5, 1.5, 0.2),
    Case("single_thick", 1, 2.5, 1.5, 2.0),
    Case("three_thin", 3, 2.5, 1.5, 0.2),
    Case("three_thick", 3, 2.5, 1.5, 2.0),
    Case("seven_narrow", 7, 2.5, 1.0, 1.5),
    Case("seven_wide", 7, 2.5, 2.0, 1.5),
    Case("nine_fine", 9, 1.2, 0.7, 0.5),
    Case("nine_heavy", 9, 3.5, 2.2, 3.0),
    Case("nineteen_thin", 19, REFERENCE_PITCH_MM, 1.5146940685852002, 0.2),
    Case("nineteen_reference", 19, REFERENCE_PITCH_MM, 1.5146940685852002, 1.5),
    Case("nineteen_thick", 19, REFERENCE_PITCH_MM, 1.5146940685852002, 3.0),
)


def _outline(case: Case) -> tuple[tuple[float, float], ...]:
    """
    Generate one closed fitted contour with shallow inter-trace relief.
    """
    half_width = case.count * case.pitch_mm / 2.0
    half_height = case.thickness_mm / 2.0
    spacing = case.pitch_mm - case.trace_width_mm
    top: list[tuple[float, float]] = [(-half_width, half_height)]
    for index in range(case.count):
        center = (index - (case.count - 1) / 2.0) * case.pitch_mm
        half_trace = case.trace_width_mm / 2.0
        top.extend(
            (center + fraction * half_trace, half_height)
            for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0)
        )
        if index < case.count - 1:
            right_land = center + half_trace
            top.extend(
                (
                    right_land + spacing * fraction,
                    half_height - case.thickness_mm * 0.05 * depth_fraction,
                )
                for fraction, depth_fraction in ((0.25, 0.5), (0.5, 1.0), (0.75, 0.5))
            )
    top.append((half_width, half_height))
    bottom = [(across, -height) for across, height in reversed(top)]
    return ((-half_width, 0.0), *top, (half_width, 0.0), *bottom)


def _mapping(case: Case) -> tuple[float, float, float, float]:
    """
    Extrapolate the reference mapping using pitch and thickness ratios.

    This is the hypothesis under test, not a proven production formula.
    """
    edge_total = (case.thickness_mm / REFERENCE_THICKNESS_MM) * (REFERENCE_PITCH_MM / case.pitch_mm)
    right_edge = 0.35 * edge_total
    left_edge = 0.65 * edge_total
    total_cells = 2 * case.count + edge_total
    scale_cm = REFERENCE_CELL_SCALE_CM * (case.pitch_mm / REFERENCE_PITCH_MM) * total_cells
    offset_cm = REFERENCE_OFFSET_CM * (case.pitch_mm / REFERENCE_PITCH_MM)
    return scale_cm, offset_cm, right_edge, left_edge


def _case(
    root: adsk.fusion.Component,
    design: adsk.fusion.Design,
    source_appearance: adsk.core.Appearance,
    case: Case,
    center_x_cm: float,
) -> dict[str, object]:
    """
    Sweep one fitted profile and assign a fresh computed stripe appearance.
    """
    path_sketch = root.sketches.add(root.xYConstructionPlane)
    path_sketch.name = f"{case.name} path"
    start = path_sketch.modelToSketchSpace(adsk.core.Point3D.create(center_x_cm, 0.0, 0.0))
    end = path_sketch.modelToSketchSpace(adsk.core.Point3D.create(center_x_cm, PATH_LENGTH_CM, 0.0))
    line = path_sketch.sketchCurves.sketchLines.addByTwoPoints(start, end)
    path = root.features.createPath(line, False)
    section = root.sketches.add(root.xZConstructionPlane)
    section.name = f"{case.name} one-face section"
    fit_points = adsk.core.ObjectCollection.create()
    for across_mm, height_mm in _outline(case):
        world = adsk.core.Point3D.create(center_x_cm + across_mm / 10.0, 0.0, height_mm / 10.0)
        fit_points.add(section.modelToSketchSpace(world))
    spline = section.sketchCurves.sketchFittedSplines.add(fit_points)
    spline.isClosed = True
    if section.profiles.count != 1:
        raise RuntimeError("The fitted section did not form one closed profile.")
    profile = section.profiles.item(0)
    if profile.profileLoops.item(0).profileCurves.count != 1:
        raise RuntimeError("Fusion split the section into multiple profile curves.")
    sweep_input = root.features.sweepFeatures.createInput(
        profile, path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
    sweep = root.features.sweepFeatures.add(sweep_input)
    if sweep is None or sweep.bodies.count != 1:
        raise RuntimeError("The case did not produce exactly one sweep body.")
    body = sweep.bodies.item(0)
    if not body.isSolid or body.faces.count != 3:
        raise RuntimeError("The sweep is not a three-face, single-side solid.")
    sweep.name = f"{case.name} fitted sweep"
    side = max((body.faces.item(index) for index in range(body.faces.count)), key=lambda f: f.area)
    scale_cm, offset_cm, right_edge, left_edge = _mapping(case)
    texture_path = OUTPUT / f"{case.name}.png"
    texture_path.write_bytes(
        _pattern(case.count, case.trace_width_mm, case.pitch_mm, right_edge, left_edge)
    )
    appearance = design.appearances.addByCopy(source_appearance, f"{case.name} stripe test")
    appearance.colorTexture = str(texture_path)
    slot = appearance.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("Fusion did not connect the case texture.")
    scale = texture.properties.itemById("texture_RealWorldScaleX")
    offset = texture.properties.itemById("texture_RealWorldOffsetX")
    if scale is None or offset is None:
        raise RuntimeError("Fusion did not expose the case texture mapping controls.")
    scale.value = scale_cm
    offset.value = offset_cm
    side.appearance = appearance
    marker = root.sketches.add(root.xYConstructionPlane)
    marker.name = f"{case.name} contact-center ticks"
    for index in range(case.count):
        x = center_x_cm + (index - (case.count - 1) / 2.0) * case.pitch_mm / 10.0
        tick_left = marker.modelToSketchSpace(adsk.core.Point3D.create(x - 0.045, -0.40, 0.0))
        tick_right = marker.modelToSketchSpace(adsk.core.Point3D.create(x + 0.045, -0.40, 0.0))
        marker.sketchCurves.sketchLines.addByTwoPoints(tick_left, tick_right)
    path_sketch.isLightBulbOn = False
    section.isLightBulbOn = False
    return {
        "name": case.name,
        "count": case.count,
        "pitch_mm": case.pitch_mm,
        "trace_width_mm": case.trace_width_mm,
        "thickness_mm": case.thickness_mm,
        "nominal_width_mm": case.count * case.pitch_mm,
        "center_x_cm": center_x_cm,
        "scale_cm": scale.value,
        "offset_cm": offset.value,
        "edge_cells": [right_edge, left_edge],
        "body_faces": body.faces.count,
        "side_face_edges": side.edges.count,
        "texture": str(texture_path),
    }


def run(_context: object) -> None:
    """
    Build the matrix and capture matched top/bottom views for each case.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the matrix.")
    source = application.activeDocument
    if source is None or source.name != "Untitled" or source.isSaved:
        raise RuntimeError("Activate the calibrated unsaved FFC scratch first.")
    source_design = adsk.fusion.Design.cast(application.activeProduct)
    source_appearance = source_design.appearances.itemByName(SOURCE_APPEARANCE)
    if source_appearance is None:
        raise RuntimeError("The calibrated mirrored appearance is unavailable.")
    source_modified_before = source.isModified
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("Fusion did not create a test design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    root = design.rootComponent
    results: list[dict[str, object]] = []
    for index, case in enumerate(CASES):
        center_x_cm = index * 15.0
        try:
            row = _case(root, design, source_appearance, case, center_x_cm)
            row["result"] = "solid"
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row = {"name": case.name, "result": "failed", "error": str(error)}
        results.append(row)
    viewport = application.activeViewport
    for row in results:
        if row["result"] != "solid":
            continue
        case_name = str(row["name"])
        extent_cm = max(2.8, float(row["nominal_width_mm"]) / 10.0 * 0.75)
        row["view_extent_cm"] = extent_cm
        for side_name, direction in (("top", 1), ("bottom", -1)):
            camera = viewport.camera
            center_x = float(row["center_x_cm"])
            camera.target = adsk.core.Point3D.create(center_x, 0.75, 0.0)
            camera.eye = adsk.core.Point3D.create(center_x, 0.75, 100.0 * direction)
            camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
            camera.viewExtents = extent_cm
            viewport.camera = camera
            viewport.refresh()
            image_path = OUTPUT / f"{case_name}_{side_name}.png"
            row[f"{side_name}_image"] = str(image_path)
            row[f"{side_name}_saved"] = viewport.saveAsImageFile(str(image_path), 0, 0)
    report = {
        "source_document": source.name,
        "source_modified_before": source_modified_before,
        "source_modified_after": source.isModified,
        "scratch_document": scratch.name,
        "cases": results,
    }
    report_path = OUTPUT / "matrix.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FFC_TEXTURE_MATRIX="
        + json.dumps(
            {
                "cases": len(results),
                "solids": sum(row["result"] == "solid" for row in results),
                "report": str(report_path),
                "source_modified_after": source.isModified,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
