"""
Probe loft correspondence as relative rectangle twists rise from 5 to 90 degrees.

Run with ``Python.Run`` in Fusion while no command is active. The new unsaved
scratch design stays open for visual inspection, including if the loft fails.
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

WIDTH_CM = 2.0
HEIGHT_CM = 10.0
STATION_SPACING_CM = 3.0
RELATIVE_ANGLES_DEGREES = tuple(range(5, 91, 5))
REPORT_NAME = "rectangle_5x_incremental_twist_loft"


def _rectangle_corners(angle_degrees: int) -> tuple[adsk.core.Point3D, ...]:
    """
    Return rectangle corners in logical order before applying the station offset.
    """
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    half_width = WIDTH_CM / 2.0
    half_height = HEIGHT_CM / 2.0
    local_corners = (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )
    return tuple(
        adsk.core.Point3D.create(x * cosine - y * sine, x * sine + y * cosine, 0.0)
        for x, y in local_corners
    )


def _add_section(
    root: adsk.fusion.Component, index: int, relative_angle: int, total_angle: int
) -> adsk.fusion.Profile:
    """
    Create one closed rectangle and mark its logical corner zero for inspection.
    """
    if index == 0:
        plane = root.xYConstructionPlane
    else:
        plane_input = root.constructionPlanes.createInput()
        offset = adsk.core.ValueInput.createByReal(-index * STATION_SPACING_CM)
        if not plane_input.setByOffset(root.xYConstructionPlane, offset):
            raise RuntimeError(f"Could not define station {index} offset plane.")
        plane = root.constructionPlanes.add(plane_input)
        if plane is None:
            raise RuntimeError(f"Could not create station {index} offset plane.")
        plane.name = f"Station {index:02d}: +{relative_angle} deg, total {total_angle} deg"
    sketch = root.sketches.add(plane)
    if sketch is None:
        raise RuntimeError(f"Could not create station {index} sketch.")
    sketch.name = f"Rectangle {index:02d}: +{relative_angle} deg, total {total_angle} deg"
    corners = _rectangle_corners(total_angle)
    for first, second in zip(corners, (*corners[1:], corners[0])):
        if sketch.sketchCurves.sketchLines.addByTwoPoints(first, second) is None:
            raise RuntimeError(f"Could not draw station {index} rectangle.")
    marker = sketch.sketchCurves.sketchLines.addByTwoPoints(
        adsk.core.Point3D.create(0.0, 0.0, 0.0), corners[0]
    )
    if marker is None:
        raise RuntimeError(f"Could not mark station {index} corner zero.")
    marker.isConstruction = True
    if sketch.profiles.count != 1:
        raise RuntimeError(f"Station {index} yielded {sketch.profiles.count} profiles.")
    return sketch.profiles.item(0)


def run(_context: object) -> None:
    """
    Loft nineteen rectangular sections and leave the diagnostic design open.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the scratch design.")
    total_angles = (0, *(5 * index * (index + 1) // 2 for index in range(1, 19)))
    report: dict[str, object] = {
        "document": scratch.name,
        "section_count": len(total_angles),
        "relative_angles_degrees": RELATIVE_ANGLES_DEGREES,
        "cumulative_angles_degrees": total_angles,
        "rectangle_width_mm": WIDTH_CM * 10.0,
        "rectangle_height_mm": HEIGHT_CM * 10.0,
        "station_spacing_mm": STATION_SPACING_CM * 10.0,
        "station_direction": "top_to_bottom_negative_z",
        "guide_rails": 0,
    }
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The new document is not a Fusion design.")
        root = design.rootComponent
        profiles: list[adsk.fusion.Profile] = []
        for index, total_angle in enumerate(total_angles):
            relative_angle = 0 if index == 0 else RELATIVE_ANGLES_DEGREES[index - 1]
            profile = _add_section(root, index, relative_angle, total_angle)
            profiles.append(profile)
        prefixes: list[dict[str, object]] = []
        report["prefixes"] = prefixes
        for section_count in range(2, len(profiles) + 1):
            loft_input = root.features.loftFeatures.createInput(
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            for profile in profiles[:section_count]:
                loft_input.loftSections.add(profile)
            loft_input.isSolid = True
            step = {
                "section_count": section_count,
                "last_relative_angle_degrees": RELATIVE_ANGLES_DEGREES[section_count - 2],
                "last_cumulative_angle_degrees": total_angles[section_count - 1],
            }
            prefixes.append(step)
            try:
                loft = root.features.loftFeatures.add(loft_input)
                if loft is None:
                    error_code, detail = application.getLastError()
                    raise RuntimeError(f"Fusion rejected the loft ({error_code}: {detail}).")
                bodies: list[dict[str, object]] = []
                for index in range(loft.bodies.count):
                    body = loft.bodies.item(index)
                    body.name = f"Increasing rectangle twist body {index + 1}"
                    face_areas = sorted(
                        body.faces.item(face_index).area for face_index in range(body.faces.count)
                    )
                    bodies.append(
                        {
                            "name": body.name,
                            "solid": body.isSolid,
                            "faces": body.faces.count,
                            "face_areas_cm2": face_areas,
                            "volume_cm3": body.volume,
                        }
                    )
                step["result"] = "single_body" if len(bodies) == 1 else "split_bodies"
                step["bodies"] = bodies
                if section_count < len(profiles) and not loft.deleteMe():
                    raise RuntimeError(f"Could not remove prefix {section_count} loft.")
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                step["result"] = "failed"
                step["error"] = str(error)
                if section_count < len(profiles):
                    raise
        report["result"] = prefixes[-1]["result"]
        application.activeViewport.fit()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["result"] = "failed"
        report["error"] = str(error)
    finally:
        report["active_document"] = application.activeDocument.name
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / f"artifacts/verification/{REPORT_NAME}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("RECTANGLE_INCREMENTAL_TWIST_LOFT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
