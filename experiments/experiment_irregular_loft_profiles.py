"""
Probe face identity when asymmetric polygon and arc sections evolve between gates.

Run with ``Python.Run`` in Fusion while no command is active. The unsaved
scratch design remains open; the JSON report is under artifacts/verification.
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
from experiments.experiment_tangent_spaghetti_loft import _frame, _frame_change_degrees


def _section_points(
    shape_fraction: float, rotation_fraction: float, curved: bool, internal_turn_degrees: float
) -> tuple[tuple[float, float], ...]:
    """
    Return five labeled, asymmetric perimeter vertices in section coordinates.

    The angular progression is applied to geometry inside each sketch plane,
    independently of the route-tangent frame. Vertex offsets also vary from
    station to station when shape variation is enabled, removing rotational
    symmetry without relying on sketch-curve order.
    """
    sway = math.sin(2.0 * math.pi * shape_fraction)
    points = (
        (-1.2, -3.0),
        (1.0 + 0.20 * sway, -3.2),
        (1.35, 1.25 + 0.25 * sway),
        (0.10 - 0.15 * sway, 3.1),
        (-1.0, 2.45 - 0.20 * sway),
    )
    if curved:
        points = (points[0], (1.0, -3.2), (1.35, 1.25), points[3], points[4])
    theta = math.radians(internal_turn_degrees * rotation_fraction)
    cosine, sine = math.cos(theta), math.sin(theta)
    return tuple((cosine * x - sine * y, sine * x + cosine * y) for x, y in points)


def _add_section(
    root: adsk.fusion.Component,
    label: str,
    station: int,
    intervals: int,
    path: str,
    roll: float,
    kink: float,
    curved: bool,
    internal_turn: float,
    morph: bool,
    offset_xy: tuple[float, float],
) -> tuple[adsk.fusion.Profile, tuple[adsk.core.Point3D, ...]]:
    """
    Draw a five-edge section; curved sections replace edge 1 with one arc.
    """
    fraction = station / intervals
    center, tangent, width_axis, height_axis = _frame(path, fraction, offset_xy, roll, kink)
    plane = adsk.core.Plane.create(center, adsk.core.Vector3D.create(*tangent))
    if plane is None:
        raise RuntimeError(f"{label}: station {station} has no plane.")
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

    shape_fraction = fraction if morph else 0.0
    coordinates = _section_points(shape_fraction, fraction, curved, internal_turn)
    corners = tuple(
        adsk.core.Point3D.create(
            center.x + x * width_axis[0] + y * height_axis[0],
            center.y + x * width_axis[1] + y * height_axis[1],
            center.z + x * width_axis[2] + y * height_axis[2],
        )
        for x, y in coordinates
    )
    sketch_points = tuple(sketch.modelToSketchSpace(corner) for corner in corners)
    for edge_index in range(5):
        start = sketch_points[edge_index]
        end = sketch_points[(edge_index + 1) % 5]
        if curved and edge_index == 1:
            middle_x = (1.0 + 1.35) / 2.0 + 0.8 + 0.25 * math.cos(2.0 * math.pi * shape_fraction)
            middle_y = (-3.2 + 1.25) / 2.0
            theta = math.radians(internal_turn * fraction)
            # Rotate the arc's outward bulge with its end vertices.
            middle_x, middle_y = (
                math.cos(theta) * middle_x - math.sin(theta) * middle_y,
                math.sin(theta) * middle_x + math.cos(theta) * middle_y,
            )
            middle = adsk.core.Point3D.create(
                center.x + middle_x * width_axis[0] + middle_y * height_axis[0],
                center.y + middle_x * width_axis[1] + middle_y * height_axis[1],
                center.z + middle_x * width_axis[2] + middle_y * height_axis[2],
            )
            curve = sketch.sketchCurves.sketchArcs.addByThreePoints(
                start, sketch.modelToSketchSpace(middle), end
            )
        else:
            curve = sketch.sketchCurves.sketchLines.addByTwoPoints(start, end)
        if curve is None:
            raise RuntimeError(f"{label}: station {station} edge {edge_index} failed.")
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{label}: station {station} has {sketch.profiles.count} profiles.")
    return sketch.profiles.item(0), corners


def _corner_indices(
    face: adsk.fusion.BRepFace, corners: tuple[adsk.core.Point3D, ...]
) -> list[int]:
    """
    Find labeled section vertices on a BRep face within 0.01 mm.
    """
    result: set[int] = set()
    for vertex_index in range(face.vertices.count):
        vertex = face.vertices.item(vertex_index).geometry
        for corner_index, corner in enumerate(corners):
            if vertex.distanceTo(corner) < 0.001:
                result.add(corner_index)
    return sorted(result)


def _inspect_body(
    body: adsk.fusion.BRepBody,
    start: tuple[adsk.core.Point3D, ...],
    end: tuple[adsk.core.Point3D, ...],
) -> dict[str, object]:
    """
    Compare each lateral face's labeled edge at the first and last section.
    """
    mappings = [
        {
            "start": _corner_indices(body.faces.item(face_index), start),
            "end": _corner_indices(body.faces.item(face_index), end),
        }
        for face_index in range(body.faces.count)
    ]
    expected = {tuple(sorted((index, (index + 1) % 5))) for index in range(5)}
    matched = {
        tuple(mapping["start"])
        for mapping in mappings
        if len(mapping["start"]) == 2 and mapping["start"] == mapping["end"]
    }
    return {
        "solid": body.isSolid,
        "faces": body.faces.count,
        "volume_cm3": body.volume,
        "edge_mappings": mappings,
        "correspondence": "clean"
        if body.isSolid and body.faces.count == 7 and matched == expected
        else "deviation_or_unresolved",
    }


def run(_context: object) -> None:
    """
    Create irregular lofts in a fresh unsaved design and record mappings.
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
            raise RuntimeError("The scratch document is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        cases = [
            (curved, "kink", 0.0, 0.0, 180.0, step, True)
            for curved in (False, True)
            for step in (15, 20, 25, 30, 36, 45, 60)
        ]
        cases.extend(
            (curved, path, roll, kink, internal_turn, step, True)
            for curved in (False, True)
            for path, roll, kink, internal_turn, step in (
                ("u_turn", 360.0, 0.0, 0.0, 20),
                ("helix", 360.0, 0.0, 0.0, 30),
                ("kink", 0.0, 90.0, 90.0, 30),
            )
        )
        cases.extend(
            (curved, "kink", 0.0, 0.0, turn, step, False)
            for curved in (False, True)
            for turn, step in ((0.0, 30), (180.0, 20), (180.0, 30), (180.0, 45))
        )
        for case_index, (curved, path, roll, kink, internal_turn, step, morph) in enumerate(cases):
            total = 180 if path == "u_turn" else 360 if path == "helix" else 180
            intervals = int(total // step) if kink == 0 else 3
            label = (
                f"{'arc' if curved else 'polygon'} {path} "
                f"roll {roll:g} kink {kink:g} internal {internal_turn:g} "
                f"step {step} morph {morph}"
            )
            case: dict[str, object] = {
                "label": label,
                "profile": "arc" if curved else "polygon",
                "path": path,
                "roll_degrees": roll,
                "kink_degrees": kink,
                "internal_turn_degrees": internal_turn,
                "morph": morph,
                "intervals": intervals,
                "guide_rails": 0,
            }
            case_reports.append(case)
            try:
                offset = ((case_index % 4) * 120.0, (case_index // 4) * 120.0)
                profiles: list[adsk.fusion.Profile] = []
                corners: list[tuple[adsk.core.Point3D, ...]] = []
                frames = []
                for station in range(intervals + 1):
                    fraction = station / intervals
                    frames.append(_frame(path, fraction, offset, roll, kink))
                    profile, section_corners = _add_section(
                        root,
                        label,
                        station,
                        intervals,
                        path,
                        roll,
                        kink,
                        curved,
                        internal_turn,
                        morph,
                        offset,
                    )
                    profiles.append(profile)
                    corners.append(section_corners)
                case["maximum_frame_step_degrees"] = max(
                    _frame_change_degrees(frames[index], frames[index + 1])
                    for index in range(intervals)
                )
                case["internal_step_degrees"] = internal_turn / intervals
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
                    if len(bodies) == 1 and bodies[0]["correspondence"] == "clean"
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
            / "artifacts/verification/irregular_loft_profiles.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("IRREGULAR_LOFT_PROFILES=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
