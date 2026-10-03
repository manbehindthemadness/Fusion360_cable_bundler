"""
Read transverse display-mesh UVs from the open FFC texture matrix.

Run through the local Fusion MCP script runner while its unsaved test design
is active. This does not change Fusion geometry or appearances.
"""

from __future__ import annotations

import json
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_texture_matrix import CASES

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_texture_matrix"


def run(_context: object) -> None:
    """
    Record UV extents and physical cross-section positions per sweep.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC texture matrix first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    report: list[dict[str, object]] = []
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != len(CASES):
        raise RuntimeError("The active test design does not contain the expected sweep matrix.")
    for feature_index in range(sweeps.count):
        sweep = sweeps.item(feature_index)
        body = sweep.bodies.item(0)
        side = max(
            (body.faces.item(index) for index in range(body.faces.count)),
            key=lambda face: face.area,
        )
        meshes = side.meshManager.displayMeshes
        mesh = (
            meshes.item(0) if meshes.count else side.meshManager.createMeshCalculator().calculate()
        )
        nodes = mesh.nodeCoordinates
        coordinates = mesh.textureCoordinates
        if len(nodes) != len(coordinates):
            raise RuntimeError(f"Mesh UV count differs for {sweep.name}.")
        samples = [
            {
                "x": round(node.x, 7),
                "y": round(node.y, 7),
                "z": round(node.z, 7),
                "u": round(uv.x, 7),
                "v": round(uv.y, 7),
            }
            for node, uv in zip(nodes, coordinates)
            if abs(node.y) < 0.0001
        ]
        report.append(
            {
                "name": CASES[feature_index].name,
                "mesh_nodes": len(nodes),
                "start_samples": samples,
                "u_range": [min(uv.x for uv in coordinates), max(uv.x for uv in coordinates)],
                "v_range": [min(uv.y for uv in coordinates), max(uv.y for uv in coordinates)],
            }
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "uv_ranges.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FFC_MATRIX_UV=" + json.dumps({"sweeps": len(report), "report": str(path)}))


if __name__ == "__main__":
    run(None)
