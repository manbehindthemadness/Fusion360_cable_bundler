"""
Define the local positive-thickness Jacobian limit independently of routing search.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class BendModel(Enum):
    """
    Keep historical references distinct from the user-defined geometric pinch rule.
    """

    LEGACY = "legacy"
    PINCH = "pinch percent"


@dataclass(frozen=True)
class PinchLimit:
    """
    Specify utilization below the zero-inside-radius threshold, in percent.

    For a circular tube, utilization is curvature times half-thickness. For the
    developable material strip it is thickness times maximum principal curvature
    divided by two. This local regularity condition is not a global contact audit.
    """

    percent: float = 99.6

    def __post_init__(self) -> None:
        """
        Refuse a pinched/singular 100-percent boundary or malformed percentage.
        """
        if (
            isinstance(self.percent, bool)
            or not isinstance(self.percent, (float, int))
            or not math.isfinite(self.percent)
            or not 0 < self.percent < 100
        ):
            raise ValueError(
                "Pinch utilization must be finite and strictly between 0 and 100 percent."
            )

    @property
    def fraction(self) -> float:
        """
        Return the dimensionless permitted fraction of the geometric pinch limit.
        """
        return self.percent / 100

    def turn_bound(
        self, minimum_progress: float, eta: float, diameter_mm: float, lines: int
    ) -> float:
        """
        Bound tangent turning for a circular tube or a full-width material strip.

        A strip's normal-offset Jacobian is s(q)-v*b*(1+eta^2), with lane
        progress s(q), tangent turn b and thickness coordinate v. Its minimum
        over width and +/-D/2 thickness supplies the shared bound for all guides.
        A circular section is perpendicular to its tangent and has no eta factor.
        """
        if (
            not all(math.isfinite(value) for value in (minimum_progress, eta, diameter_mm))
            or minimum_progress <= 0
            or diameter_mm <= 0
            or lines < 1
        ):
            raise ValueError("Pinch bounds require finite positive progress and thickness.")
        factor = 1.0 if lines == 1 else 1 + eta * eta
        return self.fraction * minimum_progress / (diameter_mm / 2 * factor)
