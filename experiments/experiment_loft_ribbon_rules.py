"""
Probe finite, trace-sized rectangular lofts for stable four-face correspondence.

Run with ``Python.Run`` in Fusion while no command is active. The probe creates
and closes one unsaved scratch design and writes an ignored JSON report.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_loft_seam_rail import _add_vertex_rail
from experiments.experiment_tangent_spaghetti_loft import _frame, _frame_change_degrees


def _section(
    root: adsk.fusion.Component,
    label: str,
    station: int,
    intervals: int,
    path: str,
    roll_degrees: float,
    width_cm: float,
    thickness_cm: float,
    offset: tuple[float, float],
) -> tuple[adsk.fusion.Profile, tuple[adsk.core.Point3D, ...]]:
    """
    Draw a tangent-normal rectangle with a labeled first corner and fixed winding.
    """
    center, tangent, width_axis, height_axis = _frame(
        path, station / intervals, offset, roll_degrees
    )
    plane = adsk.core.Plane.create(center, adsk.core.Vector3D.create(*tangent))
    plane_input = root.constructionPlanes.createInput()
    if not plane_input.setByPlane(plane):
        raise RuntimeError(f"{label}: station {station} has no section plane.")
    construction_plane = root.constructionPlanes.add(plane_input)
    if construction_plane is None:
        raise RuntimeError(f"{label}: station {station} plane could not be created.")
    sketch = root.sketches.add(construction_plane)
    sketch.name = f"{label} section {station}"
    corners = tuple(
        adsk.core.Point3D.create(
            center.x + u * width_axis[0] + v * height_axis[0],
            center.y + u * width_axis[1] + v * height_axis[1],
            center.z + u * width_axis[2] + v * height_axis[2],
        )
        for u, v in (
            (-width_cm / 2, -thickness_cm / 2),
            (width_cm / 2, -thickness_cm / 2),
            (width_cm / 2, thickness_cm / 2),
            (-width_cm / 2, thickness_cm / 2),
        )
    )
    sketch_corners = tuple(sketch.modelToSketchSpace(point) for point in corners)
    for first, second in zip(sketch_corners, (*sketch_corners[1:], sketch_corners[0])):
        if sketch.sketchCurves.sketchLines.addByTwoPoints(first, second) is None:
            raise RuntimeError(f"{label}: station {station} edge could not be drawn.")
    marker = sketch.sketchCurves.sketchLines.addByTwoPoints(
        sketch.modelToSketchSpace(center), sketch_corners[0]
    )
    if marker is None:
        raise RuntimeError(f"{label}: station {station} marker could not be drawn.")
    marker.isConstruction = True
    if sketch.profiles.count != 1:
        raise RuntimeError(f"{label}: station {station} has {sketch.profiles.count} profiles.")
    return sketch.profiles.item(0), corners


def _face_vertices(face: adsk.fusion.BRepFace, corners: tuple[adsk.core.Point3D, ...]) -> list[int]:
    """
    Locate labeled gate vertices incident to a body face within 0.01 mm.
    """
    return sorted(
        {
            index
            for vertex_index in range(face.vertices.count)
            for index, point in enumerate(corners)
            if face.vertices.item(vertex_index).geometry.distanceTo(point) < 0.001
        }
    )


def _inspect(
    body: adsk.fusion.BRepBody,
    profiles: list[adsk.fusion.Profile],
    corners: list[tuple[adsk.core.Point3D, ...]],
    tolerance_cm: float,
) -> dict[str, object]:
    """
    Require one face per labeled side from the first through every later gate.
    """
    face_by_side: dict[int, int] = {}
    cap_faces = {
        index
        for index in range(body.faces.count)
        if len(_face_vertices(body.faces.item(index), corners[0])) == 4
        or len(_face_vertices(body.faces.item(index), corners[-1])) == 4
    }
    for face_index in range(body.faces.count):
        start = _face_vertices(body.faces.item(face_index), corners[0])
        for side in range(4):
            if start == sorted((side, (side + 1) % 4)):
                face_by_side[side] = face_index
    misses: list[dict[str, object]] = []
    for station in range(1, len(profiles)):
        for side in range(4):
            first, second = corners[station][side], corners[station][(side + 1) % 4]
            midpoint = adsk.core.Point3D.create(
                (first.x + second.x) / 2,
                (first.y + second.y) / 2,
                (first.z + second.z) / 2,
            )
            hits = [
                index
                for index in range(body.faces.count)
                if index not in cap_faces
                and body.faces.item(index).isPointOnFace(midpoint, tolerance_cm)
            ]
            if hits != [face_by_side.get(side)]:
                misses.append({"station": station, "side": side, "hits": hits})
    return {
        "solid": body.isSolid,
        "face_count": body.faces.count,
        "volume_cm3": body.physicalProperties.volume,
        "identified_sides": sorted(face_by_side),
        "sample_count": (len(profiles) - 1) * 4,
        "miss_count": len(misses),
        "first_misses": misses[:12],
        "clean": body.isSolid and body.faces.count == 6 and len(face_by_side) == 4 and not misses,
    }


def _expected_result(
    path: str, roll_degrees: float, intervals: int, vertices: tuple[int, ...]
) -> str:
    """
    Encode the observed matrix so future Fusion runs expose changed outcomes.
    """
    if intervals != 4 or roll_degrees != 360.0:
        return "clean"
    if not vertices:
        return "deviation"
    if path == "u_turn" and vertices == (0, 2):
        return "clean"
    return "failed"


def run(_context: object) -> None:
    """
    Compare unrailed, single-key, and two-key lofts at finite gate densities.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the scratch design.")
    report: dict[str, object] = {"document": scratch.name, "cases": []}
    cases: list[dict[str, object]] = report["cases"]
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is None:
            raise RuntimeError("The scratch document is not a Fusion design.")
        design.designType = adsk.fusion.DesignTypes.DirectDesignType
        root = design.rootComponent
        dimensions = ((1.0, 0.05), (0.1, 0.01))  # cm: 10 x 0.5 and 1 x 0.1 mm
        routes = (("u_turn", 180.0), ("u_turn", 360.0), ("helix", 360.0))
        intervals_set = (4, 8, 12, 24)
        rail_sets = ((), (0,), (0, 2))
        case_index = 0
        for width_cm, thickness_cm in dimensions:
            for path, roll_degrees in routes:
                for intervals in intervals_set:
                    for vertices in rail_sets:
                        label = (
                            f"ribbon {width_cm:g}x{thickness_cm:g} {path} "
                            f"roll {roll_degrees:g} n{intervals} rails {vertices}"
                        )
                        case: dict[str, object] = {
                            "width_mm": width_cm * 10,
                            "thickness_mm": thickness_cm * 10,
                            "path": path,
                            "roll_degrees": roll_degrees,
                            "intervals": intervals,
                            "rail_vertices": list(vertices),
                            "roll_step_degrees": roll_degrees / intervals,
                            "expected_result": _expected_result(
                                path, roll_degrees, intervals, vertices
                            ),
                        }
                        cases.append(case)
                        try:
                            offset = ((case_index % 9) * 100.0, (case_index // 9) * 100.0)
                            frames = [
                                _frame(path, station / intervals, offset, roll_degrees)
                                for station in range(intervals + 1)
                            ]
                            case["maximum_frame_step_degrees"] = max(
                                _frame_change_degrees(frames[index], frames[index + 1])
                                for index in range(intervals)
                            )
                            profiles: list[adsk.fusion.Profile] = []
                            corners: list[tuple[adsk.core.Point3D, ...]] = []
                            for station in range(intervals + 1):
                                profile, points = _section(
                                    root,
                                    label,
                                    station,
                                    intervals,
                                    path,
                                    roll_degrees,
                                    width_cm,
                                    thickness_cm,
                                    offset,
                                )
                                profiles.append(profile)
                                corners.append(points)
                            loft_input = root.features.loftFeatures.createInput(
                                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                            )
                            loft_input.isSolid = True
                            for profile in profiles:
                                loft_input.loftSections.add(profile)
                            for vertex in vertices:
                                rail, gap = _add_vertex_rail(root, label, corners, vertex)
                                case[f"rail_{vertex}_max_gate_gap_cm"] = gap
                                if gap > 0.001:
                                    raise RuntimeError(
                                        f"Rail {vertex} missed a gate by {gap:g} cm."
                                    )
                                if loft_input.centerLineOrRails.addRail(rail) is None:
                                    raise RuntimeError(f"Fusion refused vertex {vertex} rail.")
                            loft = root.features.loftFeatures.add(loft_input)
                            if loft is None:
                                code, detail = application.getLastError()
                                raise RuntimeError(f"Fusion rejected loft ({code}: {detail}).")
                            case["body_count"] = loft.bodies.count
                            if loft.bodies.count != 1:
                                case["result"] = "body_count"
                            else:
                                inspected = _inspect(
                                    loft.bodies.item(0),
                                    profiles,
                                    corners,
                                    application.pointTolerance * 10,
                                )
                                case["inspection"] = inspected
                                case["result"] = "clean" if inspected["clean"] else "deviation"
                        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                            case["result"] = "failed"
                            case["error"] = str(error)
                        case["regression"] = case["result"] != case["expected_result"]
                        case_index += 1
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["fatal_error"] = str(error)
    finally:
        scratch.close(False)
        report["scratch_closed"] = True
        report["unexpected_cases"] = [
            index for index, case in enumerate(cases) if case.get("regression")
        ]
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / "artifacts/verification/loft_ribbon_rules.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("LOFT_RIBBON_RULES=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
