"""
Enclose thick material cells analytically instead of treating display meshes as solids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, dot
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_extrema import prepare_extrema
from .geometry import PlacedPiece, Straight


@dataclass(frozen=True)
class Span:
    """
    Carry outward-rounded floating interval bounds, including trigonometric extrema.
    """

    low: float
    high: float

    def add(self, other: Span) -> Span:
        """
        Enclose the sum of both intervals.
        """
        return Span(
            math.nextafter(self.low + other.low, -math.inf),
            math.nextafter(self.high + other.high, math.inf),
        )

    def scale(self, value: float) -> Span:
        """
        Enclose multiplication by one fixed coefficient.
        """
        a, b = self.low * value, self.high * value
        return Span(math.nextafter(min(a, b), -math.inf), math.nextafter(max(a, b), math.inf))

    def multiply(self, other: Span) -> Span:
        """
        Enclose the product of both intervals.
        """
        values = (
            self.low * other.low,
            self.low * other.high,
            self.high * other.low,
            self.high * other.high,
        )
        return Span(math.nextafter(min(values), -math.inf), math.nextafter(max(values), math.inf))

    def sine(self) -> Span:
        """
        Include endpoint values and every interior sine extremum.
        """
        values = [math.sin(self.low), math.sin(self.high)]
        low = math.ceil((self.low - math.pi / 2) / math.pi)
        high = math.floor((self.high - math.pi / 2) / math.pi)
        values.extend(1.0 if k % 2 == 0 else -1.0 for k in range(low, high + 1))
        return Span(min(values) - 2e-15, max(values) + 2e-15)

    def cosine(self) -> Span:
        """
        Bound cosine through the same complete sine-extremum calculation.
        """
        return self.add(Span(math.pi / 2, math.pi / 2)).sine()


@dataclass(frozen=True)
class Cell:
    """
    Select a closed material box within one original route piece.
    """

    piece: int
    u: Span
    q: Span
    height: Span
    depth: int = 0

    def split(self, length: float) -> tuple[Cell, Cell]:
        """
        Bisect the largest material-space span, retaining every part of the box.
        """
        spans = (self.u, self.q, self.height)
        sizes = (
            (self.u.high - self.u.low) * length,
            self.q.high - self.q.low,
            self.height.high - self.height.low,
        )
        index = max(range(3), key=lambda i: sizes[i])
        span = spans[index]
        middle = (span.low + span.high) / 2
        first, second = list(spans), list(spans)
        first[index], second[index] = Span(span.low, middle), Span(middle, span.high)
        return Cell(self.piece, *first, self.depth + 1), Cell(self.piece, *second, self.depth + 1)


def projection(piece: PlacedPiece, cell: Cell, axis: Vector3) -> Span:
    """
    Enclose the full thick material cell using the shared prepared projection.
    """
    return prepare_projection(piece, axis)(cell)


def prepare_projection(piece: PlacedPiece, axis: Vector3) -> Callable[[Cell], Span]:
    """
    Prepare fixed piece/axis transforms while retaining the exact analytic cell enclosure.

    Correlated edge extrema and their rounding guard remain unchanged. The returned
    evaluator is bound to immutable material geometry and one axis. Callers may
    cache it within a bounded measurement context; no global route cache is held.
    Nonfinite or underflowed extrema retain the interval-arithmetic fallback.
    """
    if isinstance(piece.geometry, Straight):
        projected_origin = dot(piece.pose.origin, axis)
        length = piece.geometry.material_length_mm
        coefficients = (
            dot(piece.pose.tangent, axis),
            dot(piece.pose.width, axis),
            dot(cross(piece.pose.tangent, piece.pose.width), axis),
        )

        def straight_bound(cell: Cell) -> Span:
            """
            Retain the established outward-rounded straight material enclosure.
            """
            return _straight_projection(projected_origin, length, coefficients, cell)

        return straight_bound
    fold = piece.geometry
    c, s = math.cos(fold.bank_radians), math.sin(fold.bank_radians)
    alpha = dot(piece.pose.direction(Vector3(c, s, 0)), axis)
    beta = dot(piece.pose.direction(Vector3(-s, c, 0)), axis)
    gamma = dot(cross(piece.pose.tangent, piece.pose.width), axis)
    tangent = dot(piece.pose.tangent, axis)
    base = dot(piece.pose.origin, axis) + fold.before_mm * tangent
    origin = piece.pose.origin
    translation_scale = abs(origin.x * axis.x) + abs(origin.y * axis.y) + abs(origin.z * axis.z)
    length = fold.material_length_mm
    bound_extrema = prepare_extrema(fold, alpha, beta, gamma)

    def fold_bound(cell: Cell) -> Span:
        """
        Bound one complete thick cell with the original correlated-extrema arithmetic.
        """
        corners = []
        for u, q in (
            (cell.u.low, cell.q.low),
            (cell.u.high, cell.q.low),
            (cell.u.high, cell.q.high),
            (cell.u.low, cell.q.high),
        ):
            along = u * length - fold.before_mm
            corners.append((c * along + s * q, -s * along + c * q))
        result = bound_extrema(tuple(corners), (cell.height.low, cell.height.high))
        extent = fold.radius_mm * 2 + max(abs(x) for x, _ in corners)
        extent += max(abs(cell.height.low), abs(cell.height.high))
        scale = (
            1
            + translation_scale
            + abs(fold.before_mm * tangent)
            + (abs(alpha) + abs(gamma)) * extent
            + abs(beta) * max(abs(y) for _, y in corners)
        )
        if result is None or not math.isfinite(base + scale):
            return interval_projection(piece, cell, axis)
        guard = 1e-11 * scale
        return Span(base + result[0] - guard, base + result[1] + guard)

    return fold_bound


def _straight_projection(
    origin: float, length: float, coefficients: tuple[float, float, float], cell: Cell
) -> Span:
    """
    Preserve every original interval operation while reusing fixed straight transform coefficients.
    """
    result = Span(origin, origin)
    for span, coefficient in zip((cell.u.scale(length), cell.q, cell.height), coefficients):
        result = result.add(span.scale(coefficient))
    guard = 1e-11 * (1 + max(abs(result.low), abs(result.high)))
    return Span(result.low - guard, result.high + guard)


def interval_projection(piece: PlacedPiece, cell: Cell, axis: Vector3) -> Span:
    """
    Enclose all occupied points of a material cell projected onto a fixed axis.

    The rectangular +/-half-thickness envelope contains the actual joined profile.
    Dependencies between xi and eta are dropped conservatively. A small numerical
    enclosure guard accounts for floating transforms; it is not physical clearance.
    """
    origin = dot(piece.pose.origin, axis)
    if isinstance(piece.geometry, Straight):
        return _straight_projection(
            origin,
            piece.geometry.material_length_mm,
            (
                dot(piece.pose.tangent, axis),
                dot(piece.pose.width, axis),
                dot(cross(piece.pose.tangent, piece.pose.width), axis),
            ),
            cell,
        )
    else:
        fold = piece.geometry
        c, s = math.cos(fold.bank_radians), math.sin(fold.bank_radians)
        along = cell.u.scale(fold.material_length_mm).add(Span(-fold.before_mm, -fold.before_mm))
        xi = along.scale(c).add(cell.q.scale(s))
        eta = along.scale(-s).add(cell.q.scale(c))
        sign = math.copysign(1.0, fold.angle_radians)
        angle = abs(fold.angle_radians)
        arc = fold.radius_mm * angle
        parts: list[tuple[Span, Span]] = []
        if xi.low <= 0:
            parts.append((Span(xi.low, min(0.0, xi.high)), cell.height))
        if xi.high >= 0 and xi.low <= arc:
            phase = Span(max(0.0, xi.low), min(arc, xi.high)).scale(1 / fold.radius_mm)
            rho = cell.height.scale(-sign).add(Span(fold.radius_mm, fold.radius_mm))
            x = rho.multiply(phase.sine())
            z = (
                rho.multiply(phase.cosine())
                .scale(-sign)
                .add(Span(sign * fold.radius_mm, sign * fold.radius_mm))
            )
            parts.append((x, z))
        if xi.high >= arc:
            delta = Span(max(arc, xi.low) - arc, xi.high - arc)
            x = (
                delta.scale(math.cos(angle))
                .add(cell.height.scale(-sign * math.sin(angle)))
                .add(Span(fold.radius_mm * math.sin(angle), fold.radius_mm * math.sin(angle)))
            )
            z = (
                delta.scale(sign * math.sin(angle))
                .add(cell.height.scale(math.cos(angle)))
                .add(
                    Span(
                        sign * fold.radius_mm * (1 - math.cos(angle)),
                        sign * fold.radius_mm * (1 - math.cos(angle)),
                    )
                )
            )
            parts.append((x, z))
        e1 = piece.pose.direction(Vector3(c, s, 0))
        e2 = piece.pose.direction(Vector3(-s, c, 0))
        normal = cross(piece.pose.tangent, piece.pose.width)
        base = origin + fold.before_mm * dot(piece.pose.tangent, axis)
        projections = [
            Span(base, base)
            .add(x.scale(dot(e1, axis)))
            .add(eta.scale(dot(e2, axis)))
            .add(z.scale(dot(normal, axis)))
            for x, z in parts
        ]
        result = Span(min(p.low for p in projections), max(p.high for p in projections))
    guard = 1e-11 * (1 + max(abs(result.low), abs(result.high)))
    return Span(result.low - guard, result.high + guard)


def cap_neighborhood(piece: PlacedPiece, cell: Cell, at_end: bool) -> bool:
    """
    Prove a material region stays on its proper side of a shared terminal plane.

    Within90degrees of a flat cap, F_s dot T_cap is nonnegative and is positive
    on every nonempty inward interval when R>half-thickness. Adjacent regions
    satisfying this condition can share their cap without volume intersection.
    Entire adjacent pieces are never exempted merely because they are neighbors.
    """
    if isinstance(piece.geometry, Straight):
        return True
    fold: CylindricalFold = piece.geometry
    c, s = math.cos(fold.bank_radians), math.sin(fold.bank_radians)
    values = [
        (u * fold.material_length_mm - fold.before_mm) * c + q * s
        for u in (cell.u.low, cell.u.high)
        for q in (cell.q.low, cell.q.high)
    ]
    low = max(0.0, min(abs(fold.angle_radians), min(values) / fold.radius_mm))
    high = max(0.0, min(abs(fold.angle_radians), max(values) / fold.radius_mm))
    deviation = abs(fold.angle_radians) - low if at_end else high
    return deviation <= math.pi / 2
