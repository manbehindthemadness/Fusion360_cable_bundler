"""
Apply the established aesthetic curvature objective to shared flexible material geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute


def surface_score(route: FoldRoute, reference_length_mm: float) -> float:
    """
    Measure full-cylinder curvature with one fixed comparison length across fold merges.
    """
    return reference_length_mm * math.fsum(
        abs(p.geometry.angle_radians) / (p.geometry.radius_mm * math.cos(p.geometry.bank_radians))
        for p in route.pieces
        if isinstance(p.geometry, CylindricalFold)
    )


@dataclass(frozen=True)
class Model(FlexibleModel):
    """
    Retain the aesthetic pass's original signed-angle and radius restrictions.
    """

    label_prefix: ClassVar[str] = "Layout-relaxed material piece"

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Preserve fold sign/order, regular bank angles and the original minimum radius.
        """
        kind = index % 4
        if kind == 0:
            return 0.0, math.inf
        if kind == 1:
            return (
                (1e-6, math.pi) if self.folds[index // 4].angle_radians > 0 else (-math.pi, -1e-6)
            )
        if kind == 2:
            return -math.pi / 2 + 1e-3, math.pi / 2 - 1e-3
        minimum = max(self.original.radius_mm, min(f.radius_mm for f in self.folds))
        return minimum / self.scale, math.inf

    @staticmethod
    def score(values: tuple[float, ...]) -> float:
        """
        Measure layout-normalized integral of cylindrical material-surface curvature squared.

        Unlike the earlier lane-only score, the full cylinder curvature1/R does
        not underweight a visibly sharp diagonal crease when its lane bank is high.
        This is geometric fairness, not a physical elastic-energy model.
        """
        return math.fsum(
            abs(values[i + 1]) / (values[i + 3] * math.cos(values[i + 2]))
            for i in range(0, len(values) - 1, 4)
        )

    @staticmethod
    def gradient(values: tuple[float, ...]) -> list[float]:
        """
        Differentiate full-fold curvature with respect to layout-normalized coordinates.
        """
        gradient = [0.0] * len(values)
        for i in range(0, len(values) - 1, 4):
            angle, bank, radius = values[i + 1 : i + 4]
            score = abs(angle) / (radius * math.cos(bank))
            gradient[i + 1] = math.copysign(1, angle) / (radius * math.cos(bank))
            gradient[i + 2] = score * math.tan(bank)
            gradient[i + 3] = -score / radius
        return gradient
