"""
Rasterize one source color function into each unchanged native face chart.
"""

from __future__ import annotations

import math
import struct
import zlib
from collections import deque
from collections.abc import Callable
from typing import Any

SIZE = 128


def png(pixels: bytes, size: int) -> bytes:
    """
    Encode RGB rows in PNG top-to-bottom order without an imaging dependency.
    """

    def chunk(kind: bytes, data: bytes) -> bytes:
        """
        Frame a PNG payload with its checksum.
        """
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\0" + pixels[y * size * 3 : (y + 1) * size * 3] for y in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def raster(
    face: dict[str, Any],
    coordinates: list[tuple[float, float]],
    color_at: Callable[[float, float], tuple[int, int, int]],
) -> tuple[bytes, list[float], int]:
    """
    Rasterize one face chart and extend boundary colors into a filtering gutter.

    Each face has one image; triangles are only interpolation cells in that image.
    """
    uv = face["uv"]
    low = [min(p[a] for p in uv) for a in (0, 1)]
    span = [max(p[a] for p in uv) - low[a] for a in (0, 1)]
    if min(span) <= 1e-12:
        raise RuntimeError("Degenerate native appearance chart")
    # Four texels outside the native chart protect linear filtering at face edges.
    bounds = [
        low[0] - span[0] * 4 / (SIZE - 8),
        low[1] - span[1] * 4 / (SIZE - 8),
        span[0] * SIZE / (SIZE - 8),
        span[1] * SIZE / (SIZE - 8),
    ]
    xy = [
        (
            (p[0] - bounds[0]) / bounds[2] * SIZE - 0.5,
            (1 - (p[1] - bounds[1]) / bounds[3]) * SIZE - 0.5,
        )
        for p in uv
    ]
    pixels = bytearray(SIZE * SIZE * 3)
    covered = bytearray(SIZE * SIZE)
    indices = face["triangles"]
    for k in range(0, len(indices), 3):
        ids = indices[k : k + 3]
        a, b, c = [xy[i] for i in ids]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        for y in range(
            max(0, math.ceil(min(a[1], b[1], c[1]))),
            min(SIZE - 1, math.floor(max(a[1], b[1], c[1]))) + 1,
        ):
            for x in range(
                max(0, math.ceil(min(a[0], b[0], c[0]))),
                min(SIZE - 1, math.floor(max(a[0], b[0], c[0]))) + 1,
            ):
                wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
                wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
                wc = 1 - wa - wb
                if min(wa, wb, wc) < -1e-10:
                    continue
                s, q = (
                    sum(w * coordinates[i][axis] for w, i in zip((wa, wb, wc), ids))
                    for axis in (0, 1)
                )
                index = y * SIZE + x
                pixels[3 * index : 3 * index + 3] = bytes(color_at(s, q))
                covered[index] = 1
    initial = sum(covered)
    if not initial:
        raise RuntimeError("Chart rasterization produced no coverage")
    pending = deque(i for i, v in enumerate(covered) if v)
    while pending:
        index = pending.popleft()
        x, y = index % SIZE, index // SIZE
        for neighbor in (
            (index - 1 if x else -1),
            (index + 1 if x < SIZE - 1 else -1),
            (index - SIZE if y else -1),
            (index + SIZE if y < SIZE - 1 else -1),
        ):
            if neighbor >= 0 and not covered[neighbor]:
                covered[neighbor] = 1
                pixels[neighbor * 3 : neighbor * 3 + 3] = pixels[index * 3 : index * 3 + 3]
                pending.append(neighbor)
    return bytes(pixels), bounds, initial


def sample(pixels: bytes, bounds: list[float], uv: list[float]) -> tuple[float, float, float]:
    """
    Independently bilinearly sample the image that will be assigned to a face.
    """
    x = min(SIZE - 1, max(0, (uv[0] - bounds[0]) / bounds[2] * SIZE - 0.5))
    y = min(SIZE - 1, max(0, (1 - (uv[1] - bounds[1]) / bounds[3]) * SIZE - 0.5))
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    return tuple(
        sum(
            w * pixels[3 * (min(SIZE - 1, iy + dy) * SIZE + min(SIZE - 1, ix + dx)) + a]
            for dx, dy, w in (
                (0, 0, (1 - fx) * (1 - fy)),
                (1, 0, fx * (1 - fy)),
                (0, 1, (1 - fx) * fy),
                (1, 1, fx * fy),
            )
        )
        for a in (0, 1, 2)
    )
