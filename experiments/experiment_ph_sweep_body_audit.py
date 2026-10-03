"""
Audit existing PH sweep solids without changing the open Fusion scratch.

Run with Fusion ``Python.Run`` after ``experiment_ph_spaghetti_sweep.py``.
The report distinguishes body topology, sampled side-face correspondence,
and an independent planar minimum-bend-radius criterion.
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
from experiments.experiment_ph_quintic import HermiteCase, PhQuintic, ph_hermite_candidates


def _sweep_body(root: adsk.fusion.Component, name: str, start_y_cm: float) -> adsk.fusion.BRepBody:
    """
    Match an isolated body to the path's independently saved Y location.

    Direct-mode Fusion assigns generic feature names despite the experiment's
    requested names. The stress cases are spaced 10 cm apart in Y.
    """
    candidates = [
        root.bRepBodies.item(index)
        for index in range(root.bRepBodies.count)
        if abs(root.bRepBodies.item(index).boundingBox.minPoint.y - start_y_cm) < 1.0
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"{name}: found {len(candidates)} bodies near Y={start_y_cm} cm.")
    return candidates[0]


def _start_y_cm(root: adsk.fusion.Component, name: str) -> float:
    """
    Read the generated path's world-space start to recover its scratch offset.
    """
    sketch = root.sketches.itemByName(f"{name} PH path")
    if sketch is None or sketch.sketchCurves.sketchControlPointSplines.count != 1:
        raise RuntimeError(f"{name}: missing the expected path sketch.")
    spline = sketch.sketchCurves.sketchControlPointSplines.item(0)
    return spline.controlPoints[0].worldGeometry.y


def _face_hits(
    body: adsk.fusion.BRepBody, point: adsk.core.Point3D, tolerance_cm: float
) -> list[int]:
    """
    Return all faces containing one predicted side midpoint.
    """
    return [
        index
        for index in range(body.faces.count)
        if body.faces.item(index).isPointOnFace(point, tolerance_cm)
    ]


def _cap_bridge_topology(body: adsk.fusion.BRepBody) -> dict[str, object]:
    """
    Check whether each of four side faces joins one start and one end edge.

    Both endpoint profiles lie in X=0 planes. This only tests topological
    continuity, not the precise interior roll trajectory of a side face.
    """
    vertices_by_face = [
        [face.vertices.item(index).geometry for index in range(face.vertices.count)]
        for face in (body.faces.item(index) for index in range(body.faces.count))
    ]
    cap_indices = [
        index
        for index, vertices in enumerate(vertices_by_face)
        if len(vertices) == 4
        and body.faces.item(index).geometry.objectType == adsk.core.Plane.classType()
        and abs(adsk.core.Plane.cast(body.faces.item(index).geometry).normal.x) > 0.999
        and all(abs(vertex.x) < 0.0001 for vertex in vertices)
    ]
    cap_indices.sort(key=lambda index: sum(vertex.y for vertex in vertices_by_face[index]) / 4.0)
    if len(cap_indices) != 2:
        return {"cap_indices": cap_indices, "four_side_bridges": False}
    cap_centers = [
        (
            sum(vertex.y for vertex in vertices_by_face[index]) / 4.0,
            sum(vertex.z for vertex in vertices_by_face[index]) / 4.0,
        )
        for index in cap_indices
    ]
    side_connections: list[dict[str, object]] = []
    for face_index, vertices in enumerate(vertices_by_face):
        if face_index in cap_indices:
            continue
        shared = [
            [
                vertex
                for vertex in vertices
                if any(
                    vertex.distanceTo(cap_vertex) < 0.0001 for cap_vertex in vertices_by_face[cap]
                )
            ]
            for cap in cap_indices
        ]
        labels: list[str] = []
        for cap_index, pair in enumerate(shared):
            if len(pair) != 2:
                labels.append("unresolved")
            elif abs(pair[0].z - pair[1].z) < 0.0001:
                labels.append("z+" if pair[0].z > cap_centers[cap_index][1] else "z-")
            elif abs(pair[0].y - pair[1].y) < 0.0001:
                labels.append("y+" if pair[0].y > cap_centers[cap_index][0] else "y-")
            else:
                labels.append("oblique")
        side_connections.append(
            {
                "face": face_index,
                "shared_cap_vertices": [len(pair) for pair in shared],
                "start_end_edge_labels": labels,
            }
        )
    return {
        "cap_indices": cap_indices,
        "side_connections": side_connections,
        "four_side_bridges": len(side_connections) == 4
        and all(connection["shared_cap_vertices"] == [2, 2] for connection in side_connections),
    }


def _sample_untwisted_sides(
    body: adsk.fusion.BRepBody,
    curve: PhQuintic,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Check four labeled ribbon side midpoints at seven interior stations.

    The PH curve remains in XY; the unrolled sweep's width direction is Z.
    A match must hit one face and preserve that face through all stations.
    """
    face_by_side: dict[str, int] = {}
    misses: list[dict[str, object]] = []
    for station in range(1, 8):
        parameter = station / 8.0
        position = curve.point_at(parameter)
        derivative = curve.derivative_at(parameter)
        speed = abs(derivative)
        if speed <= 1e-9:
            raise RuntimeError(f"The PH centerline is stationary at station {station}.")
        normal = complex(-derivative.imag, derivative.real) / speed
        for side, transverse_mm, height_mm in (
            ("thin_plus", 0.25, 0.0),
            ("thin_minus", -0.25, 0.0),
            ("width_plus", 0.0, 5.0),
            ("width_minus", 0.0, -5.0),
        ):
            expected = position + transverse_mm * normal
            world = adsk.core.Point3D.create(
                expected.real / 10.0,
                offset_y_cm + expected.imag / 10.0,
                height_mm / 10.0,
            )
            hits = _face_hits(body, world, 0.001)
            if station == 1 and len(hits) == 1:
                face_by_side[side] = hits[0]
            if hits != [face_by_side.get(side)]:
                misses.append({"station": station, "side": side, "hits": hits})
    return {
        "sample_count": 28,
        "face_by_side": face_by_side,
        "miss_count": len(misses),
        "first_misses": misses[:8],
        "distinct_side_faces": len(set(face_by_side.values())) == 4,
    }


def _sampled_minimum_radius_mm(curve: PhQuintic) -> float:
    """
    Screen the planar centerline at 4097 deterministic parameter values.
    """
    maximum_curvature = max(abs(curve.curvature_at(index / 4096.0)) for index in range(4097))
    return 1.0 / maximum_curvature if maximum_curvature > 0.0 else math.inf


def run(_context: object) -> None:
    """
    Compare one-body sweep outcomes with bend and face evidence in place.
    """
    application = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    root = design.rootComponent
    cases = (
        ("radius_h2_ribbon_10x0p5mm", 2.0, 25.0, True),
        ("radius_h5_ribbon_10x0p5mm", 5.0, 25.0, True),
        ("radius_h10_ribbon_10x0p5mm", 10.0, 25.0, True),
        ("radius_h20_ribbon_10x0p5mm", 20.0, 25.0, True),
        ("radius_h60_ribbon_10x0p5mm", 60.0, 25.0, True),
        ("roll_h10_a90", 10.0, 25.0, False),
        ("roll_h20_a360", 20.0, 25.0, False),
    )
    report: dict[str, object] = {
        "document": application.activeDocument.name,
        "minimum_bend_radius_criterion_mm": 12.0,
        "cases": [],
    }
    for name, separation_mm, derivative_mm, unrolled in cases:
        start_y_cm = _start_y_cm(root, name)
        body = _sweep_body(root, name, start_y_cm)
        curve = ph_hermite_candidates(
            HermiteCase(
                name,
                complex(0.0, separation_mm),
                complex(derivative_mm, 0.0),
                complex(-derivative_mm, 0.0),
            )
        )[0]
        minimum_radius = _sampled_minimum_radius_mm(curve)
        entry: dict[str, object] = {
            "name": name,
            "body_is_solid": body.isSolid,
            "body_face_count": body.faces.count,
            "body_volume_cm3": body.volume,
            "cap_bridge_topology": _cap_bridge_topology(body),
            "minimum_sampled_planar_radius_mm": minimum_radius,
            "passes_12mm_bend_criterion": minimum_radius >= 12.0,
        }
        if unrolled:
            entry["side_probe"] = _sample_untwisted_sides(body, curve, start_y_cm)
        report["cases"].append(entry)
    output = (
        Path(cable_bundler.__file__).resolve().parents[1]
        / "artifacts/verification/ph_sweep_body_audit.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PH_SWEEP_BODY_AUDIT="
        + json.dumps(
            {
                "cases": len(report["cases"]),
                "report": str(output),
                "document": report["document"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
