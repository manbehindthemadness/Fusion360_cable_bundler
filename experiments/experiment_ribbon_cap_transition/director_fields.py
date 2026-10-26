"""
Freeze distinct forward-kinematic ribbon challenges before transport evaluation.

These prescribed fields author fixtures,not fixed-endpoint routing solutions.
Development,one-use validation and model/policy rejection controls stay separate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Coefficients = tuple[float, float, float, float]


@dataclass(frozen=True)
class DirectorField:
    """
    Specify signed bending and ruling direction over normalized material length.

    Coefficients multiply1,cos(2pi*u),sin(2pi*u),sin(4pi*u). Bending is divided
    by length to obtain curvature per millimeter. No material constants or energy
    minimization are implied. Terminal ruling slopes must be zero for normal caps.
    """

    name: str
    length_mm: float
    bending: Coefficients
    ruling: Coefficients
    lines: int = 19
    diameter_mm: float = 1.5

    def __post_init__(self) -> None:
        """
        Reject malformed fields before numerical integration or native authoring.
        """
        values = (*self.bending, *self.ruling, self.length_mm, self.diameter_mm)
        if (
            len(self.bending) != 4
            or len(self.ruling) != 4
            or not all(math.isfinite(v) for v in values)
        ):
            raise ValueError("Director fields need four finite coefficients per function.")
        if (
            self.length_mm <= 0
            or self.diameter_mm <= 0
            or isinstance(self.lines, bool)
            or not isinstance(self.lines, int)
            or self.lines < 1
        ):
            raise ValueError("Director field dimensions must be positive.")
        if abs(self.ruling[0] + self.ruling[1]) > 1e-12:
            raise ValueError("Normal terminal caps require zero terminal ruling slope.")

    @property
    def half_width_mm(self) -> float:
        """
        Preserve the existing ribbon outer-guide padding policy for comparison.
        """
        return self.lines * self.diameter_mm / 2 + self.diameter_mm * 0.1

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Return signed curvature,eta and eta's material-length derivative.
        """
        if not math.isfinite(u) or not 0 <= u <= 1:
            raise ValueError("Director sample fraction must lie within[0,1].")
        angle = 2 * math.pi * u
        basis = (1.0, math.cos(angle), math.sin(angle), math.sin(2 * angle))
        derivative = (0.0, -math.sin(angle), math.cos(angle), 2 * math.cos(2 * angle))
        curvature = sum(a * b for a, b in zip(self.bending, basis)) / self.length_mm
        eta = sum(a * b for a, b in zip(self.ruling, basis))
        eta_s = 2 * math.pi * sum(a * b for a, b in zip(self.ruling, derivative)) / self.length_mm
        return curvature, eta, eta_s


def development() -> tuple[DirectorField, ...]:
    """
    Register seven distinct behaviors inspired qualitatively by the physical photos.
    """
    z = (0.0, 0.0, 0.0, 0.0)
    return (
        DirectorField("D01_straight", 80, z, z),
        DirectorField("D02_gentle_arc", 90, (math.pi / 3, 0, 0, 0), z),
        DirectorField("D03_broad_return", 150, (math.pi, -math.pi, 0, 0), z),
        DirectorField("D04_planar_reversal", 120, (0, 0, math.pi, 0), z),
        DirectorField("D05_banked_turn", 150, (math.pi, -math.pi, 0, 0), (0.4, -0.4, 0, 0)),
        DirectorField("D06_spatial_reversal", 180, (0, 0, 1.5 * math.pi, 0), (0, 0, 0.7, 0)),
        DirectorField("D07_coupled_coil", 160, (2 * math.pi, 0, 0, 0), (0.4, -0.4, 0, 0)),
    )


def validation() -> tuple[DirectorField, ...]:
    """
    Reserve four mixed fields for one evaluation after the transport method freezes.

    Width changes accompany distinct fields/boundary poses;they are not counted
    as independent evidence for a width-only generalization claim.
    """
    return (
        DirectorField(
            "V01_mixed_spatial", 130, (1.3, -0.6, 1.2, -0.8), (0.15, -0.15, 0.35, 0.1), 17
        ),
        DirectorField(
            "V02_opposed_bend", 120, (-math.pi / 2, math.pi / 2, 0, 0), (0.4, -0.4, 0, 0), 25, 1
        ),
        DirectorField("V03_twisting_entry", 75, (math.pi / 2, 0, 0, 0), (0, 0, 0.7, 0), 13),
        DirectorField("V04_multiple_reversals", 110, (0, 0, 0, 4), (0, 0, 0.3, 0), 23, 1.2),
    )


def rejection_controls() -> tuple[DirectorField, ...]:
    """
    Keep a map-folding control separate from a current-radius-policy rejection.
    """
    return (
        DirectorField("I01_material_map_folding", 80, (1, 0, 0, 0), (0, 0, 2, 0)),
        DirectorField("I02_radius_policy_rejection", 30, (10, 0, 0, 0), (0, 0, 0, 0)),
    )
