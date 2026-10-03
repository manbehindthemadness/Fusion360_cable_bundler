"""
Map FFC lane colors from the swept section's measured mesh UV positions.

Run through local Fusion MCP with the unsaved 11-case matrix active. Only test
appearances in that unsaved design are changed; no saved design is edited.
"""

from __future__ import annotations

import bisect
import colorsys
import json
import struct
import zlib

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from experiments.experiment_ffc_perimeter_stripes import _chunk
from experiments.experiment_ffc_texture_matrix import CASES, OUTPUT, Case

REFERENCE_SCALE_CM = 8.282368421052632
REFERENCE_U_SPAN = 20.779499053955078
CALIBRATED_SCALE_FACTOR = 0.9883
IMAGE_WIDTH = 4096
IMAGE_HEIGHT = 16
BASE_COLOR = (38, 42, 48)


def _image(
    case: Case,
    samples: list[dict[str, float]],
    center_x_cm: float,
) -> bytes:
    """
    Convert actual cross-section U positions into physical lane colors.

    Interpolation is within the rendered mesh's starting section, not an
    assumption that millimeters and Fusion UV are linearly related.
    """
    ordered = sorted(samples, key=lambda sample: sample["u"])
    positions = [sample["u"] for sample in ordered]
    if len(ordered) < 2 or positions[-1] <= positions[0]:
        raise ValueError("No usable transverse UV samples were reported.")
    if any(right <= left for left, right in zip(positions, positions[1:])):
        raise ValueError("The section UV samples are not uniquely ordered.")
    u_min = positions[0]
    u_span = positions[-1] - u_min
    row = bytearray()
    for pixel in range(IMAGE_WIDTH):
        u = u_min + (pixel + 0.5) * u_span / IMAGE_WIDTH
        index = min(bisect.bisect_right(positions, u), len(ordered) - 1)
        left = ordered[index - 1]
        right = ordered[index]
        fraction = (u - left["u"]) / (right["u"] - left["u"])
        x_mm = (left["x"] + fraction * (right["x"] - left["x"]) - center_x_cm) * 10.0
        lane = round(x_mm / case.pitch_mm + (case.count - 1) / 2.0)
        if 0 <= lane < case.count:
            center_mm = (lane - (case.count - 1) / 2.0) * case.pitch_mm
            if abs(x_mm - center_mm) <= case.trace_width_mm / 2.0:
                hue = (lane * 0.618033988749895) % 1.0
                red, green, blue = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
                row.extend((round(red * 255), round(green * 255), round(blue * 255)))
                continue
        row.extend(BASE_COLOR)
    scanlines = b"".join(b"\x00" + bytes(row) for _ in range(IMAGE_HEIGHT))
    header = struct.pack(">2I5B", IMAGE_WIDTH, IMAGE_HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _chunk(b"IEND", b"")
    )


def run(
    _context: object,
    scale_factor: float = CALIBRATED_SCALE_FACTOR,
    capture_suffix: str | None = None,
) -> None:
    """
    Render and report UV-derived lane textures for both sides of every case.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.isSaved or document.name != "Untitled":
        raise RuntimeError("Activate the unsaved FFC matrix design first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before the experiment.")
    if not 0.95 <= scale_factor <= 1.05:
        raise ValueError("The material-scale probe is outside test bounds.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active document is not a Fusion design.")
    sweeps = design.rootComponent.features.sweepFeatures
    if sweeps.count != len(CASES):
        raise RuntimeError("The active design is not the expected sweep matrix.")
    uv_rows = json.loads((OUTPUT / "uv_ranges.json").read_text(encoding="utf-8"))
    matrix = json.loads((OUTPUT / "matrix.json").read_text(encoding="utf-8"))
    if [row["name"] for row in uv_rows] != [case.name for case in CASES]:
        raise RuntimeError("UV report and sweep matrix order differ.")
    if capture_suffix is None:
        capture_suffix = "_uv_scale_final"
    if not capture_suffix.startswith("_uv_"):
        raise ValueError("The capture suffix must identify a UV experiment.")
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
            raise RuntimeError(f"No test appearance for {case.name}.")
        case_row = matrix["cases"][index]
        center_x_cm = float(case_row["center_x_cm"])
        image_path = OUTPUT / f"{case.name}{capture_suffix}.png"
        image_path.write_bytes(_image(case, uv_rows[index]["start_samples"], center_x_cm))
        appearance.colorTexture = str(image_path)
        slot = appearance.appearanceProperties.itemById("opaque_albedo")
        texture = None if slot is None else slot.connectedTexture
        if texture is None:
            raise RuntimeError(f"No test texture for {case.name}.")
        scale = texture.properties.itemById("texture_RealWorldScaleX")
        offset = texture.properties.itemById("texture_RealWorldOffsetX")
        if scale is None or offset is None:
            raise RuntimeError(f"Mapping controls unavailable for {case.name}.")
        u_span = uv_rows[index]["u_range"][1] - uv_rows[index]["u_range"][0]
        scale.value = REFERENCE_SCALE_CM * u_span / REFERENCE_U_SPAN * scale_factor
        offset.value = 0.0
        row: dict[str, object] = {
            "name": case.name,
            "scale_cm": scale.value,
            "offset_cm": offset.value,
            "texture": str(image_path),
        }
        extent_cm = float(case_row["view_extent_cm"])
        for side_name, direction in (("top", 1), ("bottom", -1)):
            camera = viewport.camera
            camera.target = adsk.core.Point3D.create(center_x_cm, 0.75, 0.0)
            camera.eye = adsk.core.Point3D.create(center_x_cm, 0.75, 100.0 * direction)
            camera.upVector = adsk.core.Vector3D.create(0.0, 1.0, 0.0)
            camera.viewExtents = extent_cm
            viewport.camera = camera
            viewport.refresh()
            capture = OUTPUT / f"{case.name}_{side_name}{capture_suffix}.png"
            row[f"{side_name}_image"] = str(capture)
            row[f"{side_name}_saved"] = viewport.saveAsImageFile(str(capture), 0, 0)
        rows.append(row)
    path = OUTPUT / f"{capture_suffix.removeprefix('_')}.json"
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("FFC_UV_EXACT=" + json.dumps({"cases": len(rows), "report": str(path)}))


if __name__ == "__main__":
    run(None)
