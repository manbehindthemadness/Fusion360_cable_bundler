"""
Keep endpoint closure affine while redistributing straight travel and fold radii.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_joint_route.allocation import Model as JointModel
from experiments.experiment_ribbon_joint_route.frames import Topology


def curvature_score(route: FoldRoute) -> float:
    """
    Return D times the exact integral of longitudinal lane curvature squared.

    A cylindrical material fold has lane curvature cos(bank)^2/R over material
    length R*abs(angle)/cos(bank). Flat leads contribute zero. Every material
    lane has the same integral; this is a geometric objective, not elastic energy.
    Curvature jumps at existing flat/arc joins remain part of the representation.
    """
    return math.fsum(
        abs(p.geometry.angle_radians)
        * math.cos(p.geometry.bank_radians) ** 3
        * route.targets.diameter_mm
        / p.geometry.radius_mm
        for p in route.pieces
        if isinstance(p.geometry, CylindricalFold)
    )


def peak_curvature(route: FoldRoute) -> float:
    """
    Return the maximum longitudinal material-lane curvature in inverse millimeters.
    """
    return max(
        (
            math.cos(p.geometry.bank_radians) ** 2 / p.geometry.radius_mm
            for p in route.pieces
            if isinstance(p.geometry, CylindricalFold)
        ),
        default=0.0,
    )


@dataclass(frozen=True)
class Model:
    """
    Retain fixed angles/banks/leads with all straight slots available for compensation.

    Radius floors preserve the declared physical construction bound and prevent
    increasing the original peak lane curvature. A formerly broad fold may tighten
    within those bounds to ease a sharper fold. Both ordered endpoint frames remain
    fixed; no guide attraction, new folds or post-build edits are involved.
    """

    affine: JointModel
    initial: tuple[float, ...]
    columns: tuple[tuple[float, float, float], ...]
    costs: tuple[float, ...]
    budget: float
    weights: tuple[float, ...]

    @classmethod
    def create(cls, source: FoldRoute, length_growth: float) -> Model:
        """
        Normalize variables by diameter and bound total material length explicitly.
        """
        if not math.isfinite(length_growth) or not 0 <= length_growth <= 0.1:
            raise ValueError("Declare a finite aesthetic length allowance between zero and10%.")
        folds = tuple(p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold))
        peak = peak_curvature(source)
        floors = tuple(
            replace(
                f,
                radius_mm=min(
                    f.radius_mm,
                    max(source.radius_mm, math.cos(f.bank_radians) ** 2 / peak),
                ),
            )
            for f in folds
        )
        affine = JointModel(source, Topology("aesthetic-fixed-folds", floors, 0))
        diameter = source.targets.diameter_mm
        values = [0.0] * affine.size
        index = 0
        for piece in source.pieces:
            if isinstance(piece.geometry, Straight):
                values[2 * index] += piece.geometry.material_length_mm / diameter
            else:
                values[2 * index + 1] = (
                    piece.geometry.radius_mm - floors[index].radius_mm
                ) / diameter
                index += 1
        costs = tuple(
            1.0
            if i % 2 == 0
            else abs(folds[i // 2].angle_radians) / math.cos(folds[i // 2].bank_radians)
            for i in range(affine.size)
        )
        base = math.fsum(f.material_length_mm for f in floors) / diameter
        budget = source.material_length_mm * (1 + length_growth) / diameter - base
        columns, _ = affine.equations()
        return cls(
            affine,
            tuple(values),
            columns,
            costs,
            budget,
            tuple(abs(f.angle_radians) * math.cos(f.bank_radians) ** 3 for f in folds),
        )

    def gradient(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Differentiate exact integrated curvature with respect to normalized radii.
        """
        diameter = self.affine.source.targets.diameter_mm
        return tuple(
            0.0
            if i % 2 == 0
            else -self.weights[i // 2]
            / (self.affine.topology.folds[i // 2].radius_mm / diameter + value) ** 2
            for i, value in enumerate(values)
        )

    def route(self, values: tuple[float, ...]) -> FoldRoute:
        """
        Recompose the same material primitives under the original ordered targets.
        """
        source = self.affine.source
        return FoldRoute(source.targets, self.affine.pieces(values), source.radius_mm)
