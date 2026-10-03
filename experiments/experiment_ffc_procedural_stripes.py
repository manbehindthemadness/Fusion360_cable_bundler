"""
Create a measured, procedural stripe appearance on the open FFC sweep scratch.

Run through the local Fusion MCP script runner with no command active. This
experiment changes only the active unsaved scratch document and leaves it open.
Fusion's ``Appearance.colorTexture`` setter is a preview API; this is not a
production appearance implementation.
"""

from __future__ import annotations

import colorsys
import json
import struct
import zlib
from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

TRACE_COUNT = 19
PITCH_MM = 2.506666666666669
TRACE_WIDTH_MM = 1.5146940685852002
PIXELS_PER_PITCH = 64
TEXTURE_HEIGHT = 16
APPEARANCE_NAME = "FFC procedural 19-trace stripe test"
TARGET_COMPONENT = "FFC one-face sweep with rail (7)"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    """
    Encode one PNG chunk with its size and CRC.
    """
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _stripe_png() -> tuple[bytes, int]:
    """
    Build distinct flat trace bands with dark inter-trace gaps, without Pillow.
    """
    width = TRACE_COUNT * PIXELS_PER_PITCH
    trace_fraction = TRACE_WIDTH_MM / PITCH_MM
    row = bytearray()
    for pixel in range(width):
        position = (pixel + 0.5) / PIXELS_PER_PITCH
        trace_index = int(position)
        distance_from_center = abs(position - (trace_index + 0.5))
        if distance_from_center <= trace_fraction / 2.0:
            hue = (trace_index * 0.618033988749895) % 1.0
            red, green, blue = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
            rgb = (round(red * 255), round(green * 255), round(blue * 255))
        else:
            rgb = (38, 42, 48)
        row.extend(rgb)
    scanlines = b"".join(b"\x00" + bytes(row) for _ in range(TEXTURE_HEIGHT))
    header = struct.pack(">2I5B", width, TEXTURE_HEIGHT, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _png_chunk(b"IEND", b"")
    )
    return png, width


def _target_body(design: adsk.fusion.Design) -> adsk.fusion.BRepBody:
    """
    Select only the latest known 19-trace scratch sweep.
    """
    matches = [
        body
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name == TARGET_COMPONENT
        for body in occurrence.component.bRepBodies
    ]
    if len(matches) != 1 or not matches[0].isSolid or matches[0].faces.count != 3:
        raise RuntimeError("The expected one-face 19-trace scratch body is unavailable.")
    return matches[0]


def run(_context: object) -> None:
    """
    Add one texture appearance and apply it to the sweep's lengthwise face.
    """
    application = adsk.core.Application.get()
    document = application.activeDocument
    if document is None or document.name != "Untitled" or document.isSaved:
        raise RuntimeError("Activate the unsaved FFC sweep scratch document first.")
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before applying stripes.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active scratch is not a Fusion design.")
    body = _target_body(design)
    face = max((body.faces.item(index) for index in range(body.faces.count)), key=lambda f: f.area)
    if design.appearances.itemByName(APPEARANCE_NAME) is not None:
        raise RuntimeError("The procedural stripe appearance already exists in this scratch.")

    output = Path(__file__).resolve().parents[1] / "artifacts/verification/ffc_trace_stripes.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    png, pixel_width = _stripe_png()
    output.write_bytes(png)

    library = application.materialLibraries.itemById("BA5EE55E-9982-449B-9D66-9F036540E140")
    if library is None:
        raise RuntimeError("Fusion's built-in appearance library is unavailable.")
    generic = library.appearances.itemById("Prism-129")
    if generic is None:
        raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
    appearance = design.appearances.addByCopy(generic, APPEARANCE_NAME)
    if appearance is None:
        raise RuntimeError("Fusion could not copy the opaque test appearance.")
    appearance.colorTexture = str(output)
    if not appearance.colorTexture:
        raise RuntimeError("Fusion did not connect the procedural stripe image.")
    texture_slot = appearance.appearanceProperties.itemById("opaque_albedo")
    if texture_slot is None or texture_slot.connectedTexture is None:
        raise RuntimeError("The new appearance has no connected albedo texture.")
    texture = texture_slot.connectedTexture
    scale_x = texture.properties.itemById("texture_RealWorldScaleX")
    scale_y = texture.properties.itemById("texture_RealWorldScaleY")
    if scale_x is not None:
        scale_x.value = TRACE_COUNT * PITCH_MM / 10.0
    if scale_y is not None:
        scale_y.value = 100.0
    face.appearance = appearance
    application.activeViewport.refresh()
    print(
        "FFC_PROCEDURAL_STRIPES="
        + json.dumps(
            {
                "document": document.name,
                "appearance": appearance.name,
                "texture": str(output),
                "image_pixels": [pixel_width, TEXTURE_HEIGHT],
                "trace_count": TRACE_COUNT,
                "ribbon_width_mm": TRACE_COUNT * PITCH_MM,
                "trace_width_mm": TRACE_WIDTH_MM,
                "spacing_mm": PITCH_MM - TRACE_WIDTH_MM,
                "scale_x": None if scale_x is None else scale_x.value,
                "scale_y": None if scale_y is None else scale_y.value,
                "face_area_cm2": face.area,
                "assigned_appearance": face.appearance.name if face.appearance else None,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    run(None)
