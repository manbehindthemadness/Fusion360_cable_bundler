"""
Reflect one measured incident fold sign while keeping its angle and bank free for cap closure.
"""

from __future__ import annotations

import math
from functools import cached_property

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints


class IncidentJoints(SignedJoints):
    """
    Preserve radii and all other signs while jointly reclosing one reflected incident bend.
    """

    selected: int

    def __init__(self, original: FoldRoute, selected: int) -> None:
        """
        Require one existing evidence-derived fold, without trying alternative sign candidates.
        """
        super().__init__(original)
        if type(selected) is not int or not 0 <= selected < len(self.folds):
            raise ValueError("Select one existing incident fold")
        object.__setattr__(self, "selected", selected)

    @cached_property
    def initial(self) -> tuple[float, ...]:
        """
        Negate only the selected original angle, retaining its initial magnitude and bank.
        """
        values = list(super().initial)
        for index, full in enumerate(self.indices):
            if full % 4 == 1 and full // 4 == self.selected:
                values[index] *= -1
        return tuple(values)

    def preserves(self, route: FoldRoute) -> bool:
        """
        Check ordered radii/profile widths and exactly the one prescribed sign change.
        """
        folds = tuple(p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold))
        return len(folds) == len(self.folds) and all(
            a.radius_mm == b.radius_mm
            and a.width_mm == b.width_mm
            and math.copysign(1, a.angle_radians)
            == math.copysign(1, b.angle_radians) * (-1 if i == self.selected else 1)
            for i, (a, b) in enumerate(zip(folds, self.folds))
        )
