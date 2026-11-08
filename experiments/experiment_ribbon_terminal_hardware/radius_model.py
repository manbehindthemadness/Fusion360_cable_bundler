"""
Restore finite terminal clearance by growing only the bend implicated by actual material evidence.
"""

from __future__ import annotations

import math
from functools import cached_property

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints


class RadiusJoints(SignedJoints):
    """
    Free one incident radius upward while preserving every ordered fold sign and all other radii.

    The route's material radius floor remains unchanged. A larger construction
    radius is a solver coordinate, not a relaxed material constraint or output repair.
    """

    selected: int

    def __init__(self, original: FoldRoute, selected: int) -> None:
        """
        Require one existing evidence-derived fold before exposing its radius coordinate.
        """
        super().__init__(original)
        if type(selected) is not int or not 0 <= selected < len(self.folds):
            raise ValueError("Select an existing incident fold")
        object.__setattr__(self, "selected", selected)

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Add only the selected radius to the existing angle, bank and runway coordinates.
        """
        return tuple(
            i for i in range(len(self.full.initial)) if i % 4 != 3 or i // 4 == self.selected
        )

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Retain existing bounds and prohibit shrinking the selected radius below its source value.
        """
        low, high = super().bounds(index)
        if self.indices[index] % 4 == 3:
            low = max(low, self.folds[self.selected].radius_mm / self.scale)
        return low, high

    def preserves(self, route: FoldRoute) -> bool:
        """
        Require original fold order, signs, profile widths and every immutable radius anchor.
        """
        folds = tuple(
            piece.geometry for piece in route.pieces if isinstance(piece.geometry, CylindricalFold)
        )
        return len(folds) == len(self.folds) and all(
            actual.width_mm == original.width_mm
            and math.copysign(1, actual.angle_radians) == math.copysign(1, original.angle_radians)
            and (
                actual.radius_mm >= original.radius_mm
                if index == self.selected
                else actual.radius_mm == original.radius_mm
            )
            for index, (actual, original) in enumerate(zip(folds, self.folds))
        )
