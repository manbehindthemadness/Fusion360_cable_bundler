"""
Test UV-span-normalized stripe mapping on the unsaved FFC sweep matrix.

This intentionally changes only the 11 experiment appearances in the active
unsaved matrix design and leaves that design open for visual inspection.
"""

from __future__ import annotations

import json

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_texture_matrix import CASES, OUTPUT, REFERENCE_OFFSET_CM

REFERENCE_SCALE_CM = 8.282368421052632
REFERENCE_U_SPAN = 20.779499053955078


def run(_context: object) -> None:
    """
    Map each image's full perimeter repeat to its measured display-mesh U span.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC matrix design first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != len(CASES):
        raise RuntimeError("The active design is not the expected sweep matrix.")
    uv_rows = json.loads((OUTPUT / "uv_ranges.json").read_text(encoding="utf-8"))
    if [row["name"] for row in uv_rows] != [case.name for case in CASES]:
        raise RuntimeError("UV report and sweep matrix case order differ.")
    matrix = json.loads((OUTPUT / "matrix.json").read_text(encoding="utf-8"))
    viewport = application.activeViewport
    rows: list[dict[str, object]] = []
    for index, case in enumerate(CASES):
        body = sweeps.item(index).bodies.item(0)
        side = max(
            (body.faces.item(face_index) for face_index in range(body.faces.count)),
            key=lambda face: face.area,
        )
        appearance = side.appearance
        if appearance is None:
            raise RuntimeError(f"No side appearance for {case.name}.")
        slot = appearance.appearanceProperties.itemById("opaque_albedo")
        texture = None if slot is None else slot.connectedTexture
        if texture is None:
            raise RuntimeError(f"No side texture for {case.name}.")
        scale = texture.properties.itemById("texture_RealWorldScaleX")
        offset = texture.properties.itemById("texture_RealWorldOffsetX")
        if scale is None or offset is None:
            raise RuntimeError(f"Mapping controls unavailable for {case.name}.")
        u_span = uv_rows[index]["u_range"][1] - uv_rows[index]["u_range"][0]
        ratio = u_span / REFERENCE_U_SPAN
        old_scale = scale.value
        old_offset = offset.value
        scale.value = REFERENCE_SCALE_CM * ratio
        offset.value = REFERENCE_OFFSET_CM * ratio
        row: dict[str, object] = {
            "name": case.name,
            "u_span": u_span,
            "old_scale_cm": old_scale,
            "scale_cm": scale.value,
            "old_offset_cm": old_offset,
            "offset_cm": offset.value,
        }
        case_row = matrix["cases"][index]
        center_x = float(case_row["center_x_cm"])
        extent_cm = float(case_row["view_extent_cm"])
        for side_name, direction in (("top", 1), ("bottom", -1)):
            camera = viewport.camera
            camera.target = adsk.core.Point3D.create(center_x, 0.75, 0.0)
            camera.eye = adsk.core.Point3D.create(center_x, 0.75, 100.0 * direction)
            camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
            camera.viewExtents = extent_cm
            viewport.camera = camera
            viewport.refresh()
            path = OUTPUT / f"{case.name}_{side_name}_uv_fit.png"
            row[f"{side_name}_image"] = str(path)
            row[f"{side_name}_saved"] = viewport.saveAsImageFile(str(path), 0, 0)
        rows.append(row)
    path = OUTPUT / "uv_fit.json"
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("FFC_UV_FIT=" + json.dumps({"cases": len(rows), "report": str(path)}))


if __name__ == "__main__":
    run(None)
