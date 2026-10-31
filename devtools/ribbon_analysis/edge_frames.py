"""
Derive the same material ruling kinematics for analytic boundary evaluators.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit


@dataclass(frozen=True)
class RulingKinematics:
    """
    Retain tangent, width, speed, curvature and ruling slope with its parameter rate.
    """

    tangent: Vector3
    width: Vector3
    speed: float
    curvature: float
    eta: float
    eta_u: float


def ruling_kinematics(
    velocity: Vector3, acceleration: Vector3, jerk: Vector3, snap: Vector3
) -> RulingKinematics:
    """
    Evaluate eta=torsion/curvature and its exact derivative for a regular boundary.

    Preserve the established1e-10speed/cross-product guards. Inflections require a
    separately supplied material frame; this function never invents one.
    """
    speed = magnitude(velocity)
    product = cross(velocity, acceleration)
    norm = magnitude(product)
    if speed <= 1e-10 or norm <= 1e-10:
        raise ValueError("Boundary has singular speed or bend frame.")
    eta = dot(product, jerk) * speed**3 / norm**3
    speed_log_rate = dot(velocity, acceleration) / (speed * speed)
    bend_log_rate = dot(product, cross(velocity, jerk)) / (norm * norm)
    relative_rate = 3 * (speed_log_rate - bend_log_rate)
    eta_u = dot(product, snap) * speed**3 / norm**3 + eta * relative_rate
    return RulingKinematics(unit(velocity), unit(product), speed, norm / speed**3, eta, eta_u)
