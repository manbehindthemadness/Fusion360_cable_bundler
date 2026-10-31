"""
Measure local pinch for an unchanged perpendicular profile with no lateral bending.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit

from .pinch import PinchLimit


@dataclass(frozen=True)
class NormalProfilePinch:
    """
    Retain local normal-profile measurements without a native or material-validity claim.
    """

    curvature_per_mm: float
    half_thickness_mm: float
    utilization: float
    minimum_jacobian: float
    actual_radius_mm: float | None
    inside_radius_mm: float | None
    minimum_radius_mm: float
    allowed_fraction: float

    @property
    def within_limit(self) -> bool:
        """
        Require the configured utilization and a strictly positive inner local mapping.
        """
        return self.utilization <= self.allowed_fraction and self.minimum_jacobian > 0


def inspect_normal_profile(
    velocity: Vector3,
    acceleration: Vector3,
    width: Vector3,
    thickness_mm: float,
    limit: PinchLimit,
) -> NormalProfilePinch:
    """
    Check thickness pinch of a fixed profile perpendicular to its actual center tangent.

    Require unit width perpendicular to tangent and curvature. For the declared
    normal-profile sweep X(s,q,v)=r(s)+q*W(s)+v*H(s), its normalized volume
    determinant is 1-kappa*v when curvature has no width component. Thus the
    worst thickness point uses kappa*D/2. Frame twist has no additional multiplier
    in this determinant; a developable sheet with curved transverse sections is
    a different model and must not be silently substituted.

    Reject lateral bending and invalid input rather than apply this restricted
    result outside its assumptions. This local ideal-envelope check does not
    certify strain, global contact, lane spacing or Fusion's actual interpolation.
    """
    if (
        isinstance(thickness_mm, bool)
        or not isinstance(thickness_mm, (int, float))
        or not math.isfinite(thickness_mm)
        or thickness_mm <= 0
        or any(
            not math.isfinite(value)
            for vector in (velocity, acceleration, width)
            for value in (vector.x, vector.y, vector.z)
        )
    ):
        raise ValueError("Use finite vectors and positive physical profile thickness.")
    speed = magnitude(velocity)
    if speed <= 1e-10:
        raise ValueError("A normal profile requires a regular center tangent.")
    tangent = unit(velocity)
    if abs(magnitude(width) - 1) > 1e-8 or abs(dot(width, tangent)) > 1e-8:
        raise ValueError("Profile width must be unit and perpendicular to its center tangent.")
    curvature = magnitude(cross(velocity, acceleration)) / speed**3
    curvature_vector = acceleration.translated(tangent, -dot(acceleration, tangent))
    lateral = abs(dot(curvature_vector, width)) / speed**2
    if lateral > 1e-10 * max(1.0, curvature):
        raise ValueError("Normal-profile pinch requires no lateral bending.")
    half = thickness_mm / 2
    utilization = half * curvature
    radius = 1 / curvature if curvature > 0 else None
    return NormalProfilePinch(
        curvature,
        half,
        utilization,
        1 - utilization,
        radius,
        None if radius is None else radius - half,
        half / limit.fraction,
        limit.fraction,
    )
