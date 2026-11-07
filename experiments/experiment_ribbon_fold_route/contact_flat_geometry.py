"""
Describe exact flat material regions and their unchanged circular profile intervals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import cross
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_convex import Triple, add, dot, scaled, subtract, triple
from .geometry import PlacedPiece

Point = tuple[float, float]
Polygon = tuple[Point, ...]


class FlatPhase(Enum):
    """
    Identify a stable affine region independently of changing joint coordinates.
    """

    STRAIGHT = "straight"
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True)
class ProfileArc:
    """
    Bound one upper joined-profile circular arc; the lower boundary is its reflection.
    """

    low_q: float
    high_q: float
    center_q: float
    center_height: float
    radius: float

    def height(self, q: float) -> float:
        """
        Evaluate the established circular contour on this arc's declared interval.
        """
        return self.center_height + math.sqrt(max(0.0, self.radius**2 - (q - self.center_q) ** 2))

    def maximum_height(self) -> float:
        """
        Enclose every true profile height across the complete interval.
        """
        return self.height(min(self.high_q, max(self.low_q, self.center_q)))


def profile_arcs(lines: int, diameter: float) -> tuple[ProfileArc, ...]:
    """
    Retain the same circular lobes,0.6half-height valleys and0.2half-height side extensions.
    """
    if type(lines) is not int or lines < 1 or not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Positive conductor count and finite diameter required")
    half = diameter / 2
    nominal = lines * half
    extension, valley = 0.2 * half, 0.6 * half
    side_radius = (extension**2 + valley**2) / (2 * extension)
    radius = (half**2 + (half - valley) ** 2) / (2 * (half - valley))
    result = [
        ProfileArc(
            -nominal - extension, -nominal, -(nominal + extension - side_radius), 0.0, side_radius
        )
    ]
    for index in range(lines):
        low = -nominal + index * diameter
        result.append(ProfileArc(low, low + diameter, low + half, half - radius, radius))
    result.append(
        ProfileArc(
            nominal, nominal + extension, nominal + extension - side_radius, 0.0, side_radius
        )
    )
    return tuple(result)


def clip(polygon: Polygon, a: float, b: float, cut: float) -> Polygon:
    """
    Retain the closed half polygon a*s+b*q<=cut, with an outward numerical cut guard.

    This polygon is used for witness proposals and conservative motion guidance,
    never as an independent positive contact certificate.
    """
    cut += 1e-12 * (1 + abs(cut))
    result: list[Point] = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        first, second = a * start[0] + b * start[1] - cut, a * end[0] + b * end[1] - cut
        if first <= 0:
            result.append(start)
        if first < 0 < second or second < 0 < first:
            t = first / (first - second)
            result.append((start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])))
    return tuple(result)


@dataclass(frozen=True)
class FlatRegion:
    """
    Carry one affine material polygon and its rigid world placement.
    """

    phase: FlatPhase
    polygon: Polygon
    origin: Triple
    tangent: Triple
    width: Triple
    normal: Triple
    cap_origin: Triple


def region(piece: PlacedPiece, phase: FlatPhase, low_q: float, high_q: float) -> FlatRegion:
    """
    Retain the complete longitudinal before/after-flat region in one fixed profile interval.
    """
    geometry = piece.geometry
    length = geometry.material_length_mm
    polygon = ((0.0, low_q), (length, low_q), (length, high_q), (0.0, high_q))
    pose = piece.pose
    origin = triple(pose.origin)
    if isinstance(geometry, CylindricalFold):
        c, s = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
        if phase is FlatPhase.BEFORE:
            polygon = clip(polygon, c, s, geometry.before_mm * c)
        elif phase is FlatPhase.AFTER:
            polygon = clip(
                polygon,
                -c,
                -s,
                -geometry.before_mm * c - geometry.radius_mm * abs(geometry.angle_radians),
            )
            pose = piece.end_pose()
            origin = subtract(triple(pose.origin), scaled(triple(pose.tangent), length))
        else:
            raise ValueError("A fold requires an explicit before/after flat region")
    elif phase is not FlatPhase.STRAIGHT:
        raise ValueError("A straight has no cylindrical transition")
    return FlatRegion(
        phase,
        polygon,
        origin,
        triple(pose.tangent),
        triple(pose.width),
        triple(cross(pose.tangent, pose.width)),
        triple(pose.origin),
    )


@dataclass(frozen=True)
class Shape:
    """
    Supply actual extrema of one affine polygon restricted to one circular profile interval.
    """

    placement: FlatRegion
    arc: ProfileArc

    @property
    def origin(self) -> Triple:
        """
        Return the shared material phase origin for deterministic probe initialization.
        """
        return self.placement.origin

    def support(self, direction: Triple) -> Triple:
        """
        Maximize affine longitudinal motion plus the exact circular profile support.
        """
        placement = self.placement
        a, b, g = (
            dot(placement.tangent, direction),
            dot(placement.width, direction),
            dot(placement.normal, direction),
        )
        best = -math.inf
        selected = 0.0, 0.0, 0.0
        for start, end in zip(placement.polygon, placement.polygon[1:] + placement.polygon[:1]):
            ds, dq = end[0] - start[0], end[1] - start[1]
            parameters = [0.0, 1.0]
            if dq != 0 and g != 0:
                linear = a * ds / dq + b
                q = self.arc.center_q + self.arc.radius * linear / math.hypot(linear, g)
                t = (q - start[1]) / dq
                if 0 < t < 1:
                    parameters.append(t)
            for t in parameters:
                along, q = start[0] + ds * t, start[1] + dq * t
                height = math.copysign(self.arc.height(q), g)
                value = a * along + b * q + g * height
                if value > best:
                    best, selected = value, (along, q, height)
        return add(
            placement.origin,
            add(
                scaled(placement.tangent, selected[0]),
                add(scaled(placement.width, selected[1]), scaled(placement.normal, selected[2])),
            ),
        )


def shapes(piece: PlacedPiece, arcs: tuple[ProfileArc, ...]) -> tuple[Shape, ...]:
    """
    Cover every flat profile region; curved material remains the full checker's responsibility.
    """
    phases = (
        (FlatPhase.BEFORE, FlatPhase.AFTER)
        if isinstance(piece.geometry, CylindricalFold)
        else (FlatPhase.STRAIGHT,)
    )
    result = []
    for phase in phases:
        full = region(piece, phase, arcs[0].low_q, arcs[-1].high_q)
        if not full.polygon:
            continue
        for arc in arcs:
            polygon = clip(clip(full.polygon, 0.0, 1.0, arc.high_q), 0.0, -1.0, -arc.low_q)
            if len(polygon) >= 3:
                placement = FlatRegion(
                    phase,
                    polygon,
                    full.origin,
                    full.tangent,
                    full.width,
                    full.normal,
                    full.cap_origin,
                )
                result.append(Shape(placement, arc))
    return tuple(result)
