"""
Integrate ribbon frames whose angular velocity cannot create edgewise bending.

Each axis lies in the local tangent/width plane. A nonzero tangent component
couples rotation to the spatial bend. Quintic angle easing gives zero curvature
and frame rate at joins. This is a kinematic primitive, not elastic equilibrium.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

ZERO = Vector3(0, 0, 0)
_NODES = (0.1834346424956498, 0.5255324099163290, 0.7966664774136267, 0.9602898564975363)
_WEIGHTS = (0.3626837833783620, 0.3137066458778873, 0.2223810344533745, 0.1012285362903763)


class AngleLaw(Enum):
    """
    Distinguish eased helical motion from exact constant-curvature controls.
    """

    EASED = "quintic-angle"
    LINEAR = "constant-rate"


def rotate(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
    """
    Apply Rodrigues rotation about a unit axis without changing vector length.
    """
    cosine = math.cos(angle)
    return (
        ZERO.translated(vector, cosine)
        .translated(cross(axis, vector), math.sin(angle))
        .translated(axis, dot(axis, vector) * (1 - cosine))
    )


@dataclass(frozen=True)
class CoupledMotion:
    """
    Retain one positive-length center/frame motion, with dimensions in millimeters.

    Center positions use fixed 8-panel, 8-node Gauss quadrature for eased angles;
    this numerical integration is neither a continuous certificate nor a search.
    Linear-angle circles and straight motions have analytic position integrals.
    """

    start: Vector3
    tangent: Vector3
    width: Vector3
    axis: Vector3
    angle: float
    length: float
    law: AngleLaw = AngleLaw.EASED

    def __post_init__(self) -> None:
        """
        Reject malformed frames, reverse travel and a forbidden angular component.
        """
        vectors = (self.start, self.tangent, self.width, self.axis)
        if any(not math.isfinite(v) for p in vectors for v in (p.x, p.y, p.z)):
            raise ValueError("Motion vectors must be finite.")
        if not math.isfinite(self.length) or self.length <= 0 or not math.isfinite(self.angle):
            raise ValueError("Motion needs finite positive length and finite angle.")
        if any(abs(magnitude(p) - 1) > 1e-8 for p in vectors[1:]):
            raise ValueError("Motion axes must be unit vectors.")
        if abs(dot(self.tangent, self.width)) > 1e-8:
            raise ValueError("Motion tangent and width must be perpendicular.")
        if abs(dot(self.axis, cross(self.tangent, self.width))) > 1e-8:
            raise ValueError("Angular axis would introduce forbidden width-axis bending.")
        if not isinstance(self.law, AngleLaw):
            raise ValueError("An explicit angle law is required.")

    def angle_jet(self, u: float) -> tuple[float, float, float]:
        """
        Return angle and its first two parameter derivatives on the closed interval.
        """
        if not math.isfinite(u) or not 0 <= u <= 1:
            raise ValueError("Motion fraction must lie in [0,1].")
        if self.law is AngleLaw.LINEAR:
            return self.angle * u, self.angle, 0.0
        return (
            self.angle * u**3 * (10 - 15 * u + 6 * u * u),
            self.angle * 30 * u * u * (1 - u) ** 2,
            self.angle * 60 * u * (1 - u) * (1 - 2 * u),
        )

    def frame(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Rotate tangent and ordered width together, preserving their orthogonality.
        """
        angle, _, _ = self.angle_jet(u)
        return rotate(self.tangent, self.axis, angle), rotate(self.width, self.axis, angle)

    def displacement(self, u: float) -> Vector3:
        """
        Integrate positive forward travel with a fixed amount of quadrature work.
        """
        self.angle_jet(u)
        if self.angle == 0:
            return ZERO.translated(self.tangent, self.length * u)
        parallel = ZERO.translated(self.axis, dot(self.axis, self.tangent))
        transverse = difference(self.tangent, parallel)
        turning = cross(self.axis, self.tangent)
        if self.law is AngleLaw.LINEAR:
            sine_integral = 2 * math.sin(self.angle * u / 2) ** 2 / self.angle
            cosine_integral = math.sin(self.angle * u) / self.angle
        else:
            cosine_integral = sine_integral = 0.0
            half = u / 16
            for panel in range(8):
                middle = (2 * panel + 1) * half
                for node, weight in zip(_NODES, _WEIGHTS):
                    for sign in (-1, 1):
                        angle, _, _ = self.angle_jet(middle + sign * half * node)
                        cosine_integral += half * weight * math.cos(angle)
                        sine_integral += half * weight * math.sin(angle)
        return (
            ZERO.translated(parallel, self.length * u)
            .translated(transverse, self.length * cosine_integral)
            .translated(turning, self.length * sine_integral)
        )

    def jet(self, u: float, offset: float = 0) -> tuple[Vector3, Vector3, Vector3]:
        """
        Return position, velocity and acceleration of a center or ordered lane.
        """
        _, rate, acceleration = self.angle_jet(u)
        tangent, width = self.frame(u)
        width_rate = ZERO.translated(cross(self.axis, width), rate)
        width_acceleration = ZERO.translated(cross(self.axis, width), acceleration).translated(
            cross(self.axis, cross(self.axis, width)), rate * rate
        )
        return (
            self.start.translated(self.displacement(u), 1).translated(width, offset),
            ZERO.translated(tangent, self.length).translated(width_rate, offset),
            ZERO.translated(cross(self.axis, tangent), self.length * rate).translated(
                width_acceleration, offset
            ),
        )

    def maximum_curvature(self) -> float:
        """
        Bound center curvature analytically for the selected angle law.
        """
        peak = 1.875 if self.law is AngleLaw.EASED else 1.0
        return peak * abs(self.angle) * magnitude(cross(self.axis, self.tangent)) / self.length


def orientation_angles(
    tangent: Vector3, width: Vector3, end_tangent: Vector3, end_width: Vector3
) -> tuple[float, float, float]:
    """
    Factor a relative frame rotation into three fixed oblique-axis rotations.

    Local axes A=(T+W)/sqrt(2), B=(T-W)/sqrt(2) are perpendicular. An A-B-A
    Euler factorization is closed-form; its axes always satisfy the no-wide-bend
    invariant. The selected branch is fixed, with no alternate-branch search.
    """
    a, b = unit(tangent.translated(width, 1)), unit(tangent.translated(width, -1))
    end_a = unit(end_tangent.translated(end_width, 1))
    end_b = unit(end_tangent.translated(end_width, -1))
    basis, target = (a, b, cross(a, b)), (end_a, end_b, cross(end_a, end_b))
    matrix = tuple(tuple(dot(p, q) for q in target) for p in basis)
    sine_beta = math.hypot(matrix[1][0], matrix[2][0])
    beta = math.atan2(sine_beta, matrix[0][0])
    if sine_beta <= 1e-10:
        return math.atan2(matrix[2][1], matrix[1][1]), beta, 0.0
    return math.atan2(matrix[1][0], -matrix[2][0]), beta, math.atan2(matrix[0][1], matrix[0][2])
