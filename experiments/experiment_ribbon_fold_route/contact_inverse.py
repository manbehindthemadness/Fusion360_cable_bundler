"""
Recover actual material coordinates for occupied-volume intersection witnesses.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit

from .geometry import PlacedPiece, Straight, relative


def profile_height(q: float, lines: int, diameter: float) -> float:
    """
    Evaluate the preserved joined-lobe contour's positive half-height at material q.

    These are the same three-point circular arcs as ribbon_builder._add_section:
    valley0.6*half-thickness and side extension0.2*half-thickness. No native
    profile or body is created or modified by this analytical containment check.
    """
    h = diameter / 2
    nominal = lines * diameter / 2
    extension, valley = 0.2 * h, 0.6 * h
    if abs(q) > nominal + extension:
        return 0.0
    if abs(q) > nominal:
        radius = (extension**2 + valley**2) / (2 * extension)
        center = nominal + extension - radius
        return math.sqrt(max(0.0, radius**2 - (abs(q) - center) ** 2))
    lane = min(lines - 1, int((q + nominal) / diameter))
    center = -nominal + (lane + 0.5) * diameter
    radius = (h**2 + (h - valley) ** 2) / (2 * (h - valley))
    return h - radius + math.sqrt(max(0.0, radius**2 - (q - center) ** 2))


def occupied_coordinates(
    piece: PlacedPiece, point: Vector3, lines: int, diameter: float
) -> tuple[float, float, float] | None:
    """
    Find a strictly interior preimage in the actual thick joined material profile.

    A returned preimage provides a penetration witness, unlike an overlapping
    bounding envelope. Numerical-boundary points stay unresolved rather than
    becoming claimed penetrations. Each regular single fold is injective.
    """
    p = relative(piece.pose, difference(point, piece.pose.origin))
    if isinstance(piece.geometry, Straight):
        candidates = [(p.x / piece.geometry.material_length_mm, p.y, p.z)]
    else:
        fold = piece.geometry
        c, s = math.cos(fold.bank_radians), math.sin(fold.bank_radians)
        x = c * (p.x - fold.before_mm) + s * p.y
        eta = -s * (p.x - fold.before_mm) + c * p.y
        sign = math.copysign(1.0, fold.angle_radians)
        angle, radius = abs(fold.angle_radians), fold.radius_mm
        unrolled: list[tuple[float, float]] = []
        if x <= 0:
            unrolled.append((x, p.z))
        phase = math.atan2(x, radius - sign * p.z)
        if 0 <= phase <= angle:
            rho = math.hypot(x, p.z - sign * radius)
            unrolled.append((radius * phase, sign * (radius - rho)))
        dx, dz = x - radius * math.sin(angle), p.z - sign * radius * (1 - math.cos(angle))
        along = dx * math.cos(angle) + dz * sign * math.sin(angle)
        if along >= 0:
            unrolled.append(
                (radius * angle + along, -sign * dx * math.sin(angle) + dz * math.cos(angle))
            )
        candidates = [
            ((xi * c - eta * s + fold.before_mm) / fold.material_length_mm, xi * s + eta * c, b)
            for xi, b in unrolled
        ]
    guard = 1e-9 * max(1.0, diameter)
    length = piece.geometry.material_length_mm
    for u, q, b in candidates:
        if (
            guard < u * length < length - guard
            and profile_height(q, lines, diameter) - abs(b) > guard
        ):
            origin, velocity, across, _ = piece.surface(u, q)
            restored = origin.translated(unit(cross(velocity, across)), b)
            if magnitude(difference(restored, point)) <= guard:
                return u, q, b
    return None
