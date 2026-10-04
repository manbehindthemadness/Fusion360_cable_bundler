"""
Map persistent ribbon-line colors onto the one side face of an FFC sweep.
"""

from __future__ import annotations

import bisect
import hashlib
import math
import struct
import zlib
from pathlib import Path
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import CableColor
from ...domain.ffc import FfcDimensions
from ..solid_ribbon import SolidRibbonSection
from .metadata import fusion_point
from .one_face_ffc import _midpoint

IMAGE_WIDTH = 4096
IMAGE_HEIGHT = 16
UV_SCALE_CM_PER_UNIT = 8.282368421052632 / 20.779499053955078 * 0.9883
TEXTURE_CACHE = Path(__file__).resolve().parents[3] / "artifacts/generated_textures"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    """
    Encode a PNG chunk with its CRC.
    """
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _png_row(row: bytes) -> bytes:
    """
    Repeat one perimeter-color row into a compact RGB image.
    """
    width = len(row) // 3
    if width < 2 or len(row) != width * 3:
        raise ValueError("The ribbon texture row must contain at least two RGB pixels.")
    scanlines = b"".join(b"\x00" + row for _ in range(IMAGE_HEIGHT))
    header = struct.pack(">2I5B", width, IMAGE_HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _png_chunk(b"IEND", b"")
    )


def _texture_row(
    samples: tuple[tuple[float, float], ...],
    dimensions: FfcDimensions,
    colors: tuple[CableColor, ...],
    base: CableColor,
) -> bytes:
    """
    Interpolate measured perimeter U to physical width on both broad sides.
    """
    if len(samples) < 2 or not colors:
        raise ValueError("FFC texture needs UV samples and at least one trace color.")
    ordered = tuple(sorted(samples))
    u_values = tuple(sample[0] for sample in ordered)
    if any(right <= left for left, right in zip(u_values, u_values[1:])):
        raise ValueError("FFC start-section UV values must be strictly ordered.")
    u_min, u_max = u_values[0], u_values[-1]
    if min(abs(u_min), abs(u_max)) > 1e-5 or u_max - u_min <= 1e-6:
        raise ValueError("FFC texture requires one zero-based transverse UV endpoint.")
    row = bytearray()
    for pixel in range(IMAGE_WIDTH):
        u = u_min + (pixel + 0.5) * (u_max - u_min) / IMAGE_WIDTH
        right_index = min(bisect.bisect_right(u_values, u), len(ordered) - 1)
        left_u, left_across = ordered[right_index - 1]
        right_u, right_across = ordered[right_index]
        fraction = (u - left_u) / (right_u - left_u)
        across = left_across + fraction * (right_across - left_across)
        lane = round(across / dimensions.pitch_mm + (len(colors) - 1) / 2.0)
        selected = base
        if 0 <= lane < len(colors):
            center = (lane - (len(colors) - 1) / 2.0) * dimensions.pitch_mm
            if abs(across - center) <= dimensions.trace_width_mm / 2.0:
                selected = colors[lane]
        row.extend((selected.red, selected.green, selected.blue))
    return bytes(row)


def _section_uv_samples(
    side: adsk.fusion.BRepFace,
    station: SolidRibbonSection,
    dimensions: FfcDimensions,
    transform: adsk.core.Matrix3D,
) -> tuple[tuple[float, float], ...]:
    """
    Read transverse UVs and physical width from one actual swept end edge.
    """
    origin_world = _midpoint(station)
    origin = fusion_point(origin_world, transform)
    width_tip = fusion_point(origin_world.translated(station.width, 10.0), transform)
    normal_tip = fusion_point(origin_world.translated(station.normal, 10.0), transform)
    width = adsk.core.Vector3D.create(
        width_tip.x - origin.x, width_tip.y - origin.y, width_tip.z - origin.z
    )
    normal = adsk.core.Vector3D.create(
        normal_tip.x - origin.x, normal_tip.y - origin.y, normal_tip.z - origin.z
    )
    if not width.normalize() or not normal.normalize():
        raise RuntimeError("The FFC start section has no usable frame.")
    meshes = side.meshManager.displayMeshes
    mesh = meshes.item(0) if meshes.count else side.meshManager.createMeshCalculator().calculate()
    if mesh is None or len(mesh.nodeCoordinates) != len(mesh.textureCoordinates):
        raise RuntimeError("Fusion did not provide paired FFC mesh UV coordinates.")
    measured: dict[float, float] = {}
    for node, uv in zip(mesh.nodeCoordinates, mesh.textureCoordinates):
        delta = adsk.core.Vector3D.create(node.x - origin.x, node.y - origin.y, node.z - origin.z)
        if abs(delta.dotProduct(normal)) * 10.0 > 0.01:
            continue
        local_radius_mm = delta.length * 10.0
        maximum_radius_mm = (len(station.centers) / 2.0 + 1.0) * dimensions.pitch_mm
        if local_radius_mm > maximum_radius_mm:
            continue
        across = delta.dotProduct(width) * 10.0
        u = float(uv.x)
        if not math.isfinite(u) or not math.isfinite(across):
            raise RuntimeError("Fusion returned nonfinite FFC texture coordinates.")
        key = round(u, 7)
        prior = measured.get(key)
        if prior is not None and abs(prior - across) > 0.05:
            raise RuntimeError("FFC end-section UV has ambiguous width correspondence.")
        measured[key] = across
    if len(measured) < 4:
        raise RuntimeError("Fusion did not mesh enough FFC end-section UV points.")
    return tuple(sorted(measured.items()))


def _verify_uv_transport(
    start: tuple[tuple[float, float], ...],
    end: tuple[tuple[float, float], ...],
    dimensions: FfcDimensions,
) -> None:
    """
    Require each perimeter U to retain its numbered transverse position.
    """
    if abs(start[0][0] - end[0][0]) > 1e-4 or abs(start[-1][0] - end[-1][0]) > 1e-4:
        raise RuntimeError("FFC sweep changed its transverse UV span between contacts.")
    end_u = tuple(sample[0] for sample in end)
    deviations: list[tuple[float, float, float]] = []
    for u, across in start:
        index = min(max(1, bisect.bisect_right(end_u, u)), len(end) - 1)
        left_u, left_across = end[index - 1]
        right_u, right_across = end[index]
        predicted = left_across + (u - left_u) / (right_u - left_u) * (right_across - left_across)
        deviations.append((u, across, predicted))
    worst = max(deviations, key=lambda item: abs(item[1] - item[2]))
    tolerance_mm = min(dimensions.pitch_mm * 0.06, dimensions.spacing_mm * 0.25)
    if abs(worst[1] - worst[2]) > tolerance_mm:
        reversed_error = max(abs(item[1] + item[2]) for item in deviations)
        raise RuntimeError(
            "FFC sweep changed line-to-contact UV correspondence "
            f"(maximum error {abs(worst[1] - worst[2]):.3f} mm at U={worst[0]:.3f}; "
            f"limit {tolerance_mm:.3f} mm; reversed error {reversed_error:.3f} mm)."
        )


def apply_ffc_trace_texture(
    design: adsk.fusion.Design,
    feature: adsk.fusion.SweepFeature,
    start_station: SolidRibbonSection,
    end_station: SolidRibbonSection,
    dimensions: FfcDimensions,
    colors: tuple[CableColor, ...],
    base: CableColor,
    group_id: UUID,
    transform: adsk.core.Matrix3D,
) -> None:
    """
    Create a document-owned appearance from the swept face's measured UV map.

    The PNG cache is content-addressed; it is retained for design reloads.
    """
    if feature.sideFaces.count != 1:
        raise RuntimeError("FFC texture needs exactly one continuous side face.")
    side = feature.sideFaces.item(0)
    samples = _section_uv_samples(side, start_station, dimensions, transform)
    end_samples = _section_uv_samples(side, end_station, dimensions, transform)
    _verify_uv_transport(samples, end_samples, dimensions)
    row = _texture_row(samples, dimensions, colors, base)
    png = _png_row(row)
    digest = hashlib.sha256(png).hexdigest()[:16]
    TEXTURE_CACHE.mkdir(parents=True, exist_ok=True)
    path = TEXTURE_CACHE / f"ffc-{digest}.png"
    if not path.exists():
        path.write_bytes(png)
    name = f"Cable Bundler FFC UV {group_id} {digest}"
    appearance = design.appearances.itemByName(name)
    if appearance is None:
        library = adsk.core.Application.get().materialLibraries.itemById(
            "BA5EE55E-9982-449B-9D66-9F036540E140"
        )
        source = None if library is None else library.appearances.itemById("Prism-129")
        if source is None:
            raise RuntimeError("Fusion's generic opaque appearance is unavailable.")
        appearance = design.appearances.addByCopy(source, name)
        if appearance is None:
            raise RuntimeError("Fusion could not create the FFC trace appearance.")
    appearance.colorTexture = str(path)
    slot = appearance.appearanceProperties.itemById("opaque_albedo")
    texture = None if slot is None else slot.connectedTexture
    if texture is None:
        raise RuntimeError("Fusion did not connect the FFC trace texture.")
    scale = texture.properties.itemById("texture_RealWorldScaleX")
    offset = texture.properties.itemById("texture_RealWorldOffsetX")
    repeat = texture.properties.itemById("texture_URepeat")
    if scale is None or offset is None or repeat is None:
        raise RuntimeError("Fusion did not expose FFC texture mapping controls.")
    scale.value = UV_SCALE_CM_PER_UNIT * (samples[-1][0] - samples[0][0])
    offset.value = 0.0
    repeat.value = True
    side.appearance = appearance
