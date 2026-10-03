"""
Probe rectangular loft correspondence across per-step and cumulative rotations.

Run with ``Python.Run`` in Fusion while no command is active. The unsaved
scratch design stays open; results are written under artifacts/verification.
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
ASPECT_RATIOS = (1, 2, 5)
STATION_SPACING_CM = 15.0
REPORT_NAME = "sub45_multiaxis_loft"


def _rotate_vector(
    vector: tuple[float, float, float], angles_degrees: tuple[float, float, float]
) -> tuple[float, float, float]:
    """
    Apply active X, then Y, then Z rotations to a local frame vector.
    """
    x, y, z = vector
    rx, ry, rz = (math.radians(angle) for angle in angles_degrees)
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return x, y, z


def _station_angles(axis: str, angle_degrees: float) -> tuple[float, float, float]:
    """
    Return Euler angles for one chosen test axis or all three axes.
    """
    return tuple(angle_degrees if axis in (name, "xyz") else 0.0 for name in "xyz")


def _add_profile(
    root: adsk.fusion.Component,
    label: str,
    aspect_ratio: int,
    station: int,
    center_xy: tuple[float, float],
    angles_degrees: tuple[float, float, float],
) -> tuple[adsk.fusion.Profile, tuple[adsk.core.Point3D, ...]]:
    """
    Sketch one oriented rectangle with a construction marker at corner zero.
    """
    center = adsk.core.Point3D.create(center_xy[0], center_xy[1], -station * STATION_SPACING_CM)
    u = _rotate_vector((1.0, 0.0, 0.0), angles_degrees)
    v = _rotate_vector((0.0, 1.0, 0.0), angles_degrees)
    normal = _rotate_vector((0.0, 0.0, 1.0), angles_degrees)
    plane = adsk.core.Plane.create(center, adsk.core.Vector3D.create(*normal))
    if plane is None:
        raise RuntimeError(f"{label}: could not define station {station} plane.")
    plane_input = root.constructionPlanes.createInput()
    if not plane_input.setByPlane(plane):
        raise RuntimeError(f"{label}: could not set station {station} plane.")
    construction_plane = root.constructionPlanes.add(plane_input)
    if construction_plane is None:
        raise RuntimeError(f"{label}: could not create station {station} plane.")
    construction_plane.name = f"{label} plane {station}"
    sketch = root.sketches.add(construction_plane)
    if sketch is None:
        raise RuntimeError(f"{label}: could not create station {station} sketch.")
    sketch.name = f"{label} section {station}"
    half_width = WIDTH_CM / 2.0
    half_height = WIDTH_CM * aspect_ratio / 2.0
    local_corners = (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )
    corners = tuple(
        adsk.core.Point3D.create(
            center.x + local_x * u[0] + local_y * v[0],
            center.y + local_x * u[1] + local_y * v[1],
            center.z + local_x * u[2] + local_y * v[2],
        )
        for local_x, local_y in local_corners
    )
    sketch_corners = tuple(sketch.modelToSketchSpace(corner) for corner in corners)
    for first, second in zip(sketch_corners, (*sketch_corners[1:], sketch_corners[0])):
        if sketch.sketchCurves.sketchLines.addByTwoPoints(first, second) is None:
            raise RuntimeError(f"{label}: could not draw station {station} perimeter.")
    marker = sketch.sketchCurves.sketchLines.addByTwoPoints(
        sketch.modelToSketchSpace(center), sketch_corners[0]
    )
    if marker is None:
        raise RuntimeError(f"{label}: could not mark station {station} corner zero.")
    marker.isConstruction = True
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{label}: station {station} has {sketch.profiles.count} profiles.")
    return sketch.profiles.item(0), corners


def _corner_indices(
    face: adsk.fusion.BRepFace, corners: tuple[adsk.core.Point3D, ...]
) -> list[int]:
    """
    Locate profile corners among a face's boundary vertices within 0.01 mm.
    """
    indices: set[int] = set()
    for vertex_index in range(face.vertices.count):
        point = face.vertices.item(vertex_index).geometry
        for corner_index, corner in enumerate(corners):
            if point.distanceTo(corner) < 0.001:
                indices.add(corner_index)
    return sorted(indices)


def _inspect_body(
    body: adsk.fusion.BRepBody,
    start_corners: tuple[adsk.core.Point3D, ...],
    end_corners: tuple[adsk.core.Point3D, ...],
) -> dict[str, object]:
    """
    Check that each lateral face joins the same logical corner pair at both ends.
    """
    mappings: list[dict[str, list[int]]] = []
    for face_index in range(body.faces.count):
        face = body.faces.item(face_index)
        start = _corner_indices(face, start_corners)
        end = _corner_indices(face, end_corners)
        if start or end:
            mappings.append({"start": start, "end": end})
    lateral_pairs = [
        tuple(mapping["start"])
        for mapping in mappings
        if mapping["start"] and mapping["end"] and mapping["start"] == mapping["end"]
    ]
    expected_pairs = {(0, 1), (1, 2), (2, 3), (0, 3)}
    clean = body.faces.count == 6 and set(lateral_pairs) == expected_pairs
    return {
        "solid": body.isSolid,
        "faces": body.faces.count,
        "volume_cm3": body.volume,
        "end_face_mappings": mappings,
        "corner_correspondence": "clean" if clean else "deviation_or_unresolved",
    }


def run(_context: object) -> None:
    """
    Execute per-axis and compound loft cases in one unsaved direct-model design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the scratch design.")
    case_reports: list[dict[str, object]] = []
    report: dict[str, object] = {"document": scratch.name, "cases": case_reports}
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The new document is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        cases = [
            (ratio, axis, 44.9, "forward") for ratio in ASPECT_RATIOS for axis in ("x", "y", "z")
        ]
        cases.extend((ratio, "xyz", 44.0, "forward") for ratio in ASPECT_RATIOS)
        cases.extend((ratio, "z", 44.9, "alternating") for ratio in ASPECT_RATIOS)
        cases.extend((ratio, "z", 40.0, "forward") for ratio in ASPECT_RATIOS)
        cases.extend(
            (ratio, axis, angle, "two_station")
            for ratio in ASPECT_RATIOS
            for axis in ("x", "y")
            for angle in (10.0, 30.0, 44.9)
        )
        cases.extend(
            (ratio, axis, 20.0, "forward") for ratio in ASPECT_RATIOS for axis in ("x", "y")
        )
        cases.extend(
            (2, axis, angle, "three_station") for axis in ("x", "y") for angle in (44.9, 45.1)
        )
        cases.extend(
            (2, axis, angle, "forward") for axis in ("x", "y") for angle in (29.9, 30.1, 35.0)
        )
        for case_index, (ratio, axis, step_angle, pattern) in enumerate(cases):
            label = f"1:{ratio} {axis} {step_angle:g} {pattern}"
            center_xy = ((case_index % 6) * 18.0, (case_index // 6) * 22.0)
            step_multipliers = (
                (0, 1, 0, 1)
                if pattern == "alternating"
                else (0, 1)
                if pattern == "two_station"
                else (0, 1, 2)
                if pattern == "three_station"
                else (0, 1, 2, 3)
            )
            case: dict[str, object] = {
                "label": label,
                "aspect_ratio": ratio,
                "axis": axis,
                "adjacent_rotation_degrees": step_angle,
                "pattern": pattern,
            }
            case_reports.append(case)
            try:
                profiles: list[adsk.fusion.Profile] = []
                corner_sets: list[tuple[adsk.core.Point3D, ...]] = []
                for station, multiplier in enumerate(step_multipliers):
                    angles = _station_angles(axis, step_angle * multiplier)
                    profile, corners = _add_profile(root, label, ratio, station, center_xy, angles)
                    profiles.append(profile)
                    corner_sets.append(corners)
                loft_input = root.features.loftFeatures.createInput(
                    adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                )
                loft_input.isSolid = True
                for profile in profiles:
                    loft_input.loftSections.add(profile)
                loft = root.features.loftFeatures.add(loft_input)
                if loft is None:
                    error_code, detail = application.getLastError()
                    raise RuntimeError(f"Fusion rejected loft ({error_code}: {detail}).")
                bodies = [
                    _inspect_body(loft.bodies.item(index), corner_sets[0], corner_sets[-1])
                    for index in range(loft.bodies.count)
                ]
                case["bodies"] = bodies
                case["result"] = (
                    "clean"
                    if len(bodies) == 1 and bodies[0]["corner_correspondence"] == "clean"
                    else "deviation_or_unresolved"
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                case["result"] = "failed"
                case["error"] = str(error)
        application.activeViewport.fit()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["fatal_error"] = str(error)
    finally:
        report["active_document"] = application.activeDocument.name
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / f"artifacts/verification/{REPORT_NAME}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("SUB45_MULTIAXIS_LOFT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
