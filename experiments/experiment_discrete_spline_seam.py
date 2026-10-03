"""
Probe seam transport for a one-curve fitted Discrete-ribbon outline.

Run through Fusion ``Python.Run`` with no command active. The separate,
unsaved scratch remains open; existing documents are not edited or closed.
This isolates a perpendicular sweep, not the production guided sweep/loft.
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
from experiments.experiment_ph_fusion_sweep import _path_sketch
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates
from experiments.experiment_product_profile_sweeps import _section_report

CASES = (
    (3, 5.0, 0.0),
    (3, 5.0, 90.0),
    (3, 5.0, 180.0),
    (3, 10.0, 0.0),
    (3, 10.0, 90.0),
    (3, 10.0, 180.0),
    (5, 10.0, 0.0),
    (5, 10.0, 90.0),
    (5, 10.0, 180.0),
    (3, 3.0, 180.0),
    (5, 5.0, 180.0),
)


def _outline_points(lines: int) -> tuple[tuple[float, float], ...]:
    """
    Approximate 1 mm Discrete lobes in perimeter order from one cap tip.

    The first point is the explicit seam: the outside tip of the first cap.
    Duplicate junctions are omitted so the periodic fit has one curve.
    """
    radius = 0.5
    valley = radius * 0.6
    half_width = lines * radius
    cap_extension = radius * 0.2
    points: list[tuple[float, float]] = [(-half_width - cap_extension, 0.0)]
    points.append((-half_width, valley))
    for line in range(lines):
        left = -half_width + line
        for step in range(1, 7):
            fraction = step / 6.0
            points.append(
                (left + fraction, valley + (radius - valley) * math.sin(math.pi * fraction))
            )
    points.extend(((half_width + cap_extension, 0.0), (half_width, -valley)))
    for line in reversed(range(lines)):
        right = -half_width + line + 1.0
        for step in range(1, 7):
            fraction = step / 6.0
            points.append(
                (right - fraction, -valley - (radius - valley) * math.sin(math.pi * fraction))
            )
    return tuple(points)


def _profile(
    root: adsk.fusion.Component,
    path: adsk.fusion.Path,
    name: str,
    lines: int,
    offset_y_cm: float,
) -> tuple[adsk.fusion.Sketch, adsk.fusion.ConstructionPlane, adsk.core.Point3D]:
    """
    Make one periodic fitted spline on the path's starting normal plane.
    """
    plane_input = root.constructionPlanes.createInput()
    if not plane_input.setByPath(
        path,
        adsk.fusion.PathDistanceTypes.ProportionalPathDistanceType,
        adsk.core.ValueInput.createByReal(0.0),
    ):
        raise RuntimeError("Fusion could not place the fitted section plane.")
    plane = root.constructionPlanes.add(plane_input)
    if plane is None:
        raise RuntimeError("Fusion did not make the fitted section plane.")
    plane.name = f"{name} section plane"
    sketch = root.sketches.add(plane)
    if sketch is None:
        raise RuntimeError("Fusion did not make the fitted section sketch.")
    sketch.name = f"{name} fitted outline"
    points = adsk.core.ObjectCollection.create()
    outline = _outline_points(lines)
    for across_mm, height_mm in outline:
        world = adsk.core.Point3D.create(0.0, offset_y_cm + across_mm / 10.0, height_mm / 10.0)
        points.add(sketch.modelToSketchSpace(world))
    spline = sketch.sketchCurves.sketchFittedSplines.add(points)
    if spline is None:
        raise RuntimeError("Fusion could not fit the single outline curve.")
    spline.isClosed = True
    if not spline.isClosed or sketch.profiles.count != 1:
        raise RuntimeError("The fitted outline did not close as one profile.")
    profile = sketch.profiles.item(0)
    if profile.profileLoops.count != 1 or profile.profileLoops.item(0).profileCurves.count != 1:
        raise RuntimeError("Fusion split the fitted outline into multiple curves.")
    start_seam = spline.fitPoints.item(0).worldGeometry
    return sketch, plane, start_seam


def _coordinates(point: adsk.core.Point3D) -> list[float]:
    """
    Convert Fusion centimeter points to report millimeters.
    """
    return [point.x * 10.0, point.y * 10.0, point.z * 10.0]


def _distance_mm(a: adsk.core.Point3D, b: adsk.core.Point3D) -> float:
    """
    Measure a pair of Fusion points in millimeters.
    """
    return a.distanceTo(b) * 10.0


def _cap_seam(face: adsk.fusion.BRepFace) -> adsk.core.Point3D:
    """
    Retrieve the unique vertex of a one-edge periodic cap boundary.
    """
    if face.edges.count != 1:
        raise RuntimeError(f"The cap has {face.edges.count} edges, not one.")
    edge = face.edges.item(0)
    start = edge.startVertex
    end = edge.endVertex
    if start is None or end is None:
        raise RuntimeError("The cap boundary has no seam vertex.")
    if _distance_mm(start.geometry, end.geometry) > 1e-5:
        raise RuntimeError("The cap boundary does not close at one vertex.")
    return start.geometry


def _seam_report(
    feature: adsk.fusion.SweepFeature,
    start_fit_point: adsk.core.Point3D,
    seam_reach_mm: float,
    separation_mm: float,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Audit cap seam vertices, their joining edge, and expected banked tip.
    """
    starts = feature.startFaces
    ends = feature.endFaces
    if starts is None or ends is None or starts.count != 1 or ends.count != 1:
        raise RuntimeError("Fusion did not retain one start and one end cap.")
    start_seam = _cap_seam(starts.item(0))
    end_seam = _cap_seam(ends.item(0))
    connecting_edges = 0
    for index in range(feature.bodies.item(0).edges.count):
        edge = feature.bodies.item(0).edges.item(index)
        first = edge.startVertex
        last = edge.endVertex
        if first is None or last is None:
            continue
        if (
            _distance_mm(first.geometry, start_seam) < 1e-5
            and _distance_mm(last.geometry, end_seam) < 1e-5
        ) or (
            _distance_mm(last.geometry, start_seam) < 1e-5
            and _distance_mm(first.geometry, end_seam) < 1e-5
        ):
            connecting_edges += 1
    twist = math.radians(twist_degrees)
    center_y_mm = offset_y_cm * 10.0 + separation_mm
    expected_y_mm = center_y_mm + seam_reach_mm * math.cos(twist)
    expected_z_mm = -seam_reach_mm * math.sin(twist)
    actual = _coordinates(end_seam)
    expected_error_mm = math.hypot(actual[1] - expected_y_mm, actual[2] - expected_z_mm)
    return {
        "start_fit_point_mm": _coordinates(start_fit_point),
        "start_cap_seam_mm": _coordinates(start_seam),
        "start_fit_to_cap_seam_mm": _distance_mm(start_fit_point, start_seam),
        "end_cap_seam_mm": actual,
        "expected_end_tip_mm": [0.0, expected_y_mm, expected_z_mm],
        "end_tip_error_mm": expected_error_mm,
        "connecting_seam_edges": connecting_edges,
        "side_face_count": feature.sideFaces.count,
        "start_cap_edge_count": starts.item(0).edges.count,
        "end_cap_edge_count": ends.item(0).edges.count,
    }


def _case(
    root: adsk.fusion.Component,
    lines: int,
    separation_mm: float,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Sweep one periodic fitted outline through a PH reversal.
    """
    name = f"fit_{lines}_h{separation_mm:g}_twist{twist_degrees:g}"
    row: dict[str, object] = {
        "name": name,
        "lines": lines,
        "separation_mm": separation_mm,
        "twist_degrees": twist_degrees,
    }
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation_mm), 25.0 + 0j, -25.0 + 0j)
    )[0]
    path_sketch, path_spline = _path_sketch(root, name, curve.controls, offset_y_cm)
    path = root.features.createPath(path_spline, False)
    section, plane, start_fit_point = _profile(root, path, name, lines, offset_y_cm)
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
        raise RuntimeError("Fusion did not make one fitted-profile sweep.")
    feature.name = name
    body = feature.bodies.item(0)
    row.update(
        {
            "result": "solid" if body.isSolid else "non_solid",
            "body_face_count": body.faces.count,
            "body_edge_count": body.edges.count,
        }
    )
    row["seam"] = _seam_report(
        feature, start_fit_point, (lines + 0.2) / 2.0, separation_mm, twist_degrees, offset_y_cm
    )
    if body.isSolid:
        row["midpoint_section"] = _section_report(body, curve, offset_y_cm)
    path_sketch.isLightBulbOn = False
    section.isLightBulbOn = False
    plane.isLightBulbOn = False
    return row


def run(_context: object) -> None:
    """
    Execute the seam matrix in a separate unsaved Fusion design.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this probe.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create a seam-test scratch design.")
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
                "name": f"fit_{lines}_h{separation:g}_twist{twist:g}",
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
    output = root_path / "artifacts/verification/discrete_spline_seam.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "DISCRETE_SPLINE_SEAM="
        + json.dumps(
            {"cases": len(rows), "solids": sum(row["result"] == "solid" for row in rows)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
