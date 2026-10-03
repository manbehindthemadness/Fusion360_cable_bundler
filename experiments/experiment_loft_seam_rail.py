"""
Compare unrailed and vertex-railed loft correspondence on known failure cases.

Run with ``Python.Run`` in Fusion while no command is active. This creates and
closes one unsaved scratch design and writes a JSON report under
artifacts/verification. It does not modify the add-in's generation code or any
saved design.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_irregular_loft_profiles import (
    _add_section,
    _corner_indices,
    _inspect_body,
)


def _edge_sample(
    profile: adsk.fusion.Profile,
    corners: tuple[adsk.core.Point3D, ...],
    edge: int,
    curved: bool,
) -> adsk.core.Point3D:
    """
    Return an interior point on a labeled section edge, including the arc.
    """
    if curved and edge == 1:
        arc = profile.parentSketch.sketchCurves.sketchArcs.item(0)
        evaluator = arc.worldGeometry.evaluator
        success, start, end = evaluator.getParameterExtents()
        if not success:
            raise RuntimeError("The section arc has no parameter extents.")
        success, point = evaluator.getPointAtParameter((start + end) / 2.0)
        if not success:
            raise RuntimeError("The section arc midpoint could not be evaluated.")
        return point
    start = corners[edge]
    end = corners[(edge + 1) % 5]
    return adsk.core.Point3D.create(
        (start.x + end.x) / 2.0,
        (start.y + end.y) / 2.0,
        (start.z + end.z) / 2.0,
    )


def _inspect_interior(
    body: adsk.fusion.BRepBody,
    profiles: list[adsk.fusion.Profile],
    corners: list[tuple[adsk.core.Point3D, ...]],
    curved: bool,
    tolerance_cm: float,
) -> dict[str, object]:
    """
    Check that each interior labeled edge stays on its start-labeled face.
    """
    face_by_edge: dict[int, int] = {}
    for face_index in range(body.faces.count):
        start_indices = _corner_indices(body.faces.item(face_index), corners[0])
        if len(start_indices) != 2:
            continue
        for edge in range(5):
            if start_indices == sorted((edge, (edge + 1) % 5)):
                face_by_edge[edge] = face_index
    misses: list[dict[str, object]] = []
    for station in range(1, len(profiles) - 1):
        for edge in range(5):
            point = _edge_sample(profiles[station], corners[station], edge, curved)
            hits = [
                face_index
                for face_index in range(body.faces.count)
                if body.faces.item(face_index).isPointOnFace(point, tolerance_cm)
            ]
            expected = face_by_edge.get(edge)
            if expected is None or hits != [expected]:
                misses.append(
                    {
                        "station": station,
                        "edge": edge,
                        "expected_face": expected,
                        "hit_faces": hits,
                    }
                )
    return {
        "sample_count": (len(profiles) - 2) * 5,
        "miss_count": len(misses),
        "first_misses": misses[:20],
    }


def _add_vertex_rail(
    root: adsk.fusion.Component,
    label: str,
    corners: list[tuple[adsk.core.Point3D, ...]],
    vertex: int,
) -> tuple[adsk.fusion.SketchFittedSpline, float]:
    """
    Fit a rail through one labeled vertex and measure its actual gate contact.
    """
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.name = f"{label} vertex {vertex} rail"
    points = adsk.core.ObjectCollection.create()
    for section in corners:
        points.add(section[vertex])
    spline = sketch.sketchCurves.sketchFittedSplines.add(points)
    if spline is None:
        raise RuntimeError(f"{label}: vertex {vertex} spline could not be created.")
    evaluator = spline.worldGeometry.evaluator
    maximum_gap = 0.0
    for section in corners:
        success, parameter = evaluator.getParameterAtPoint(section[vertex])
        if not success:
            raise RuntimeError(f"{label}: vertex {vertex} rail could not be evaluated.")
        success, closest = evaluator.getPointAtParameter(parameter)
        if not success:
            raise RuntimeError(f"{label}: vertex {vertex} rail point could not be evaluated.")
        maximum_gap = max(maximum_gap, closest.distanceTo(section[vertex]))
    return spline, maximum_gap


def run(_context: object) -> None:
    """
    Build controlled matched cases and record correspondence or API rejection.
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
        geometries = (
            ("polygon_30", False, 6, True, "kink", 0.0, 180.0),
            ("polygon_45", False, 4, True, "kink", 0.0, 180.0),
            ("arc_morph_30", True, 6, True, "kink", 0.0, 180.0),
            ("arc_fixed_30", True, 6, False, "kink", 0.0, 180.0),
            ("polygon_u_turn_360", False, 9, True, "u_turn", 360.0, 0.0),
            ("arc_u_turn_360", True, 9, True, "u_turn", 360.0, 0.0),
            ("arc_helix_360", True, 12, True, "helix", 360.0, 0.0),
        )
        rail_sets = ((), (0,), (0, 2))
        for geometry_index, (
            name,
            curved,
            intervals,
            morph,
            path,
            roll,
            internal_turn,
        ) in enumerate(geometries):
            for rail_index, vertices in enumerate(rail_sets):
                label = f"seam_probe {name} rails {','.join(map(str, vertices)) or 'none'}"
                case: dict[str, object] = {
                    "geometry": name,
                    "curved": curved,
                    "path": path,
                    "roll_degrees": roll,
                    "internal_turn_degrees": internal_turn,
                    "internal_step_degrees": internal_turn / intervals,
                    "morph": morph,
                    "rail_vertices": list(vertices),
                }
                cases.append(case)
                try:
                    offset = (geometry_index * 100.0, rail_index * 100.0)
                    profiles: list[adsk.fusion.Profile] = []
                    corners: list[tuple[adsk.core.Point3D, ...]] = []
                    for station in range(intervals + 1):
                        profile, section_corners = _add_section(
                            root,
                            label,
                            station,
                            intervals,
                            path,
                            roll,
                            0.0,
                            curved,
                            internal_turn,
                            morph,
                            offset,
                        )
                        profiles.append(profile)
                        corners.append(section_corners)
                    loft_input = root.features.loftFeatures.createInput(
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                    )
                    loft_input.isSolid = True
                    for profile in profiles:
                        loft_input.loftSections.add(profile)
                    for vertex in vertices:
                        rail, maximum_gap = _add_vertex_rail(root, label, corners, vertex)
                        case[f"rail_{vertex}_max_gate_gap_cm"] = maximum_gap
                        if maximum_gap > 0.001:
                            raise RuntimeError(
                                f"Rail {vertex} missed a gate by {maximum_gap:.6g} cm."
                            )
                        added = loft_input.centerLineOrRails.addRail(rail)
                        if added is None:
                            raise RuntimeError(f"Fusion refused vertex {vertex} rail input.")
                    loft = root.features.loftFeatures.add(loft_input)
                    if loft is None:
                        error_code, detail = application.getLastError()
                        raise RuntimeError(f"Fusion rejected loft ({error_code}: {detail}).")
                    bodies = [
                        _inspect_body(loft.bodies.item(index), corners[0], corners[-1])
                        for index in range(loft.bodies.count)
                    ]
                    case["body_count"] = len(bodies)
                    case["bodies"] = bodies
                    if len(bodies) == 1:
                        case["interior"] = _inspect_interior(
                            loft.bodies.item(0),
                            profiles,
                            corners,
                            curved,
                            application.pointTolerance * 10.0,
                        )
                    case["result"] = (
                        "clean"
                        if (
                            len(bodies) == 1
                            and bodies[0]["correspondence"] == "clean"
                            and case["interior"]["miss_count"] == 0
                        )
                        else "deviation"
                    )
                except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                    case["result"] = "failed"
                    case["error"] = str(error)
        application.activeViewport.fit()
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        report["fatal_error"] = str(error)
    finally:
        scratch.close(False)
        report["scratch_closed"] = True
        output = (
            Path(cable_bundler.__file__).resolve().parents[1]
            / "artifacts/verification/loft_seam_rail.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("LOFT_SEAM_RAIL=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
