"""
Measure transverse texture-coordinate transport through curved FFC sweeps.

Run through Fusion's local script runner with no active command. A new unsaved
test design remains open; the source document is not modified. This checks
the experimental one-face sweep, not the production FFC generation path.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_spline_seam import _case
from experiments.experiment_ffc_texture_rebuild import _side_face

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_trace_transport.json"
CASES = (
    (1, 5.0, 0.0),
    (1, 5.0, 180.0),
    (3, 10.0, 0.0),
    (3, 10.0, 90.0),
    (3, 10.0, 180.0),
    (5, 20.0, 0.0),
    (5, 20.0, 90.0),
    (5, 20.0, 180.0),
    (9, 60.0, 180.0),
)


def _end_samples(
    face: adsk.fusion.BRepFace,
    offset_y_cm: float,
    separation_mm: float,
    twist_degrees: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """
    Return section-local across, height, and mesh U at both path ends.

    The end frame reverses transverse direction with the path tangent and
    then applies Fusion's specified sweep twist. End points are transformed
    back to the starting section's logical frame before comparison.
    """
    meshes = face.meshManager.displayMeshes
    mesh = meshes.item(0) if meshes.count else face.meshManager.createMeshCalculator().calculate()
    if mesh is None or len(mesh.nodeCoordinates) != len(mesh.textureCoordinates):
        raise RuntimeError("No paired position/UV display mesh was available.")
    sine = math.sin(math.radians(twist_degrees))
    cosine = math.cos(math.radians(twist_degrees))
    start: list[tuple[float, float, float]] = []
    end: list[tuple[float, float, float]] = []
    for point, uv in zip(mesh.nodeCoordinates, mesh.textureCoordinates):
        if abs(point.x) > 1e-5:
            continue
        local_y = (point.y - offset_y_cm) * 10.0
        height = point.z * 10.0
        if abs(local_y) < separation_mm / 3.0:
            start.append((local_y, height, uv.x))
        elif abs(local_y - separation_mm) < separation_mm / 3.0:
            displaced = local_y - separation_mm
            across = -displaced * cosine + height * sine
            end_height = displaced * sine + height * cosine
            end.append((across, end_height, uv.x))
    return start, end


def _transport(
    start: list[tuple[float, float, float]],
    end: list[tuple[float, float, float]],
) -> dict[str, object]:
    """
    Match physical perimeter nodes and quantify transverse UV displacement.
    """
    if len(start) < 5 or len(end) < 5:
        raise RuntimeError("Too few end-section mesh nodes for correspondence.")
    paired = []
    for across, height, u in start:
        candidates = [row for row in end if math.hypot(row[0] - across, row[1] - height) < 0.05]
        if candidates:
            match = min(candidates, key=lambda row: abs(row[2] - u))
            distance = math.hypot(match[0] - across, match[1] - height)
            paired.append((distance, abs(match[2] - u)))
    if len(paired) != len(start) or len(start) != len(end):
        raise RuntimeError("Every start/end profile mesh node must have a counterpart.")
    return {
        "start_nodes": len(start),
        "end_nodes": len(end),
        "matched_nodes": len(paired),
        "max_local_position_error_mm": max(row[0] for row in paired),
        "max_transverse_u_error": max(row[1] for row in paired),
        "start_u_range": [min(row[2] for row in start), max(row[2] for row in start)],
        "end_u_range": [min(row[2] for row in end), max(row[2] for row in end)],
    }


def run(_context: object) -> None:
    """
    Build valid reversals and retain the unsaved design with a JSON audit.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the transport test design.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The test document is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    for index, (lines, separation_mm, twist_degrees) in enumerate(CASES):
        offset_y_cm = index * 12.0
        try:
            row = _case(design.rootComponent, lines, separation_mm, twist_degrees, offset_y_cm)
            if row["result"] != "solid":
                raise RuntimeError("The sweep did not produce a solid.")
            feature = design.rootComponent.features.sweepFeatures.item(
                design.rootComponent.features.sweepFeatures.count - 1
            )
            side = _side_face(feature.bodies.item(0))
            start, end = _end_samples(side, offset_y_cm, separation_mm, twist_degrees)
            row["transport"] = _transport(start, end)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            row = {
                "lines": lines,
                "separation_mm": separation_mm,
                "twist_degrees": twist_degrees,
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_TRACE_TRANSPORT="
        + json.dumps(
            {
                "cases": len(rows),
                "measured": sum("transport" in row for row in rows),
                "report": str(OUTPUT),
            }
        )
    )


def audit_active(_context: object) -> None:
    """
    Recalculate transport against the already-open scratch without editing it.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved transport test design first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != sum(row["result"] == "solid" for row in report["cases"]):
        raise RuntimeError("The active document does not match the transport report.")
    feature_index = 0
    for index, row in enumerate(report["cases"]):
        if row["result"] != "solid":
            continue
        _, separation_mm, twist_degrees = CASES[index]
        feature = sweeps.item(feature_index)
        side = _side_face(feature.bodies.item(0))
        start, end = _end_samples(side, index * 12.0, separation_mm, twist_degrees)
        row["transport"] = _transport(start, end)
        feature_index += 1
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "FFC_TRACE_TRANSPORT_AUDIT="
        + json.dumps(
            {
                "cases": len(report["cases"]),
                "measured": feature_index,
                "max_u_error": max(
                    row["transport"]["max_transverse_u_error"]
                    for row in report["cases"]
                    if "transport" in row
                ),
            }
        )
    )


if __name__ == "__main__":
    run(None)
