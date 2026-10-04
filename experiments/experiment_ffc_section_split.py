"""
Locate the extra mid-route plane intersection in the live FFC sweep scratch.

Read the saved source and existing unsaved tangent experiment only. This
does not construct or alter Fusion geometry and leaves both documents open.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from cable_bundler.fusion.cable_solid_parts.metadata import fusion_point
from experiments.experiment_live_ffc_correspondence import _live_plan
from experiments.experiment_live_ffc_one_face_sweep import _midpoint, _station_subset

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_section_split.json"


def _point_mm(point: adsk.core.Point3D) -> tuple[float, float, float]:
    """
    Convert a Fusion model point to millimeters.
    """
    return point.x * 10.0, point.y * 10.0, point.z * 10.0


def run(_context: object) -> None:
    """
    Compare split-section wire locations with all planned spine crossings.
    """
    application = adsk.core.Application.get()
    source = next(
        (
            document
            for document in application.documents
            if document.name.startswith("Wire creation tester v")
        ),
        None,
    )
    if source is None:
        raise RuntimeError("The saved FFC source document is not open.")
    source_design = adsk.fusion.Design.cast(source.products.itemByProductType("DesignProductType"))
    if source_design is None:
        raise RuntimeError("The saved source is not a Fusion design.")
    plan, _thickness_mm, _dimensions, _group_id = _live_plan(source_design)
    indices = (*range(len(plan.sections) - 4), len(plan.sections) - 1)
    trimmed = _station_subset(plan, indices)
    station_index = len(trimmed.sections) // 2
    station = trimmed.sections[station_index]
    center = _midpoint(station)
    signed_distances = []
    for index, other in enumerate(trimmed.sections):
        other_center = _midpoint(other)
        delta = (
            other_center.x - center.x,
            other_center.y - center.y,
            other_center.z - center.z,
        )
        signed_distances.append(
            {
                "station": index,
                "distance_mm": (
                    delta[0] * station.normal.x
                    + delta[1] * station.normal.y
                    + delta[2] * station.normal.z
                ),
            }
        )
    rows: list[dict[str, object]] = []
    for document in application.documents:
        if document.isSaved:
            continue
        design = adsk.fusion.Design.cast(document.products.itemByProductType("DesignProductType"))
        if design is None:
            continue
        for occurrence in design.rootComponent.occurrences:
            component = occurrence.component
            if not component.name.startswith("FFC contact-cap tangent · rebuilt_"):
                continue
            if component.bRepBodies.count != 1:
                continue
            body = component.bRepBodies.item(0)
            plane = adsk.core.Plane.create(
                fusion_point(center, adsk.core.Matrix3D.create()),
                adsk.core.Vector3D.create(station.normal.x, station.normal.y, station.normal.z),
            )
            section = adsk.fusion.TemporaryBRepManager.get().planeIntersection(body, plane)
            if section is None:
                continue
            wires = []
            for index in range(section.wires.count):
                wire = section.wires.item(index)
                bounds = [
                    wire.edges.item(edge_index).boundingBox
                    for edge_index in range(wire.edges.count)
                ]
                if not bounds:
                    raise RuntimeError("Fusion returned an empty section wire.")
                minimum = adsk.core.Point3D.create(
                    *(
                        min(_point_mm(box.minPoint)[axis] for box in bounds) / 10.0
                        for axis in range(3)
                    )
                )
                maximum = adsk.core.Point3D.create(
                    *(
                        max(_point_mm(box.maxPoint)[axis] for box in bounds) / 10.0
                        for axis in range(3)
                    )
                )
                wires.append(
                    {
                        "edges": wire.edges.count,
                        "bounds_mm": {
                            "min": _point_mm(minimum),
                            "max": _point_mm(maximum),
                        },
                    }
                )
            rows.append({"document": document.name, "component": component.name, "wires": wires})
    report = {
        "source": source.name,
        "source_modified": source.isModified,
        "section_station": station_index,
        "section_center_mm": (center.x, center.y, center.z),
        "spine_plane_distances": signed_distances,
        "tail_stations": [
            {
                "index": index,
                "center_mm": (
                    _midpoint(other).x,
                    _midpoint(other).y,
                    _midpoint(other).z,
                ),
                "normal": (other.normal.x, other.normal.y, other.normal.z),
            }
            for index, other in enumerate(plan.sections)
            if index >= len(plan.sections) - 9
        ],
        "intersections": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FFC_SECTION_SPLIT=" + json.dumps({"intersections": rows, "report": str(OUTPUT)}))


if __name__ == "__main__":
    run(None)
