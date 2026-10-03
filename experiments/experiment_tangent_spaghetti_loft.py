"""
Probe loft face correspondence along tangent-aligned bends, rolls, and kinks.

Run with ``Python.Run`` in Fusion while no command is active. The unsaved
scratch design remains open and the report goes under artifacts/verification.
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

RADIUS_CM = 20.0
HELIX_RISE_CM = 30.0
WIDTH_CM = 2.0
REPORT_NAME = "tangent_spaghetti_loft"


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    """
    Normalize a nonzero analytic frame vector.
    """
    length = math.sqrt(sum(component * component for component in vector))
    return tuple(component / length for component in vector)


def _cross(
    first: tuple[float, float, float], second: tuple[float, float, float]
) -> tuple[float, float, float]:
    """
    Return the right-handed cross product of two frame vectors.
    """
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _dot(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    """
    Return the dot product of two frame vectors.
    """
    return sum(a * b for a, b in zip(first, second))


def _frame(
    path: str,
    fraction: float,
    offset_xy: tuple[float, float],
    roll_total_degrees: float = 0.0,
    kink_degrees: float = 0.0,
) -> tuple[
    adsk.core.Point3D,
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """
    Give the analytic center, tangent, width axis, and height axis.

    The planar U-turn and kink use a world-Y height reference; the helix uses
    an inward radial width reference. Optional roll rotates only within the
    tangent-normal section plane.
    """
    if path == "u_turn":
        theta = fraction * math.pi
        center = adsk.core.Point3D.create(
            offset_xy[0] + RADIUS_CM * math.sin(theta),
            offset_xy[1],
            RADIUS_CM * (1.0 - math.cos(theta)),
        )
        tangent = (math.cos(theta), 0.0, math.sin(theta))
        width_axis = (-math.sin(theta), 0.0, math.cos(theta))
    elif path == "helix":
        theta = fraction * 2.0 * math.pi
        center = adsk.core.Point3D.create(
            offset_xy[0] + RADIUS_CM * math.cos(theta),
            offset_xy[1] + RADIUS_CM * math.sin(theta),
            HELIX_RISE_CM * fraction,
        )
        tangent = _unit(
            (
                -RADIUS_CM * math.sin(theta),
                RADIUS_CM * math.cos(theta),
                HELIX_RISE_CM / (2.0 * math.pi),
            )
        )
        width_axis = (-math.cos(theta), -math.sin(theta), 0.0)
    elif path == "kink":
        theta = math.radians(kink_degrees if fraction > 0.5 else 0.0)
        if fraction < 0.5:
            center = adsk.core.Point3D.create(offset_xy[0] + 60.0 * fraction, offset_xy[1], 0.0)
        else:
            distance_after_corner = 60.0 * fraction - 30.0
            center = adsk.core.Point3D.create(
                offset_xy[0] + 30.0 + distance_after_corner * math.cos(theta),
                offset_xy[1],
                distance_after_corner * math.sin(theta),
            )
        tangent = (math.cos(theta), 0.0, math.sin(theta))
        width_axis = (-math.sin(theta), 0.0, math.cos(theta))
    else:
        raise ValueError(f"Unknown path: {path}.")
    height_axis = _cross(tangent, width_axis)
    if roll_total_degrees:
        roll = math.radians(roll_total_degrees * fraction)
        width_axis = tuple(
            math.cos(roll) * width_axis[index] + math.sin(roll) * height_axis[index]
            for index in range(3)
        )
        height_axis = _cross(tangent, width_axis)
    return center, tangent, width_axis, height_axis


def _vector_between(
    first: adsk.core.Point3D, second: adsk.core.Point3D
) -> tuple[float, float, float]:
    """
    Return the vector from one measured sketch point to another.
    """
    return second.x - first.x, second.y - first.y, second.z - first.z


def _frame_change_degrees(
    first: tuple[
        adsk.core.Point3D,
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
    second: tuple[
        adsk.core.Point3D,
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
) -> float:
    """
    Measure the full rigid-frame rotation between two neighboring gates.
    """
    trace = sum(_dot(first[index], second[index]) for index in (1, 2, 3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def _add_profile(
    root: adsk.fusion.Component,
    label: str,
    station: int,
    intervals: int,
    aspect_ratio: int,
    path: str,
    offset_xy: tuple[float, float],
    roll_total_degrees: float,
    kink_degrees: float,
) -> tuple[adsk.fusion.Profile, tuple[adsk.core.Point3D, ...], dict[str, float]]:
    """
    Draw one closed tangent-normal rectangle and measure its actual corners.
    """
    center, tangent, width_axis, height_axis = _frame(
        path, station / intervals, offset_xy, roll_total_degrees, kink_degrees
    )
    plane = adsk.core.Plane.create(center, adsk.core.Vector3D.create(*tangent))
    if plane is None:
        raise RuntimeError(f"{label}: station {station} plane could not be defined.")
    plane_input = root.constructionPlanes.createInput()
    if not plane_input.setByPlane(plane):
        raise RuntimeError(f"{label}: station {station} plane could not be set.")
    construction_plane = root.constructionPlanes.add(plane_input)
    if construction_plane is None:
        raise RuntimeError(f"{label}: station {station} plane could not be created.")
    construction_plane.name = f"{label} plane {station}"
    sketch = root.sketches.add(construction_plane)
    if sketch is None:
        raise RuntimeError(f"{label}: station {station} sketch could not be created.")
    sketch.name = f"{label} section {station}"
    half_width = WIDTH_CM / 2.0
    half_height = WIDTH_CM * aspect_ratio / 2.0
    corners = tuple(
        adsk.core.Point3D.create(
            center.x + u * width_axis[0] + v * height_axis[0],
            center.y + u * width_axis[1] + v * height_axis[1],
            center.z + u * width_axis[2] + v * height_axis[2],
        )
        for u, v in (
            (-half_width, -half_height),
            (half_width, -half_height),
            (half_width, half_height),
            (-half_width, half_height),
        )
    )
    sketch_corners = tuple(sketch.modelToSketchSpace(corner) for corner in corners)
    lines: list[adsk.fusion.SketchLine] = []
    for first, second in zip(sketch_corners, (*sketch_corners[1:], sketch_corners[0])):
        line = sketch.sketchCurves.sketchLines.addByTwoPoints(first, second)
        if line is None:
            raise RuntimeError(f"{label}: station {station} line could not be created.")
        lines.append(line)
    marker = sketch.sketchCurves.sketchLines.addByTwoPoints(
        sketch.modelToSketchSpace(center), sketch_corners[0]
    )
    if marker is None:
        raise RuntimeError(f"{label}: station {station} marker could not be created.")
    marker.isConstruction = True
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{label}: station {station} has {sketch.profiles.count} profiles.")
    measured = tuple(line.startSketchPoint.worldGeometry for line in lines)
    edges = tuple(
        _unit(_vector_between(measured[index], measured[(index + 1) % 4])) for index in range(4)
    )
    maximum_right_angle_error = max(
        abs(
            90.0
            - math.degrees(math.acos(max(-1.0, min(1.0, -_dot(edges[index - 1], edges[index])))))
        )
        for index in range(4)
    )
    measured_normal = _unit(_cross(edges[0], edges[3]))
    maximum_corner_error_mm = max(
        measured[index].distanceTo(corners[index]) * 10.0 for index in range(4)
    )
    metrics = {
        "maximum_right_angle_error_degrees": maximum_right_angle_error,
        "maximum_corner_error_mm": maximum_corner_error_mm,
        "normal_tangent_dot": abs(_dot(measured_normal, tangent)),
    }
    if maximum_right_angle_error > 0.01 or maximum_corner_error_mm > 0.01:
        raise RuntimeError(
            f"{label}: station {station} sketch geometry is not a right rectangle: {metrics}."
        )
    return sketch.profiles.item(0), corners, metrics


def _face_corner_indices(
    face: adsk.fusion.BRepFace, corners: tuple[adsk.core.Point3D, ...]
) -> list[int]:
    """
    Identify section corners on a BRep face within 0.01 mm.
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
    start: tuple[adsk.core.Point3D, ...],
    end: tuple[adsk.core.Point3D, ...],
) -> dict[str, object]:
    """
    Check whether four lateral faces preserve logical edge identity.
    """
    mappings = []
    for face_index in range(body.faces.count):
        face = body.faces.item(face_index)
        start_indices = _face_corner_indices(face, start)
        end_indices = _face_corner_indices(face, end)
        if start_indices or end_indices:
            mappings.append({"start": start_indices, "end": end_indices})
    matched = {
        tuple(mapping["start"])
        for mapping in mappings
        if len(mapping["start"]) == 2 and mapping["start"] == mapping["end"]
    }
    expected = {(0, 1), (1, 2), (2, 3), (0, 3)}
    return {
        "solid": body.isSolid,
        "faces": body.faces.count,
        "volume_cm3": body.volume,
        "end_face_mappings": mappings,
        "corner_correspondence": "clean"
        if body.faces.count == 6 and matched == expected
        else "deviation_or_unresolved",
    }


def run(_context: object) -> None:
    """
    Build tangent-aligned lofts and leave the unsaved diagnostic design open.
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
            (path, ratio, step, 0.0, 0.0)
            for path, steps in (("u_turn", (20, 30, 45, 60)), ("helix", (20, 30, 40, 45, 60)))
            for ratio in (2, 5)
            for step in steps
        ]
        cases.extend(
            (path, ratio, step, roll, 0.0)
            for path in ("u_turn", "helix")
            for ratio in (2, 5)
            for roll, steps in ((180.0, (30,)), (360.0, (30, 20, 15, 10)))
            for step in steps
        )
        cases.extend(
            ("kink", ratio, 0, 0.0, float(angle))
            for ratio in (2, 5)
            for angle in (30, 45, 60, 90, 120)
        )
        for case_index, (path, ratio, step, roll, kink) in enumerate(cases):
            total_degrees = 180 if path == "u_turn" else 360 if path == "helix" else kink
            intervals = 3 if path == "kink" else int(total_degrees // step)
            label = f"{path} 1:{ratio} roll {roll:g} kink {kink:g} step {step}"
            offset_xy = ((case_index % 5) * 100.0, (case_index // 5) * 100.0)
            case: dict[str, object] = {
                "label": label,
                "path": path,
                "aspect_ratio": ratio,
                "intervals": intervals,
                "step_degrees": None if path == "kink" else total_degrees / intervals,
                "total_turn_degrees": total_degrees,
                "roll_total_degrees": roll,
                "kink_degrees": kink,
                "guide_rails": 0,
            }
            case_reports.append(case)
            try:
                profiles: list[adsk.fusion.Profile] = []
                corners: list[tuple[adsk.core.Point3D, ...]] = []
                metrics: list[dict[str, float]] = []
                frames = []
                for station in range(intervals + 1):
                    frame = _frame(path, station / intervals, offset_xy, roll, kink)
                    frames.append(frame)
                    profile, profile_corners, profile_metrics = _add_profile(
                        root, label, station, intervals, ratio, path, offset_xy, roll, kink
                    )
                    profiles.append(profile)
                    corners.append(profile_corners)
                    metrics.append(profile_metrics)
                case["maximum_right_angle_error_degrees"] = max(
                    item["maximum_right_angle_error_degrees"] for item in metrics
                )
                case["maximum_corner_error_mm"] = max(
                    item["maximum_corner_error_mm"] for item in metrics
                )
                case["minimum_normal_tangent_dot"] = min(
                    item["normal_tangent_dot"] for item in metrics
                )
                case["minimum_chord_tangent_dot"] = min(
                    _dot(
                        _unit(_vector_between(frames[index][0], frames[index + 1][0])),
                        frames[index][1],
                    )
                    for index in range(intervals)
                )
                case["maximum_frame_step_degrees"] = max(
                    _frame_change_degrees(frames[index], frames[index + 1])
                    for index in range(intervals)
                )
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
                    _inspect_body(loft.bodies.item(index), corners[0], corners[-1])
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
        print("TANGENT_SPAGHETTI_LOFT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
