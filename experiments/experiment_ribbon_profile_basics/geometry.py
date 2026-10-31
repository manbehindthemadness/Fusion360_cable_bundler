"""
Define frozen elementary reference geometry independently of endpoint path solving.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit


def _fraction(u: float) -> None:
    """
    Reject fractions outside the closed reference domain before evaluating geometry.
    """
    if (
        isinstance(u, bool)
        or not isinstance(u, (int, float))
        or not math.isfinite(u)
        or not 0 <= u <= 1
    ):
        raise ValueError("Reference fractions lie within the closed unit interval.")


class ReferenceCurve(Protocol):
    """
    Expose authored position/derivatives and a perpendicular width for local profile checks.
    """

    def jet(self, u: float) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate position and first/second derivatives within the closed unit interval.
        """
        ...

    def width(self, u: float) -> Vector3:
        """
        Return a unit profile axis with no component in the bend-normal direction.
        """
        ...


@dataclass(frozen=True)
class Arc:
    """
    Author an exact circle segment with fixed geometric plane and radius.
    """

    start: Vector3
    tangent: Vector3
    normal: Vector3
    radius_mm: float
    angle: float = math.pi / 2

    def __post_init__(self) -> None:
        """
        Require a finite oriented plane and positive radius/sweep before sampling.
        """
        if (
            not all(
                math.isfinite(value)
                for vector in (self.start, self.tangent, self.normal)
                for value in (vector.x, vector.y, vector.z)
            )
            or not math.isfinite(self.radius_mm)
            or self.radius_mm <= 0
            or not math.isfinite(self.angle)
            or self.angle <= 0
        ):
            raise ValueError("A reference arc needs finite axes and positive radius/sweep.")
        if (
            abs(magnitude(self.tangent) - 1) > 1e-10
            or abs(magnitude(self.normal) - 1) > 1e-10
            or abs(dot(self.tangent, self.normal)) > 1e-10
        ):
            raise ValueError("Reference arc axes must be orthonormal.")

    def jet(self, u: float) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate the exact circular reference without numerical fitting.
        """
        _fraction(u)
        angle = self.angle * u
        r, a = self.radius_mm, self.angle
        p = self.start.translated(self.tangent, r * math.sin(angle)).translated(
            self.normal, r * (1 - math.cos(angle))
        )
        zero = Vector3(0, 0, 0)
        velocity = zero.translated(self.tangent, r * a * math.cos(angle)).translated(
            self.normal, r * a * math.sin(angle)
        )
        acceleration = zero.translated(self.tangent, -r * a * a * math.sin(angle)).translated(
            self.normal, r * a * a * math.cos(angle)
        )
        return p, velocity, acceleration

    def width(self, _u: float) -> Vector3:
        """
        Keep the reference profile's width along the fixed circle binormal.
        """
        return unit(cross(self.tangent, self.normal))


@dataclass(frozen=True)
class Helix:
    """
    Author a spatial center curve with a perpendicular, undeformed normal profile.
    """

    radius_mm: float
    pitch_mm: float

    def __post_init__(self) -> None:
        """
        Require finite dimensions and a positive cylinder radius.
        """
        if (
            not math.isfinite(self.radius_mm)
            or self.radius_mm <= 0
            or not math.isfinite(self.pitch_mm)
        ):
            raise ValueError("A reference helix needs finite dimensions and positive radius.")

    def jet(self, u: float) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate one radian of a geometric helix and its exact derivatives.
        """
        _fraction(u)
        return (
            Vector3(self.radius_mm * math.cos(u), self.radius_mm * math.sin(u), self.pitch_mm * u),
            Vector3(-self.radius_mm * math.sin(u), self.radius_mm * math.cos(u), self.pitch_mm),
            Vector3(-self.radius_mm * math.cos(u), -self.radius_mm * math.sin(u), 0),
        )

    def width(self, u: float) -> Vector3:
        """
        Derive the geometric binormal independently of any ruled-strip slope.
        """
        _, v, a = self.jet(u)
        return unit(cross(v, a))


@dataclass(frozen=True)
class Straight:
    """
    Supply a zero-curvature control without inventing a Frenet normal.
    """

    @staticmethod
    def jet(u: float) -> tuple[Vector3, Vector3, Vector3]:
        """
        Evaluate a ten-millimeter straight reference with constant speed.
        """
        _fraction(u)
        return Vector3(10 * u, 0, 0), Vector3(10, 0, 0), Vector3(0, 0, 0)

    @staticmethod
    def width(_u: float) -> Vector3:
        """
        Preserve the explicit straight control's transverse profile axis.
        """
        return Vector3(0, 1, 0)


def compound_s(radius_mm: float) -> tuple[Arc, ...]:
    """
    Author a circular-conductor S reference followed by a ninety-degree lateral turn.

    This is a rule-calibration fixture, never a discovered endpoint route or a
    seed. The three G1 pieces count as one reference configuration. Circular
    profile orientation is immaterial at the plane change; this does not prove a
    noncircular ribbon frame, smooth curvature transitions or global clearance.
    """
    first = Arc(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0), radius_mm)
    second = Arc(first.jet(1)[0], Vector3(0, 1, 0), Vector3(1, 0, 0), radius_mm)
    third = Arc(second.jet(1)[0], Vector3(1, 0, 0), Vector3(0, 0, 1), radius_mm)
    return first, second, third
