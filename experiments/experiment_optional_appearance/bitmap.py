"""
Read bounded RGB PNG assets and sample repeated color maps in material space.
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Bitmap:
    """
    Retain unlit RGB bytes in top-to-bottom image order.
    """

    width: int
    height: int
    pixels: bytes

    def sample(self, u: float, v: float) -> tuple[int, int, int]:
        """
        Repeat and bilinearly sample image coordinates with V increasing upward.
        """
        x = (u % 1) * self.width - 0.5
        y = ((1 - v) % 1) * self.height - 0.5
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x - ix, y - iy
        result = []
        for axis in range(3):
            value = 0.0
            for dx, dy, weight in (
                (0, 0, (1 - fx) * (1 - fy)),
                (1, 0, fx * (1 - fy)),
                (0, 1, (1 - fx) * fy),
                (1, 1, fx * fy),
            ):
                index = ((iy + dy) % self.height * self.width + (ix + dx) % self.width) * 3
                value += weight * self.pixels[index + axis]
            result.append(round(value))
        return result[0], result[1], result[2]


def read_png(path: Path) -> Bitmap:
    """
    Decode noninterlaced RGB/RGBA8 PNGs; reject unsupported formats explicitly.
    """
    data = path.read_bytes()
    if len(data) > 16 * 1024 * 1024 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Expected a bounded PNG asset")
    offset = 8
    payload = bytearray()
    width = height = channels = 0
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        block = data[offset + 8 : offset + 8 + size]
        if offset + size + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        crc = struct.unpack(">I", data[offset + 8 + size : offset + 12 + size])[0]
        if zlib.crc32(kind + block) & 0xFFFFFFFF != crc:
            raise ValueError("PNG checksum failure")
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">2I5B", block
            )
            if depth != 8 or color not in (2, 6) or compression or filtering or interlace:
                raise ValueError("Only noninterlaced RGB/RGBA8 PNG assets are supported")
            if not 0 < width <= 2048 or not 0 < height <= 2048:
                raise ValueError("Source image dimensions exceed the experiment limit")
            channels = 3 if color == 2 else 4
        elif kind == b"IDAT":
            payload.extend(block)
        offset += size + 12
    if not channels:
        raise ValueError("Missing PNG header")
    stride = width * channels
    decoder = zlib.decompressobj()
    raw = decoder.decompress(payload, (stride + 1) * height + 1)
    if not decoder.eof or len(raw) != (stride + 1) * height:
        raise ValueError("PNG payload length mismatch")
    previous = bytearray(stride)
    result = bytearray()
    for y in range(height):
        start = y * (stride + 1)
        mode = raw[start]
        row = bytearray(raw[start + 1 : start + stride + 1])
        if mode > 4:
            raise ValueError("Unknown PNG scanline filter")
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = up
            elif mode == 3:
                predictor = (left + up) // 2
            elif mode == 4:
                p = left + up - corner
                distances = abs(p - left), abs(p - up), abs(p - corner)
                predictor = (
                    left
                    if distances[0] <= min(distances[1:])
                    else up
                    if distances[1] <= distances[2]
                    else corner
                )
            else:
                predictor = 0
            row[i] = (row[i] + predictor) % 256
        if channels == 4 and any(row[i] != 255 for i in range(3, stride, 4)):
            raise ValueError("Translucent source images are outside the opaque-color trial")
        result.extend(value for i, value in enumerate(row) if channels == 3 or i % 4 != 3)
        previous = row
    return Bitmap(width, height, bytes(result))


@dataclass(frozen=True)
class ColorMap:
    """
    Sample a supported repeated source bitmap at physical material millimetres.
    """

    bitmap: Bitmap
    scale_mm: tuple[float, float]

    def __post_init__(self) -> None:
        """
        Reject singular or nonfinite source texture dimensions.
        """
        if any(not math.isfinite(v) or v <= 0 for v in self.scale_mm):
            raise ValueError("Finite positive texture dimensions are required")

    def sample(self, s: float, q: float) -> tuple[int, int, int]:
        """
        Evaluate the source image with zero offset/rotation and both repeats on.
        """
        return self.bitmap.sample(s / self.scale_mm[0], q / self.scale_mm[1])
