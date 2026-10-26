"""
Freeze diverse model-feasible endpoint witnesses outside the routing fit basis.

Witness fields author targets only;their coefficients and lengths never enter
the cold solver. They establish reachability in this kinematic model,not measured
physical equilibrium. Each family has two development and two reserved targets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, unit

from .coupled_motion import rotate
from .director_fields import DirectorField
from .director_transport import State


@dataclass(frozen=True)
class BreadthField(DirectorField):
    """
    Add third-harmonic bending and ruling terms absent from the solver basis.
    """

    third_bending: float = 0.0
    third_ruling: float = 0.0

    def __post_init__(self) -> None:
        """
        Retain base field validation and reject nonfinite extra coefficients.
        """
        super().__post_init__()
        if not all(math.isfinite(v) for v in (self.third_bending, self.third_ruling)):
            raise ValueError("Breadth harmonics must be finite.")

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Evaluate the witness and exact ruling derivative with normal terminal caps.
        """
        k, eta, eta_s = super().sample(u)
        angle = 6 * math.pi * u
        return (
            k + self.third_bending * math.sin(angle) / self.length_mm,
            eta + self.third_ruling * (math.cos(angle) - 1),
            eta_s - 6 * math.pi * self.third_ruling * math.sin(angle) / self.length_mm,
        )


@dataclass(frozen=True)
class BreadthSpec:
    """
    Pair one distinct intrinsic field with a frozen noncanonical initial pose.
    """

    field: BreadthField
    family: str
    phase: str
    axis: Vector3
    angle: float
    origin: Vector3

    def initial_pose(self) -> State:
        """
        Rotate the initial material axes rigidly without repairing generated targets.
        """
        axis = unit(self.axis)
        t = rotate(Vector3(1, 0, 0), axis, self.angle)
        w = rotate(Vector3(0, 1, 0), axis, self.angle)
        return self.origin.x, self.origin.y, self.origin.z, t.x, t.y, t.z, w.x, w.y, w.z


def registered() -> tuple[BreadthSpec, ...]:
    """
    Freeze24different fields/poses with7..40conductors and0.6..2mm diameters.

    Variants0/1are development,2/3reserved. Variants1..3carry higher harmonics;
    no pure rigid or scale copies count toward independent-case coverage.
    """
    families = ("banked_arc", "return", "reversal", "coil", "entry", "multi_reversal")
    dimensions = (
        (7, 0.6),
        (9, 0.9),
        (13, 1.0),
        (17, 1.25),
        (23, 1.4),
        (31, 0.8),
        (40, 0.7),
        (11, 2.0),
    )
    ratios = (2.7, 4.6, 3.8, 4.8, 3.1, 4.0)
    result = []
    for family_index, family in enumerate(families):
        for variant in range(4):
            sign = (-1.0) ** variant
            angle = math.pi * (0.9 + 0.04 * variant)
            bending = (
                (1.2 + 0.14 * variant, 0.0, 0.15 * sign, 0.08 * variant),
                (angle, -angle, 0.12 * sign, 0.05 * variant),
                (0.0, 0.15 * sign, 3.1 + 0.12 * variant, 0.12 * sign),
                (2 * math.pi * (0.95 + 0.02 * variant), 0.1 * sign, 0.18 * sign, 0.0),
                (1.5 + 0.1 * variant, -0.25, 0.45 * sign, -0.2 * sign),
                (0.3 * sign, -0.3 * sign, 0.25, 2.6 + 0.1 * variant),
            )[family_index]
            a = 0.02 if family_index in (2, 5) else 0.1 + 0.03 * variant
            b = (0.3 + 0.03 * variant) * sign if family_index in (2, 5) else 0.12 * sign
            lines, diameter = dimensions[(family_index * 3 + variant) % len(dimensions)]
            field = BreadthField(
                f"B{family_index * 4 + variant + 1:02}_{family}_{variant}",
                lines * diameter * ratios[family_index],
                bending,
                (a, -a, b, 0.04 * sign),
                lines,
                diameter,
                sign * (0.04 + 0.08 * variant) if variant else 0.0,
                sign * (0.005 + 0.01 * variant) if variant else 0.0,
            )
            result.append(
                BreadthSpec(
                    field,
                    family,
                    "development" if variant < 2 else "validation",
                    Vector3(1 + family_index, 1 + variant, 2),
                    0.23 * (1 + family_index + variant),
                    Vector3(-12 * family_index, 9 * variant, 4 * family_index - 3 * variant),
                )
            )
    return tuple(result)
