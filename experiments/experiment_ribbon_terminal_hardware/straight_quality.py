"""
Keep straight-feature recovery inside the original construction length and unused joint work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StraightQuality:
    """
    Activate the original length ceiling during endpoint and feature-gap closure.

    A small existing shortening margin places the equality inside the quality
    ceiling instead of relying on rounded equality at acceptance. It grants no
    physical tolerance and cannot enlarge the caller's remaining update allowance.
    """

    ceiling_mm: float
    remaining_updates: int

    def __post_init__(self) -> None:
        """
        Require a finite positive quality bound and at most four unused updates.
        """
        if (
            type(self.ceiling_mm) not in (int, float)
            or not math.isfinite(self.ceiling_mm)
            or self.ceiling_mm <= 0
            or type(self.remaining_updates) is not int
            or not 1 <= self.remaining_updates <= 4
        ):
            raise ValueError("Use the original positive ceiling and one to four remaining updates")

    @property
    def target_mm(self) -> float:
        """
        Retain the established quality margin, scaled down for very small layouts.
        """
        return self.ceiling_mm - min(1e-7, self.ceiling_mm * 1e-8)

    @property
    def newton_steps(self) -> int:
        """
        Allocate six corrections per genuinely unused original update.
        """
        return 6 * self.remaining_updates
