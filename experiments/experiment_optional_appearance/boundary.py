"""
Disambiguate float display samples using their prescribed material crease sections.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc


def boundary_nodes(face: dict[str, Any]) -> set[int]:
    """
    Return actual display-triangle boundary vertices without changing the mesh.
    """
    counts: Counter[tuple[int, int]] = Counter()
    triangles = face["triangles"]
    for i in range(0, len(triangles), 3):
        a, b, c = triangles[i : i + 3]
        counts.update((tuple(sorted(pair)) for pair in ((a, b), (b, c), (c, a))))
    return {index for pair, count in counts.items() if count == 1 for index in pair}


def crease_coordinates(
    piece: PlacedPiece, arc: MaterialArc, point_cm: list[float]
) -> tuple[float, float, float] | None:
    """
    Recognize a known entry/exit section within float32 position uncertainty.

    Only boundary vertices call this helper. A candidate must agree with the
    prescribed crease plane, circular arc and ordered arc extent. It changes no
    point or geometry: it supplies the known phase at a material cross-section,
    avoiding the ill-conditioned angular inverse near a pinched inner skin.
    """
    geometry = piece.geometry
    if not isinstance(geometry, CylindricalFold):
        return None
    uncertainty = (
        math.sqrt(
            sum(
                (10 * 2.0 ** (math.frexp(abs(value))[1] - 25) if value else 10 * 2.0**-150) ** 2
                for value in point_cm
            )
        )
        + 1e-7
    )
    point = Vector3(*(v * 10 for v in point_cm))
    delta = difference(point, piece.pose.origin)
    x, y, z = (
        dot(delta, piece.pose.tangent),
        dot(delta, piece.pose.width),
        dot(delta, unit(cross(piece.pose.tangent, piece.pose.width))),
    )
    c, sn = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
    sign = math.copysign(1, geometry.angle_radians)
    along, axial = c * (x - geometry.before_mm) + sn * y, -sn * (x - geometry.before_mm) + c * y
    a, m, b = arc.point(0), arc.point(0.5), arc.point(1)
    det = 2 * (a[0] * (m[1] - b[1]) + m[0] * (b[1] - a[1]) + b[0] * (a[1] - m[1]))
    aa, mm, bb = (q * q + height * height for q, height in (a, m, b))
    cx = (aa * (m[1] - b[1]) + mm * (b[1] - a[1]) + bb * (a[1] - m[1])) / det
    cy = (aa * (b[0] - m[0]) + mm * (a[0] - b[0]) + bb * (m[0] - a[0])) / det
    radius = math.hypot(a[0] - cx, a[1] - cy)
    candidates = []
    for phase in (0.0, abs(geometry.angle_radians)):
        sine, cosine = math.sin(phase), math.cos(phase)
        plane_error = abs(along * cosine + sign * z * sine - geometry.radius_mm * sine)
        q = c * axial + geometry.radius_mm * phase * sn
        height = -sign * sine * (along - geometry.radius_mm * sine) + cosine * (
            z - sign * geometry.radius_mm * (1 - cosine)
        )
        radial_error = abs(math.hypot(q - cx, height - cy) - radius)
        extent_ok = min(a[0], b[0]) - uncertainty <= q <= max(a[0], b[0]) + uncertainty
        extent_ok = (
            extent_ok
            and min(a[1], m[1], b[1]) - uncertainty <= height <= max(a[1], m[1], b[1]) + uncertainty
        )
        if extent_ok and max(plane_error, radial_error) <= uncertainty:
            s = (
                geometry.before_mm
                + geometry.radius_mm * phase / c
                - q * math.tan(geometry.bank_radians)
            )
            candidates.append((plane_error + radial_error, s, q, height))
    if not candidates:
        return None
    _, s, q, height = min(candidates)
    return s, q, height
