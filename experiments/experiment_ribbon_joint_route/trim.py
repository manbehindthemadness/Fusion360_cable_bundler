"""
Certify strict UV interior from complete rectangular trim sides and collapsed edges.
"""

from __future__ import annotations

import math

UV = tuple[float, float]
Segment = tuple[UV, UV]


def rectangular_interior(
    bounds: tuple[float, float, float, float],
    segments: tuple[Segment, ...],
    collapsed: frozenset[str],
    point: UV,
) -> bool:
    """
    Verify one complete rectangle, allowing only independently collapsed missing sides.

    All supplied segments must span a distinct full rectangle side. Endpoint
    uncertainty is1e-9of normalized UV extent; the query must lie farther than
    1e-8from every side. Missing sides require a separate physical constant-edge
    certificate. This is not polygon sampling, a physical tolerance change or a
    certificate for curved, holed, partial, overlapping or arbitrary trim loops.
    """
    low_u, high_u, low_v, high_v = bounds
    if high_u <= low_u or high_v <= low_v or len(segments) not in (3, 4):
        return False
    if any(not math.isfinite(v) for v in (*bounds, *point)):
        return False

    def normalized(uv: UV) -> UV:
        """
        Compare both parameter axes independently of material and phase units.
        """
        return (uv[0] - low_u) / (high_u - low_u), (uv[1] - low_v) / (high_v - low_v)

    u, v = normalized(point)
    if not (1e-8 < u < 1 - 1e-8 and 1e-8 < v < 1 - 1e-8):
        return False
    corners = {
        "u0": ((0.0, 0.0), (0.0, 1.0)),
        "u1": ((1.0, 0.0), (1.0, 1.0)),
        "v0": ((0.0, 0.0), (1.0, 0.0)),
        "v1": ((0.0, 1.0), (1.0, 1.0)),
    }
    seen = set()
    for first, last in segments:
        if any(not math.isfinite(x) for x in (*first, *last)):
            return False
        a, b = normalized(first), normalized(last)
        side = None
        for name, (start, end) in corners.items():
            direct = max(abs(x - y) for x, y in zip((*a, *b), (*start, *end)))
            reverse = max(abs(x - y) for x, y in zip((*a, *b), (*end, *start)))
            if min(direct, reverse) <= 1e-9:
                side = name
                break
        if side is None or side in seen:
            return False
        seen.add(side)
    return set(corners) - seen <= collapsed
