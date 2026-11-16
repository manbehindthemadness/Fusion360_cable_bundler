"""
Own one complete canonical bend volume with the same captured midplane and global scalar basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from artifacts.verification.resume3216.spline import Spline
from artifacts.verification.resume3217.extraction import scalar
from artifacts.verification.resume3218.profile import Fields

from .c2_material import MidplaneSource
from .exact_frame import invert
from .volume_boundary import VolumeSpan

Point = tuple[Fraction, ...]


def bend_columns(
    forward: Point, across: Point, cosine: Fraction, sine: Fraction
) -> tuple[Point, Point, Point]:
    """
    Derive the original raw bank frame without normalizing coefficients or extracting any bend spans.
    """
    if any(
        len(p) != 3 or any(type(x) is not Fraction for x in p) for p in (forward, across)
    ) or any(type(x) is not Fraction for x in (cosine, sine)):
        raise ValueError("Exact original pose and bank coefficients required")
    normal = tuple(
        forward[(k + 1) % 3] * across[(k + 2) % 3] - forward[(k + 2) % 3] * across[(k + 1) % 3]
        for k in range(3)
    )
    first = tuple(cosine * a + sine * b for a, b in zip(forward, across))
    second = tuple(-sine * a + cosine * b for a, b in zip(forward, across))
    return first, second, normal


@dataclass(frozen=True)
class VolumeJet:
    """
    Retain exact world position and phase/q/b Jacobian columns of one canonical volume point.
    """

    point: Point
    columns: tuple[Point, Point, Point]


@dataclass(frozen=True)
class BendVolume:
    """
    Preserve one complete C2 material volume without assuming global or native validity.

    A(phi,q) is the SAME captured tensor. N(phi)=-sign*M_x*S(phi)+M_z*C(phi)
    uses the original scalar coefficients and exact fixed frame. Whole-basis
    ownership makes continuity structural; a collection of matching samples or
    unrelated span controls cannot inherit a global certificate.
    """

    source: MidplaneSource
    fields: Fields
    radius_mm: Fraction
    half_thickness_mm: Fraction
    cosine: Fraction
    sine: Fraction
    sign: int
    origin: Point
    forward: Point
    across: Point
    before_mm: Fraction
    columns: tuple[Point, Point, Point] = field(init=False)
    normals: tuple[Spline, Spline, Spline] = field(init=False)

    def __post_init__(self) -> None:
        """
        Reject stale basis ownership and malformed reference metadata without repairing geometry.
        """
        basis = self.source.surface.basis
        if any(
            curve.basis is not basis
            for curve in (self.fields.sine, self.fields.cosine, self.fields.phase)
        ):
            raise ValueError("All scalar fields must own the SAME original captured basis")
        if (
            any(
                type(x) is not Fraction
                for x in (
                    self.radius_mm,
                    self.half_thickness_mm,
                    self.cosine,
                    self.sine,
                    self.before_mm,
                )
            )
            or min(self.radius_mm, self.half_thickness_mm, self.cosine) <= 0
            or type(self.sign) is not int
            or self.sign not in (-1, 1)
            or any(
                len(p) != 3 or any(type(x) is not Fraction for x in p)
                for p in (self.origin, self.forward, self.across)
            )
        ):
            raise ValueError(
                "Exact finite frame/scalars and positive radius/thickness/cosine required"
            )
        first, second, normal = bend_columns(self.forward, self.across, self.cosine, self.sine)
        columns = (first, second, normal)
        normals = tuple(
            Spline(
                basis,
                tuple(
                    -self.sign * first[k] * sv + normal[k] * cv
                    for sv, cv in zip(self.fields.sine.controls, self.fields.cosine.controls)
                ),
            )
            for k in range(3)
        )
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "normals", normals)

    def span(self, index: int) -> VolumeSpan:
        """
        Restrict the same global thickness field to one original span exactly.
        """
        axes = tuple(scalar(curve, index) for curve in self.normals)
        return VolumeSpan(
            self.source, index, tuple(tuple(axis[i] for axis in axes) for i in range(6))
        )

    def jet(self, phase: Fraction, q: Fraction, b: Fraction) -> VolumeJet:
        """
        Evaluate the actual stored volume and derivatives without an analytic-fold substitution.

        Phase and width remain inside the original source. Any exact finite
        thickness coordinate is permitted for conservative contact supersets;
        occupied-section membership is a separate caller check.
        """
        breaks = self.source.surface.basis.breaks
        if any(type(x) is not Fraction for x in (phase, q, b)) or not (
            breaks[0] <= phase <= breaks[-1] and -self.source.half_mm <= q <= self.source.half_mm
        ):
            raise ValueError("Exact original phase/width coordinates required")
        surface = self.source.surface.jet(phase, (q / self.source.half_mm + 1) / 2)
        normals = tuple(curve.jet(phase) for curve in self.normals)
        point = tuple(surface.point[k] + b * normals[k][0] for k in range(3))
        columns = (
            tuple(surface.u[k] + b * normals[k][1] for k in range(3)),
            tuple(x / (2 * self.source.half_mm) for x in surface.v),
            tuple(n[0] for n in normals),
        )
        return VolumeJet(point, columns)

    def reference_lower(self) -> Fraction | None:
        """
        Bound global reference separation in physical crease-distance/q/b coordinates.

        For angle differences <=4, sin(dphi/2)>=dphi/6, giving radial/angular
        lower scale min(1,(R-h)/(3R)). Exact frame inverse and bank-coordinate
        norm bounds transfer it to world coordinates. None means this reference
        cannot qualify the requested domain, not proof of physical infeasibility.
        """
        basis = self.source.surface.basis
        if basis.breaks[0] != 0 or basis.breaks[-1] > 4 or self.half_thickness_mm >= self.radius_mm:
            return None
        frame = invert(self.columns)
        if frame.inverse_norm is None:
            return None
        radial = min(Fraction(1), (self.radius_mm - self.half_thickness_mm) / (3 * self.radius_mm))
        return radial / (2 * frame.inverse_norm * (2 + abs(self.cosine) + abs(self.sine)))
