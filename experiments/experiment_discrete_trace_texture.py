"""
Render UV-derived line colors on the open Discrete transport scratch.

Run through the local Fusion script runner after the Discrete transport
experiment. It modifies only that unsaved scratch and leaves it open.
"""

from __future__ import annotations

import json
import runpy
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_discrete_trace_transport import CASES
from experiments.experiment_ffc_texture_matrix import Case
from experiments.experiment_ffc_texture_rebuild import _side_face
from experiments.experiment_ffc_trace_transport import _end_samples

OUTPUT = Path(__file__).resolve().parents[1] / "artifacts/verification/discrete_trace_texture"
CASE_INDICES = (2, 5, 7)
UV_IMAGE = runpy.run_path(str(Path(__file__).with_name("experiment_ffc_texture_uv_exact.py")))


def run(_context: object) -> None:
    """
    Color three twisted Discrete profiles and capture both broad sides.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved Discrete transport scratch first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the texture test.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != len(CASES):
        raise RuntimeError("The active scratch does not contain the Discrete sweep matrix.")
    library = application.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    source = None if library is None else library.appearances.itemById("Prism-129")
    if source is None:
        raise RuntimeError("Fusion's opaque appearance is unavailable.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    viewport = application.activeViewport
    for index in CASE_INDICES:
        lines, separation_mm, twist_degrees = CASES[index]
        offset_y_cm = index * 12.0
        body = sweeps.item(index).bodies.item(0)
        side = _side_face(body)
        start, end = _end_samples(side, offset_y_cm, separation_mm, twist_degrees)
        samples = [{"x": across / 10.0, "u": u} for across, _height, u in start]
        case = Case(f"discrete_{lines}_twist{twist_degrees:g}", lines, 1.0, 0.8, 1.0)
        texture_path = OUTPUT / f"{case.name}.png"
        texture_path.write_bytes(UV_IMAGE["_image"](case, samples, 0.0))
        appearance = design.appearances.addByCopy(source, f"{case.name} UV lane test")
        if appearance is None:
            raise RuntimeError("Fusion could not copy the texture test appearance.")
        appearance.colorTexture = str(texture_path)
        slot = appearance.appearanceProperties.itemById("opaque_albedo")
        texture = None if slot is None else slot.connectedTexture
        if texture is None:
            raise RuntimeError("Fusion did not connect the Discrete lane image.")
        scale = texture.properties.itemById("texture_RealWorldScaleX")
        offset = texture.properties.itemById("texture_RealWorldOffsetX")
        if scale is None or offset is None:
            raise RuntimeError("Fusion did not expose texture mapping controls.")
        u_span = max(u for _across, _height, u in start) - min(u for _across, _height, u in start)
        scale.value = (
            UV_IMAGE["REFERENCE_SCALE_CM"]
            * u_span
            / UV_IMAGE["REFERENCE_U_SPAN"]
            * UV_IMAGE["CALIBRATED_SCALE_FACTOR"]
        )
        offset.value = 0.0
        side.appearance = appearance
        row: dict[str, object] = {
            "name": case.name,
            "lines": lines,
            "twist_degrees": twist_degrees,
            "start_nodes": len(start),
            "end_nodes": len(end),
            "u_span": u_span,
            "scale_cm": scale.value,
            "texture": str(texture_path),
            "appearance_name": side.appearance.name,
            "face_count": body.faces.count,
        }
        for side_name, direction in (("top", 1), ("bottom", -1)):
            camera = viewport.camera
            camera.target = adsk.core.Point3D.create(0.5, offset_y_cm + separation_mm / 20.0, 0.0)
            camera.eye = adsk.core.Point3D.create(
                0.5, offset_y_cm + separation_mm / 20.0, 100.0 * direction
            )
            camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
            camera.viewExtents = 3.0
            viewport.camera = camera
            viewport.refresh()
            capture = OUTPUT / f"{case.name}_{side_name}.png"
            row[f"{side_name}_image"] = str(capture)
            row[f"{side_name}_saved"] = viewport.saveAsImageFile(str(capture), 0, 0)
        rows.append(row)
    report = OUTPUT / "report.json"
    report.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("DISCRETE_TRACE_TEXTURE=" + json.dumps({"cases": len(rows), "report": str(report)}))


if __name__ == "__main__":
    run(None)
