"""
Translate a frozen material map into bounded-error tensor-product surface patches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .geometry import PlacedPiece, Straight
from .material_profile import MaterialArc


@dataclass(frozen=True)
class MaterialPatch:
    """
    Keep native surface controls and their material provenance together.

    Rows advance through longitudinal U; columns follow the clockwise profile V.
    Fold U is bend phase in radians; straight U is a normalized lead fraction.
    """

    piece_index: int
    region: str
    profile_index: int
    degree_u: int
    knots_u: tuple[float, ...]
    rows: tuple[tuple[Vector3, ...], ...]
    profile: MaterialArc
    error_bound_mm: float


def _flat_point(piece: PlacedPiece, u: float, q: float, b: float) -> Vector3:
    """
    Evaluate a terminal flat material section, including its prescribed thickness.
    """
    point, velocity, across, _ = piece.surface(u, q)
    return point.translated(unit(cross(velocity, across)), b)


def _bent_point(
    fold: CylindricalFold, phase: float, q: float, b: float, *, derivative: bool = False
) -> Vector3:
    """
    Evaluate the exact physical map in crease coordinates, or its phase derivative.

    Material s=before+R*phase/cos(bank)-q*tan(bank). This reparameterizes
    the supplied isometry; it does not replace it with perpendicular sections.
    """
    c, s = math.cos(fold.bank_radians), math.sin(fold.bank_radians)
    sign = math.copysign(1, fold.angle_radians)
    radius = fold.radius_mm
    if derivative:
        along = (radius - sign * b) * math.cos(phase)
        axial = -radius * s / c
        z = (sign * radius - b) * math.sin(phase)
        origin = 0.0
    else:
        along = (radius - sign * b) * math.sin(phase)
        axial = -radius * phase * s / c + q / c
        z = sign * radius * (1 - math.cos(phase)) + b * math.cos(phase)
        origin = fold.before_mm
    return Vector3(origin + c * along - s * axial, s * along + c * axial, z)


def material_patches(
    pieces: tuple[PlacedPiece, ...],
    profile: tuple[MaterialArc, ...],
    *,
    maximum_phase_step: float = 0.025,
) -> tuple[MaterialPatch, ...]:
    """
    Construct fixed patches without fitting, rerouting or changing material limits.

    Planar leads and rational circular profile sections are exact. Cubic Hermite
    phase interpolation has a stated positional bound; it is not an exact helix
    or a continuous curvature/contact certificate. Zero-length complete leads
    are omitted. A tip-only zero-length edge remains a triangular face boundary.
    """
    if not math.isfinite(maximum_phase_step) or not 0 < maximum_phase_step <= 0.1:
        raise ValueError("A phase step in (0,0.1] radians is required.")
    patches = []
    for piece_index, piece in enumerate(pieces):
        geometry = piece.geometry
        if isinstance(geometry, Straight):
            regions = ("straight",)
        else:
            regions = (
                (("before",) if geometry.before_mm > 0 else ())
                + ("bend",)
                + (("after",) if geometry.after_mm > 0 else ())
            )
        for region in regions:
            for profile_index, arc in enumerate(profile):
                if region == "bend":
                    if not isinstance(geometry, CylindricalFold):
                        raise TypeError("A bend patch requires cylindrical material geometry.")
                    count = math.ceil(abs(geometry.angle_radians) / maximum_phase_step)
                    breaks = tuple(
                        abs(geometry.angle_radians) * i / count for i in range(count + 1)
                    )
                    rows = []
                    for low, high in zip(breaks, breaks[1:]):
                        width = (high - low) / 3
                        start = [_bent_point(geometry, low, q, b) for q, b in arc.controls]
                        end = [_bent_point(geometry, high, q, b) for q, b in arc.controls]
                        if not rows:
                            rows.append(tuple(piece.pose.point(p) for p in start))
                        rows.extend(
                            (
                                tuple(
                                    piece.pose.point(
                                        p.translated(
                                            _bent_point(geometry, low, q, b, derivative=True), width
                                        )
                                    )
                                    for p, (q, b) in zip(start, arc.controls)
                                ),
                                tuple(
                                    piece.pose.point(
                                        p.translated(
                                            _bent_point(geometry, high, q, b, derivative=True),
                                            -width,
                                        )
                                    )
                                    for p, (q, b) in zip(end, arc.controls)
                                ),
                                tuple(piece.pose.point(p) for p in end),
                            )
                        )
                    # Bound applies to the physical contour, not its off-circle controls.
                    height = max(abs(b) for a in profile for _, b in a.controls)
                    bound = (
                        math.sqrt(2)
                        * (geometry.radius_mm + height)
                        * (abs(geometry.angle_radians) / count) ** 4
                        / 384
                    )
                    knots = (
                        (0.0,) * 4
                        + tuple(v for v in breaks[1:-1] for _ in range(3))
                        + (breaks[-1],) * 4
                    )
                    patches.append(
                        MaterialPatch(
                            piece_index, region, profile_index, 3, knots, tuple(rows), arc, bound
                        )
                    )
                    continue
                first = []
                last = []
                for q, b in arc.controls:
                    if isinstance(geometry, Straight):
                        start, end = _flat_point(piece, 0, q, b), _flat_point(piece, 1, q, b)
                    elif region == "before":
                        start = _flat_point(piece, 0, q, b)
                        end = piece.pose.point(_bent_point(geometry, 0, q, b))
                    else:
                        start = piece.pose.point(
                            _bent_point(geometry, abs(geometry.angle_radians), q, b)
                        )
                        end = _flat_point(piece, 1, q, b)
                    first.append(start)
                    last.append(end)
                patches.append(
                    MaterialPatch(
                        piece_index,
                        region,
                        profile_index,
                        1,
                        (0.0, 0.0, 1.0, 1.0),
                        (tuple(first), tuple(last)),
                        arc,
                        0.0,
                    )
                )
    return tuple(patches)
