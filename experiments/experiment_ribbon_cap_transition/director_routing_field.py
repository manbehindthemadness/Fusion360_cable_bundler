"""
Add one symmetric harmonic to the frozen director representation for target routing.

The old forward benchmark fields and transport implementation stay unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from .constraint_policy import ConstraintPolicy, current
from .director_fields import DirectorField


@dataclass(frozen=True)
class RoutingField(DirectorField):
    """
    Supply ten routing coordinates while retaining zero terminal ruling slopes.

    Five bending coefficients,four ruling coefficients and positive length are
    solver freedoms. The extra ruling basis cos(4pi*u)-1 vanishes at both caps.
    """

    extra_bending: float = 0.0
    extra_ruling: float = 0.0
    constraints: ConstraintPolicy = dataclass_field(default_factory=current, init=False)

    def __post_init__(self) -> None:
        """
        Apply the original field contract and reject nonfinite extra coefficients.
        """
        super().__post_init__()
        if not math.isfinite(self.extra_bending) or not math.isfinite(self.extra_ruling):
            raise ValueError("Routing harmonics must be finite.")

    def sample(self, u: float) -> tuple[float, float, float]:
        """
        Extend the analytical field and its ruling derivative without endpoint repair.
        """
        k, eta, eta_s = super().sample(u)
        angle = 4 * math.pi * u
        return (
            k + self.extra_bending * math.cos(angle) / self.length_mm,
            eta + self.extra_ruling * (math.cos(angle) - 1),
            eta_s - 4 * math.pi * self.extra_ruling * math.sin(angle) / self.length_mm,
        )
