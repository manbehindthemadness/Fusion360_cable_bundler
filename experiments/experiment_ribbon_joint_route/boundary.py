"""
Describe fixed material-fold boundary inputs without inventing a provisional route.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from devtools.ribbon_analysis.contracts import Targets


class FoldBoundary(Protocol):
    """
    Supply immutable cap/profile dimensions and the declared physical radius floor.
    """

    @property
    def targets(self) -> Targets:
        """
        Return the complete ordered connection poses and dimensions.
        """
        ...

    @property
    def radius_mm(self) -> float:
        """
        Return the declared construction radius, independent of routing history.
        """
        ...

    @property
    def half_width_mm(self) -> float:
        """
        Return the unchanged joined-profile material half width.
        """
        ...


@dataclass(frozen=True)
class Boundary:
    """
    Freeze endpoint-only inputs for cold construction without a seeded or cached route.
    """

    targets: Targets
    radius_mm: float

    def __post_init__(self) -> None:
        """
        Reject malformed declared dimensions before constructing material geometry.
        """
        Targets.capture(self.targets)
        if (
            isinstance(self.radius_mm, bool)
            or not isinstance(self.radius_mm, (int, float))
            or not math.isfinite(self.radius_mm)
            or self.radius_mm <= 0
        ):
            raise ValueError("The construction radius must be finite and positive")

    @property
    def half_width_mm(self) -> float:
        """
        Preserve the established conductor width and outer-cap extension.
        """
        return self.targets.lines * self.targets.diameter_mm / 2 + self.targets.diameter_mm * 0.1
