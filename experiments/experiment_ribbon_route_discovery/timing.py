"""
Enforce solve-time comparisons against actual complete-candidate sweep construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ConstructionTiming:
    """
    Retain path/profile authoring and sweep-kernel time for every ordered conductor.

    Inputs must cover a completed candidate. Exclude solving,feasibility audits,
    graphics,captures and archive work. Failed or partial builds cannot provide a
    successful-construction benchmark. A control benchmark is provisional;each
    final candidate also needs its own matched timing comparison.
    """

    authoring_seconds: float
    kernel_seconds: float

    def __post_init__(self) -> None:
        """
        Refuse missing,nonfinite,negative or entirely zero construction measurements.
        """
        values = (self.authoring_seconds, self.kernel_seconds)
        if not all(math.isfinite(v) and v >= 0 for v in values) or sum(values) <= 0:
            raise ValueError("Completed sweep construction needs positive finite elapsed time.")

    @property
    def construction_seconds(self) -> float:
        """
        Return measured complete-candidate authoring plus kernel work.
        """
        return self.authoring_seconds + self.kernel_seconds

    @property
    def provisional_solve_ceiling(self) -> float:
        """
        Cap a new solve at measured construction time and the proposed five seconds.
        """
        return min(5.0, self.construction_seconds)

    def allows(self, solve_and_feasibility_seconds: float) -> bool:
        """
        Check the user's ratio against matched construction,including all solve work.
        """
        if not math.isfinite(solve_and_feasibility_seconds) or solve_and_feasibility_seconds < 0:
            raise ValueError("Solve and numerical feasibility time must be finite and nonnegative.")
        return solve_and_feasibility_seconds <= self.construction_seconds
