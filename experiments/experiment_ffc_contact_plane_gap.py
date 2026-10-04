"""
Measure the live one-face FFC sweep against exact Interface contact planes.

Run with the existing unsaved FFC sweep/contact scratch active and no command
open. This experiment reads geometry only and leaves every document open.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_live_ffc_correspondence import _live_plan
from experiments.experiment_live_ffc_one_face_sweep import _midpoint

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_contact_plane_gap.json"
SWEEP_COMPONENT = "FFC one-face sweep with rail (7)"
BANK_COMPONENTS = (
    "FFC START Interface contacts · pins 1–19",
    "FFC END Interface contacts · pins 1–19",
)
DISPLAY_COMPONENTS = (
    "FFC START contact display · 4 mm outward",
    "FFC END contact display · 4 mm outward",
)


def _component(design: adsk.fusion.Design, name: str) -> adsk.fusion.Component:
    """
    Resolve one uniquely named scratch component without changing visibility.
    """
    matches = [
        occurrence.component
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {name} component; found {len(matches)}.")
    return matches[0]


def _coordinates(point: adsk.core.Point3D) -> tuple[float, float, float]:
    """
    Convert a Fusion point from centimeters to millimeters.
    """
    return point.x * 10.0, point.y * 10.0, point.z * 10.0


def _bank(component: adsk.fusion.Component) -> dict[str, object]:
    """
    Measure the contact-plane origin, normal, and centroid spread.
    """
    bodies = component.bRepBodies
    if bodies.count != 19:
        raise RuntimeError(f"{component.name} does not contain 19 contact faces.")
    faces = [bodies.item(index).faces.item(0) for index in range(bodies.count)]
    plane = adsk.core.Plane.cast(faces[0].geometry)
    if plane is None:
        raise RuntimeError(f"{component.name} contacts are not planar.")
    centers = [_coordinates(face.centroid) for face in faces]
    normal = (plane.normal.x, plane.normal.y, plane.normal.z)
    center = tuple(sum(point[axis] for point in centers) / len(centers) for axis in range(3))
    spread = [
        sum((point[axis] - center[axis]) * normal[axis] for axis in range(3)) for point in centers
    ]
    return {
        "component": component.name,
        "center_mm": center,
        "normal": normal,
        "plane_spread_mm": max(abs(value) for value in spread),
        "first_center_mm": centers[0],
        "last_center_mm": centers[-1],
    }


def _cap_gap(cap: adsk.fusion.BRepFace, bank: dict[str, object]) -> dict[str, object]:
    """
    Decompose the cap-to-contact offset into normal and in-plane parts.
    """
    center = _coordinates(cap.centroid)
    target = bank["center_mm"]
    normal = bank["normal"]
    delta = tuple(center[axis] - target[axis] for axis in range(3))
    signed = sum(delta[axis] * normal[axis] for axis in range(3))
    distance = math.sqrt(sum(value * value for value in delta))
    in_plane = math.sqrt(max(0.0, distance * distance - signed * signed))
    cap_plane = adsk.core.Plane.cast(cap.geometry)
    alignment = (
        None
        if cap_plane is None
        else sum(
            (cap_plane.normal.x, cap_plane.normal.y, cap_plane.normal.z)[axis] * normal[axis]
            for axis in range(3)
        )
    )
    return {
        "cap_centroid_mm": center,
        "contact_center_mm": target,
        "signed_normal_gap_mm": signed,
        "absolute_normal_gap_mm": abs(signed),
        "in_plane_center_offset_mm": in_plane,
        "total_center_offset_mm": distance,
        "cap_contact_normal_dot": alignment,
        "cap_normal": (
            None
            if cap_plane is None
            else (cap_plane.normal.x, cap_plane.normal.y, cap_plane.normal.z)
        ),
        "cap_bounds_mm": {
            "min": _coordinates(cap.boundingBox.minPoint),
            "max": _coordinates(cap.boundingBox.maxPoint),
        },
    }


def _plan_ends(application: adsk.core.Application) -> list[dict[str, object]]:
    """
    Compare the saved route's actual endpoint stations with both contacts.
    """
    source = next(
        (doc for doc in application.documents if doc.name.startswith("Wire creation tester v")),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source design is not open.")
    design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if design is None:
        raise RuntimeError("The FFC source is not a Fusion design.")
    plan, _thickness, _dimensions, _group_id = _live_plan(design)
    rows: list[dict[str, object]] = []
    for end, station in enumerate((plan.sections[0], plan.sections[-1])):
        center = _midpoint(station)
        rows.append(
            {
                "end": end,
                "center_mm": (center.x, center.y, center.z),
                "normal": (station.normal.x, station.normal.y, station.normal.z),
                "width": (station.width.x, station.width.y, station.width.z),
            }
        )
    return rows


def _path_endpoints(component: adsk.fusion.Component) -> dict[str, object]:
    """
    Record the fitted spine's final control stations, without editing it.
    """
    matches = [
        component.sketches.item(index)
        for index in range(component.sketches.count)
        if component.sketches.item(index).name == "FFC sweep centerline"
    ]
    if len(matches) != 1:
        raise RuntimeError("The expected fitted centerline sketch is unavailable.")
    splines = matches[0].sketchCurves.sketchFittedSplines
    if splines.count != 1:
        raise RuntimeError("The centerline sketch does not contain one fitted spline.")
    fit_points = splines.item(0).fitPoints
    if fit_points.count < 2:
        raise RuntimeError("The fitted centerline has fewer than two points.")
    return {
        "fit_points": fit_points.count,
        "first_mm": _coordinates(fit_points.item(0).worldGeometry),
        "second_mm": _coordinates(fit_points.item(1).worldGeometry),
        "penultimate_mm": _coordinates(fit_points.item(fit_points.count - 2).worldGeometry),
        "last_mm": _coordinates(fit_points.item(fit_points.count - 1).worldGeometry),
    }


def run(_context: object) -> None:
    """
    Audit both exact contact banks and their intentionally shifted displays.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC sweep/contact scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before measuring.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active scratch is not a Fusion design.")
    component = _component(design, SWEEP_COMPONENT)
    sweeps = component.features.sweepFeatures
    if sweeps.count != 1 or sweeps.item(0).bodies.count != 1:
        raise RuntimeError("The expected 19-trace one-face sweep is unavailable.")
    sweep = sweeps.item(0)
    if sweep.startFaces.count != 1 or sweep.endFaces.count != 1:
        raise RuntimeError("The FFC sweep does not expose one cap at each end.")
    rows: list[dict[str, object]] = []
    for end, (exact_name, display_name, cap) in enumerate(
        zip(BANK_COMPONENTS, DISPLAY_COMPONENTS, (sweep.startFaces.item(0), sweep.endFaces.item(0)))
    ):
        exact = _bank(_component(design, exact_name))
        display = _bank(_component(design, display_name))
        rows.append(
            {
                "end": end,
                "exact_contacts": exact,
                "display_contacts": display,
                "exact_cap_gap": _cap_gap(cap, exact),
                "display_cap_gap": _cap_gap(cap, display),
            }
        )
    report = {
        "scratch": document.name,
        "sweep_component": component.name,
        "ends": rows,
        "planned_ends": _plan_ends(application),
        "spine": _path_endpoints(component),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_CONTACT_PLANE_GAP="
        + json.dumps(
            {
                "exact_normal_gaps_mm": [
                    row["exact_cap_gap"]["absolute_normal_gap_mm"] for row in rows
                ],
                "display_normal_gaps_mm": [
                    row["display_cap_gap"]["absolute_normal_gap_mm"] for row in rows
                ],
                "report": str(OUTPUT),
            }
        )
    )


if __name__ == "__main__":
    run(None)
