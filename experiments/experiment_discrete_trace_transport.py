"""
Test one-face Discrete-ribbon lane coordinates through planar reversals.

Run through the local Fusion script runner with no command active. This
creates an unsaved scratch and leaves it open; existing designs are read only.
Path feasibility is intentionally separate from the texture-transport result.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_discrete_spline_seam import _case
from experiments.experiment_ffc_texture_rebuild import _side_face
from experiments.experiment_ffc_trace_transport import _end_samples, _transport

OUTPUT = (
    Path(__file__).resolve().parents[1] / "artifacts/verification/discrete_trace_transport.json"
)
CASES = (
    (3, 10.0, 0.0),
    (3, 10.0, 90.0),
    (3, 10.0, 180.0),
    (5, 10.0, 0.0),
    (5, 10.0, 90.0),
    (5, 10.0, 180.0),
    (7, 20.0, 0.0),
    (7, 20.0, 180.0),
)


def _lane_centers(
    start: list[tuple[float, float, float]],
    end: list[tuple[float, float, float]],
    lines: int,
) -> dict[str, object]:
    """
    Identify each lobe on both broad sides and compare its endpoint U.

    The fitted Discrete outline has 1 mm pitch. Its upper and lower lobe
    crests are near +0.5 and -0.5 mm in section-local height, respectively.
    """
    rows: list[dict[str, object]] = []
    for lane in range(lines):
        across = lane - (lines - 1) / 2.0
        for side, height in (("top", 0.5), ("bottom", -0.5)):
            first = min(start, key=lambda row: (row[0] - across) ** 2 + (row[1] - height) ** 2)
            last = min(end, key=lambda row: (row[0] - across) ** 2 + (row[1] - height) ** 2)
            if abs(first[0] - across) > 0.1 or abs(last[0] - across) > 0.1:
                raise RuntimeError(f"No mesh crest found for Discrete lane {lane + 1} {side}.")
            rows.append(
                {
                    "lane": lane + 1,
                    "side": side,
                    "start_u": first[2],
                    "end_u": last[2],
                    "u_error": abs(first[2] - last[2]),
                }
            )
    for side in ("top", "bottom"):
        coordinates = [row["start_u"] for row in rows if row["side"] == side]
        if len(set(coordinates)) != lines:
            raise RuntimeError(f"Discrete {side} lane crests do not have distinct UVs.")
    return {"lanes": rows, "max_lane_u_error": max(row["u_error"] for row in rows)}


def run(_context: object) -> None:
    """
    Build valid Discrete reversals and audit both side/lane coordinate maps.
    """
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    source = application.activeDocument
    source_modified_before = source.isModified
    scratch = application.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    if scratch is None:
        raise RuntimeError("Fusion could not create the Discrete transport scratch.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The scratch is not a Fusion design.")
    design.designType = adsk.fusion.DesignTypes.DirectDesignType
    rows: list[dict[str, object]] = []
    for index, (lines, separation_mm, twist_degrees) in enumerate(CASES):
        offset_y_cm = index * 12.0
        try:
            row = _case(design.rootComponent, lines, separation_mm, twist_degrees, offset_y_cm)
            if row["result"] != "solid" or row["midpoint_section"]["wire_count"] != 1:
                raise RuntimeError("Discrete sweep did not make one section-valid solid.")
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
    _audit_rows(design, rows)
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
        "DISCRETE_TRACE_TRANSPORT="
        + json.dumps(
            {
                "cases": len(rows),
                "measured": sum("lane_centers" in row for row in rows),
                "report": str(OUTPUT),
            }
        )
    )


def _audit_rows(design: adsk.fusion.Design, rows: list[dict[str, object]]) -> None:
    """
    Read all side meshes after viewport tessellation has settled.
    """
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != sum(row["result"] == "solid" for row in rows):
        raise RuntimeError("The Discrete sweep count does not match the case report.")
    feature_index = 0
    for index, row in enumerate(rows):
        if row["result"] != "solid":
            continue
        lines, separation_mm, twist_degrees = CASES[index]
        side = _side_face(sweeps.item(feature_index).bodies.item(0))
        start, end = _end_samples(side, index * 12.0, separation_mm, twist_degrees)
        row["transport"] = _transport(start, end)
        row["lane_centers"] = _lane_centers(start, end, lines)
        feature_index += 1


def audit_active(_context: object) -> None:
    """
    Recheck the open unsaved Discrete scratch without changing its geometry.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved Discrete transport scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    report = json.loads(OUTPUT.read_text(encoding="utf-8"))
    for row in report["cases"]:
        if row["result"] == "failed" and row.get("error", "").startswith("No mesh crest"):
            row["result"] = "solid"
            del row["error"]
    _audit_rows(design, report["cases"])
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "DISCRETE_TRACE_TRANSPORT_AUDIT="
        + json.dumps(
            {
                "cases": len(report["cases"]),
                "measured": sum("lane_centers" in row for row in report["cases"]),
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
