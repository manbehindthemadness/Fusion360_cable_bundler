"""
Inspect temporary mid-bend sections of the existing bank/twist sweep scratch.

Run with Fusion ``Python.Run`` after the two banked-profile sweep probes.
This creates no persistent geometry and does not alter the open design.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

import cable_bundler
from experiments.experiment_banked_profile_extremes import SHAPES, normal_extremes_mm
from experiments.experiment_ph_quintic import HermiteCase, ph_hermite_candidates

TARGETS = (
    ("tight_triangle_twist90", 5.0, "triangle_8x1", 90.0, 336.0),
    ("tight_triangle_twist180", 5.0, "triangle_8x1", 180.0, 344.0),
    ("wide_triangle_twist180", 10.0, "triangle_8x1", 180.0, 416.0),
    ("wide_rectangle_twist180", 10.0, "rectangle_8x0p5", 180.0, 392.0),
)


def _coordinates(point: adsk.core.Point3D) -> list[float]:
    """
    Return a model point in millimeters for report comparison.
    """
    return [point.x * 10.0, point.y * 10.0, point.z * 10.0]


def _bounds(box: adsk.core.BoundingBox3D) -> dict[str, list[float]]:
    """
    Serialize a temporary or persistent BRep bounding box in millimeters.
    """
    return {"min_mm": _coordinates(box.minPoint), "max_mm": _coordinates(box.maxPoint)}


def _target_body(
    root: adsk.fusion.Component,
    offset_y_cm: float,
) -> adsk.fusion.BRepBody:
    """
    Locate an isolated experiment body by its separated Y coordinate.
    """
    matches = [
        root.bRepBodies.item(index)
        for index in range(root.bRepBodies.count)
        if abs(root.bRepBodies.item(index).boundingBox.minPoint.y - offset_y_cm) < 1.0
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one body at Y={offset_y_cm:g} cm; found {len(matches)}.")
    return matches[0]


def _section_case(
    root: adsk.fusion.Component,
    name: str,
    separation_mm: float,
    shape_name: str,
    twist_degrees: float,
    offset_y_cm: float,
) -> dict[str, object]:
    """
    Intersect the body with a plane normal to the PH midpoint tangent.
    """
    curve = ph_hermite_candidates(
        HermiteCase(name, complex(0.0, separation_mm), 25.0 + 0j, -25.0 + 0j)
    )[0]
    midpoint = curve.point_at(0.5)
    derivative = curve.derivative_at(0.5)
    tangent_length = abs(derivative)
    if tangent_length <= 0.0:
        raise RuntimeError("The midpoint tangent is stationary.")
    plane = adsk.core.Plane.create(
        adsk.core.Point3D.create(midpoint.real / 10.0, offset_y_cm + midpoint.imag / 10.0, 0.0),
        adsk.core.Vector3D.create(
            derivative.real / tangent_length,
            derivative.imag / tangent_length,
            0.0,
        ),
    )
    body = _target_body(root, offset_y_cm)
    section = adsk.fusion.TemporaryBRepManager.get().planeIntersection(body, plane)
    if section is None:
        raise RuntimeError("Fusion returned no mid-bend plane intersection.")
    shape = next(item for item in SHAPES if item.name == shape_name)
    expected_bank = twist_degrees / 2.0
    left, right = normal_extremes_mm(shape, expected_bank)
    inward_x = -derivative.imag / tangent_length
    inward_y = derivative.real / tangent_length
    expected_inside = (
        midpoint.real + inward_x * left,
        offset_y_cm * 10.0 + midpoint.imag + inward_y * left,
    )
    expected_outside = (
        midpoint.real - inward_x * right,
        offset_y_cm * 10.0 + midpoint.imag - inward_y * right,
    )
    return {
        "name": name,
        "body_name": body.name,
        "body_is_solid": body.isSolid,
        "body_face_count": body.faces.count,
        "body_volume_cm3": body.volume,
        "body_bounds": _bounds(body.boundingBox),
        "section_edge_count": section.edges.count,
        "section_wire_count": section.wires.count,
        "section_bounds": _bounds(section.boundingBox),
        "midpoint_mm": [midpoint.real, offset_y_cm * 10.0 + midpoint.imag, 0.0],
        "midpoint_tangent_xy": [derivative.real / tangent_length, derivative.imag / tangent_length],
        "assumed_mid_bank_degrees": expected_bank,
        "expected_inward_reach_mm": left,
        "expected_outward_reach_mm": right,
        "assumed_inside_xy_mm": list(expected_inside),
        "assumed_outside_xy_mm": list(expected_outside),
        "section_vertices_mm": [
            _coordinates(section.vertices.item(index).geometry)
            for index in range(section.vertices.count)
        ],
    }


def run(_context: object) -> None:
    """
    Record temporary sections of the two anomalies and two wide controls.
    """
    application = adsk.core.Application.get()
    active_command = str(application.userInterface.activeCommand)
    if active_command != "SelectCommand":
        raise RuntimeError(f"Finish the active Fusion command before inspection: {active_command}.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None or design.rootComponent.bRepBodies.count != 31:
        raise RuntimeError("Open the completed 31-body bank/twist experiment scratch.")
    document = application.activeDocument
    modified_before = document.isModified
    results: list[dict[str, object]] = []
    for target in TARGETS:
        try:
            results.append(_section_case(design.rootComponent, *target))
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            results.append({"name": target[0], "error": str(error)})
    report = {
        "document": document.name,
        "modified_before": modified_before,
        "modified_after": document.isModified,
        "cases": results,
    }
    root_path = Path(cable_bundler.__file__).resolve().parents[1]
    output = root_path / "artifacts/verification/banked_triangle_section_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "BANKED_TRIANGLE_SECTION_AUDIT="
        + json.dumps(
            {"cases": len(results), "errors": sum("error" in row for row in results)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
