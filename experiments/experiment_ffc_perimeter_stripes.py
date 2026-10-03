"""
Test a mirrored, perimeter-wide texture on the open one-face FFC sweep.

The two broad sides of one closed sweep face traverse the profile in opposite
directions. This experiment gives each side 19 lanes in the same physical
order and places dark half-gaps at both rounded edges. It changes only the
active unsaved scratch and leaves the saved source design untouched.
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
IMAGE_HEIGHT = 16
SOURCE_APPEARANCE = "FFC procedural 19-trace stripe test"
TEST_APPEARANCE = "FFC mirrored perimeter stripe test"
TARGET_COMPONENT = "FFC one-face sweep with rail (7)"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    """
    Write one CRC-protected PNG chunk.
    """
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _pattern(
    trace_count: int,
    trace_width_mm: float,
    pitch_mm: float,
    right_edge_cells: float,
    left_edge_cells: float,
) -> bytes:
    """
    Encode each lane forward and backward around one closed perimeter.

    Dedicated edge intervals carry no trace color. The return side starts
    after the right edge and ends before the left edge, so its outermost
    bands can remain full-width without wrapping through the texture seam.
    """
    if trace_count < 1 or pitch_mm <= 0.0 or not 0.0 < trace_width_mm <= pitch_mm:
        raise ValueError("A positive trace count and feasible width/pitch are required.")
    if right_edge_cells < 0.0 or left_edge_cells < 0.0:
        raise ValueError("Edge intervals cannot be negative.")
    total_cells = 2 * trace_count + right_edge_cells + left_edge_cells
    width = round(total_cells * PIXELS_PER_PITCH)
    trace_fraction = trace_width_mm / pitch_mm
    row = bytearray()
    for pixel in range(width):
        perimeter_position = (pixel + 0.5) / PIXELS_PER_PITCH
        on_return = perimeter_position >= trace_count + right_edge_cells
        cell_position = (
            perimeter_position - trace_count - right_edge_cells if on_return else perimeter_position
        )
        in_side = (
            trace_count + right_edge_cells
            <= perimeter_position
            < 2 * trace_count + right_edge_cells
            if on_return
            else perimeter_position < trace_count
        )
        cell_index = int(cell_position)
        lane_index = trace_count - 1 - cell_index if on_return else cell_index
        distance = abs(cell_position - (cell_index + 0.5))
        if in_side and distance <= trace_fraction / 2.0:
            hue = (lane_index * 0.618033988749895) % 1.0
            red, green, blue = colorsys.hsv_to_rgb(hue, 0.82, 0.95)
            color = (round(red * 255), round(green * 255), round(blue * 255))
        else:
            color = (38, 42, 48)
        row.extend(color)
    scanlines = b"".join(b"\x00" + bytes(row) for _ in range(IMAGE_HEIGHT))
    header = struct.pack(">2I5B", width, IMAGE_HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _chunk(b"IEND", b"")
    )


def run(
    _context: object,
    scale_cm: float = 8.282368421052632,
    offset_cm: float = 0.118,
    right_edge_cells: float = 0.35,
    left_edge_cells: float = 0.65,
) -> None:
    """
    Apply a reversible test appearance to the known scratch sweep side face.

    Defaults are measured for this scratch only. A generated route needs its
    own pitch, global phase, and edge intervals fit before assignment.
    """
    if not 0.1 <= scale_cm <= 20.0 or not -20.0 <= offset_cm <= 20.0:
        raise ValueError("Test texture mapping is outside safe experiment bounds.")
    if not 0.0 <= right_edge_cells <= 2.0 or not 0.0 <= left_edge_cells <= 2.0:
        raise ValueError("Edge intervals must be at most two lane pitches.")
    application = adsk.core.Application.get()
    if str(application.userInterface.activeCommand) != "SelectCommand":
        raise RuntimeError("Finish the active Fusion command before this experiment.")
    scratch = application.activeDocument
    if scratch is None or scratch.name != "Untitled" or scratch.isSaved:
        raise RuntimeError("Activate the unsaved FFC sweep scratch first.")
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        raise RuntimeError("The active scratch is not a Fusion design.")
    matches = [
        occurrence
        for occurrence in design.rootComponent.occurrences
        if occurrence.component.name == TARGET_COMPONENT
    ]
    if len(matches) != 1 or matches[0].component.bRepBodies.count != 1:
        raise RuntimeError("The expected 19-lane scratch sweep is unavailable.")
    body = matches[0].component.bRepBodies.item(0)
    if not body.isSolid or body.faces.count != 3:
        raise RuntimeError("The scratch sweep is no longer a three-face solid.")
    side = max((body.faces.item(index) for index in range(body.faces.count)), key=lambda f: f.area)
    source = design.appearances.itemByName(SOURCE_APPEARANCE)
    if source is None:
        raise RuntimeError("The original procedural texture is unavailable.")
    previous_appearance = side.appearance.name if side.appearance else None
    edge_tag = f"r{right_edge_cells:.3f}_l{left_edge_cells:.3f}".replace(".", "")
    output = (
        Path(__file__).resolve().parents[1]
        / f"artifacts/verification/ffc_perimeter_stripes_{edge_tag}.png"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        _pattern(TRACE_COUNT, TRACE_WIDTH_MM, PITCH_MM, right_edge_cells, left_edge_cells)
    )
    test = design.appearances.itemByName(TEST_APPEARANCE)
    if test is None:
        test = design.appearances.addByCopy(source, TEST_APPEARANCE)
    if test is None:
        raise RuntimeError("Fusion could not create the mirrored test appearance.")
    test.colorTexture = str(output)
    slot = test.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("Fusion did not connect the mirrored stripe image.")
    scale = texture.properties.itemById("texture_RealWorldScaleX")
    offset = texture.properties.itemById("texture_RealWorldOffsetX")
    repeat = texture.properties.itemById("texture_URepeat")
    if scale is None or offset is None or repeat is None:
        raise RuntimeError("The expected mapping controls are unavailable.")
    scale.value = scale_cm
    offset.value = offset_cm
    repeat.value = True
    side.appearance = test
    application.activeViewport.refresh()
    report = {
        "scratch": scratch.name,
        "previous_appearance": previous_appearance,
        "test_appearance": side.appearance.name,
        "image": str(output),
        "image_pixels": [
            round((2 * TRACE_COUNT + right_edge_cells + left_edge_cells) * PIXELS_PER_PITCH),
            IMAGE_HEIGHT,
        ],
        "lanes_per_side": TRACE_COUNT,
        "side_order": ["forward", "reversed"],
        "right_edge_cells": right_edge_cells,
        "left_edge_cells": left_edge_cells,
        "scale_cm": scale.value,
        "offset_cm": offset.value,
        "repeat": repeat.value,
    }
    report_path = output.with_name("ffc_perimeter_stripes.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FFC_PERIMETER_STRIPES=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run(None)
