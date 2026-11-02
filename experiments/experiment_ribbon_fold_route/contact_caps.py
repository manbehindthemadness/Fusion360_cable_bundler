"""
Certify separated cap half-spaces across continuous straight material bridges.
"""

from __future__ import annotations

from cable_bundler.routing.geometry import difference, dot, magnitude

from .geometry import FoldRoute, Straight, pose_error


def straight_bridge_pairs(route: FoldRoute) -> frozenset[tuple[int, int]]:
    """
    Identify original-piece pairs eligible for the existing cap-neighborhood proof.

    A positive straight bridge places its end cap strictly ahead of its start cap
    along one common normal. Cells behind the first cap and ahead of the second
    cannot intersect. Eligibility alone never skips a pair: both cell-specific
    cap-neighborhood tests remain mandatory in the caller.

    Require continuous ordered rigid frames, only intervening straights, parallel
    cap normals and positive signed separation exceeding a conservative floating/
    frame-error envelope. Tiny or malformed bridges fall back to subdivision.
    This adds a separation certificate, not a clearance tolerance or adjacency exemption.
    """
    pieces = route.pieces
    ends = tuple(piece.end_pose() for piece in pieces)
    joined = tuple(max(pose_error(end, piece.pose)) < 1e-10 for end, piece in zip(ends, pieces[1:]))
    half, thickness = route.half_width_mm, route.targets.diameter_mm / 2
    result = set()
    for first, end in enumerate(ends):
        for second in range(first + 2, len(pieces)):
            bridge = pieces[second - 1]
            if not isinstance(bridge.geometry, Straight) or not all(joined[first:second]):
                break
            a, b = pieces[first], pieces[second]
            axes = (a.pose, b.pose, *(p.pose for p in pieces[first + 1 : second]))
            if any(
                max(
                    abs(dot(p.tangent, p.tangent) - 1),
                    abs(dot(p.width, p.width) - 1),
                    abs(dot(p.tangent, p.width)),
                )
                > 1e-10
                for p in axes
            ):
                continue
            normal_error = magnitude(difference(end.tangent, b.pose.tangent))
            if normal_error > 1e-10:
                continue
            gap = dot(difference(b.pose.origin, end.origin), end.tangent)
            reach = a.geometry.material_length_mm + b.geometry.material_length_mm + half + thickness
            coordinate = max(abs(v) for p in (end.origin, b.pose.origin) for v in (p.x, p.y, p.z))
            uncertainty = 4e-10 * (second - first + 1) * (1 + coordinate + reach)
            uncertainty += normal_error * (b.geometry.material_length_mm + half + thickness)
            if gap > uncertainty:
                result.add((first, second))
    return frozenset(result)
