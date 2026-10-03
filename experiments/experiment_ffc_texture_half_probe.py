"""
Identify which half of a one-face FFC image each broad side actually samples.

This changes only the 19-trace appearance in the open unsaved matrix design.
The calibrated stripe experiment can be rerun afterward to restore it.
"""

from __future__ import annotations

import json
import struct
import zlib

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_perimeter_stripes import _chunk
from experiments.experiment_ffc_texture_matrix import CASES, OUTPUT
from experiments.experiment_ffc_texture_uv_exact import REFERENCE_SCALE_CM, REFERENCE_U_SPAN

CASE_NAME = "nineteen_reference"
IMAGE_WIDTH = 4096
IMAGE_HEIGHT = 16


def _image(probe_kind: str) -> bytes:
    """
    Encode a split-color probe or a monotone image-coordinate gradient.
    """
    threshold = (
        int(probe_kind.removeprefix("threshold_")) / 100.0
        if probe_kind.startswith("threshold_")
        else 0.5
    )
    row = b"".join(
        (bytes((235, 35, 35)) if pixel < IMAGE_WIDTH * threshold else bytes((35, 75, 235)))
        if probe_kind != "gradient"
        else bytes(
            (
                round(255 * pixel / (IMAGE_WIDTH - 1)),
                round(255 * (1 - pixel / (IMAGE_WIDTH - 1))),
                20,
            )
        )
        for pixel in range(IMAGE_WIDTH)
    )
    scanlines = b"".join(b"\x00" + row for _ in range(IMAGE_HEIGHT))
    header = struct.pack(">2I5B", IMAGE_WIDTH, IMAGE_HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _chunk(b"IEND", b"")
    )


def run(_context: object, probe_kind: str = "halves") -> None:
    """
    Assign the half-color probe and capture matched top and bottom views.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC matrix design first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    if probe_kind not in {"halves", "gradient", "threshold_25", "threshold_75"}:
        raise ValueError("The probe kind is not supported.")
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != len(CASES):
        raise RuntimeError("The active design is not the expected FFC matrix.")
    index = next(index for index, case in enumerate(CASES) if case.name == CASE_NAME)
    body = sweeps.item(index).bodies.item(0)
    side = max(
        (body.faces.item(face_index) for face_index in range(body.faces.count)),
        key=lambda face: face.area,
    )
    appearance = side.appearance
    if appearance is None:
        raise RuntimeError("The side face has no experiment appearance.")
    image_path = OUTPUT / f"{CASE_NAME}_{probe_kind}_probe.png"
    image_path.write_bytes(_image(probe_kind))
    appearance.colorTexture = str(image_path)
    slot = appearance.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("The diagnostic image is not connected to the appearance.")
    scale = texture.properties.itemById("texture_RealWorldScaleX")
    offset = texture.properties.itemById("texture_RealWorldOffsetX")
    if scale is None or offset is None:
        raise RuntimeError("Fusion did not expose the diagnostic mapping controls.")
    uv_rows = json.loads((OUTPUT / "uv_ranges.json").read_text(encoding="utf-8"))
    u_span = uv_rows[index]["u_range"][1] - uv_rows[index]["u_range"][0]
    scale.value = REFERENCE_SCALE_CM * u_span / REFERENCE_U_SPAN
    offset.value = 0.0
    matrix = json.loads((OUTPUT / "matrix.json").read_text(encoding="utf-8"))
    case_row = matrix["cases"][index]
    viewport = application.activeViewport
    for side_name, direction in (("top", 1), ("bottom", -1)):
        camera = viewport.camera
        center_x = float(case_row["center_x_cm"])
        camera.target = adsk.core.Point3D.create(center_x, 0.75, 0.0)
        camera.eye = adsk.core.Point3D.create(center_x, 0.75, 100.0 * direction)
        camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
        camera.viewExtents = float(case_row["view_extent_cm"])
        viewport.camera = camera
        viewport.refresh()
        capture = OUTPUT / f"{CASE_NAME}_{side_name}_{probe_kind}_probe.png"
        if not viewport.saveAsImageFile(str(capture), 0, 0):
            raise RuntimeError(f"Could not save {side_name} half-probe capture.")
    print("FFC_HALF_PROBE=" + str(image_path))


if __name__ == "__main__":
    run(None)
