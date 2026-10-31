"""
Map a flat material strip through one finite-radius diagonal cylindrical fold.

This authored reference preserves the mid-surface metric and has flat end caps.
It is not an endpoint solver or the geometry produced by a rigid-profile sweep.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3


@dataclass(frozen=True)
class CylindricalFold:
    """
    Round a straight crease while preserving material length and width locally.

    u advances through the same material interval on every lane. The diagonal
    crease shifts bend entry/exit along each lane. Transverse material lines
    curve within the fold; they are not rigid perpendicular sections. Curvature
    jumps at the two G1 joins; contact, equilibrium and native builds are absent.
    """

    radius_mm: float
    angle_radians: float
    bank_radians: float
    width_mm: float
    before_mm: float
    after_mm: float

    def __post_init__(self) -> None:
        """
        Require regular finite folds with the entire terminal profiles flat.
        """
        values = (
            self.radius_mm,
            self.angle_radians,
            self.bank_radians,
            self.width_mm,
            self.before_mm,
            self.after_mm,
        )
        if any(isinstance(value, bool) or not math.isfinite(value) for value in values):
            raise ValueError("Fold dimensions and angles must be finite numbers.")
        if (
            min(self.radius_mm, self.width_mm) <= 0
            or not 0 < abs(self.angle_radians) <= math.pi
            or abs(self.bank_radians) >= math.pi / 2 - 1e-6
            or min(self.before_mm, self.after_mm)
            < self.width_mm / 2 * abs(math.tan(self.bank_radians))
        ):
            raise ValueError(
                "Positive radius/width, regular crease and flat terminal profiles required."
            )

    @property
    def material_length_mm(self) -> float:
        """
        Return the common exact material length of every longitudinal lane.
        """
        return (
            self.before_mm
            + self.radius_mm * abs(self.angle_radians) / math.cos(self.bank_radians)
            + self.after_mm
        )

    def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Return position, u derivative, material-width derivative and u acceleration.

        The unrolled orthogonal coordinates are xi=s*cos(a)+q*sin(a) and
        eta=-s*sin(a)+q*cos(a). Wrapping xi around a cylinder preserves
        |X_s|=|X_q|=1 and X_s dot X_q=0. Hence every fixed-q path has the same
        length without compensating stretch or a longitudinal material reversal.
        """
        if (
            isinstance(u, bool)
            or isinstance(q, bool)
            or not math.isfinite(u)
            or not math.isfinite(q)
            or not 0 <= u <= 1
            or abs(q) > self.width_mm / 2
        ):
            raise ValueError("Fold coordinates must lie within the material strip.")
        length = self.material_length_mm
        c, s = math.cos(self.bank_radians), math.sin(self.bank_radians)
        along = u * length - self.before_mm
        xi, eta = along * c + q * s, -along * s + q * c
        angle = abs(self.angle_radians)
        sign = math.copysign(1, self.angle_radians)
        arc = self.radius_mm * angle
        if xi <= 0:
            x, z, dx, dz, ddx, ddz = xi, 0.0, 1.0, 0.0, 0.0, 0.0
        elif xi >= arc:
            x = self.radius_mm * math.sin(angle) + (xi - arc) * math.cos(angle)
            z = sign * (self.radius_mm * (1 - math.cos(angle)) + (xi - arc) * math.sin(angle))
            dx, dz = math.cos(angle), sign * math.sin(angle)
            ddx, ddz = 0.0, 0.0
        else:
            phase = xi / self.radius_mm
            x, z = self.radius_mm * math.sin(phase), sign * self.radius_mm * (1 - math.cos(phase))
            dx, dz = math.cos(phase), sign * math.sin(phase)
            ddx, ddz = -math.sin(phase) / self.radius_mm, sign * math.cos(phase) / self.radius_mm
        position = Vector3(c * x - s * eta + self.before_mm, s * x + c * eta, z)
        velocity = Vector3(
            length * (c * c * dx + s * s), length * c * s * (dx - 1), length * c * dz
        )
        across = Vector3(c * s * (dx - 1), s * s * dx + c * c, s * dz)
        acceleration = Vector3(
            length**2 * c**3 * ddx, length**2 * c**2 * s * ddx, length**2 * c**2 * ddz
        )
        return position, velocity, across, acceleration

    def lane(self, u: float, offset_mm: float) -> tuple[Vector3, Vector3]:
        """
        Return the actual material lane rather than a straight profile offset.
        """
        position, velocity, _, _ = self.surface(u, offset_mm)
        return position, velocity

    def bend_interval(self, q: float) -> tuple[float, float]:
        """
        Return the lane's staggered bend-entry and bend-exit material fractions.
        """
        self.surface(0, q)
        c, s = math.cos(self.bank_radians), math.sin(self.bank_radians)
        low = (self.before_mm - q * s / c) / self.material_length_mm
        high = low + self.radius_mm * abs(self.angle_radians) / (c * self.material_length_mm)
        return low, high
