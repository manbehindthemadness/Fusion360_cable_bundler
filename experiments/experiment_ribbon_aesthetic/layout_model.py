"""
Parameterize aesthetic folds and available straight runway in layout-relative coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation.model import Model as ClosureModel
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece


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
class Model(ClosureModel):
    """
    Relax signed angles, crease banks, radii and all straight slots with fixed targets.

    Linear coordinates use the complete initial material length, not conductor
    diameter. Diameter still governs the physical radius floor. No straight run is
    reserved: it can disappear or redistribute to accommodate broader folds.
    """

    @property
    def scale(self) -> float:
        """
        Use immutable initial material length as the covariant layout scale.
        """
        return self.original.material_length_mm

    @property
    def folds(self) -> tuple[CylindricalFold, ...]:
        """
        Retain the original ordered folds independently of omitted straight slots.
        """
        return tuple(
            p.geometry for p in self.original.pieces if isinstance(p.geometry, CylindricalFold)
        )

    @property
    def initial(self) -> tuple[float, ...]:
        """
        Interleave straight runway, signed angle, bank and normalized radius per fold.
        """
        values = [0.0] * (4 * len(self.folds) + 1)
        index = 0
        for piece in self.original.pieces:
            if isinstance(piece.geometry, Straight):
                values[4 * index] += piece.geometry.material_length_mm / self.scale
            else:
                geometry = piece.geometry
                values[4 * index + 1 : 4 * index + 4] = (
                    geometry.angle_radians,
                    geometry.bank_radians,
                    geometry.radius_mm / self.scale,
                )
                index += 1
        return tuple(values)

    @property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Identify all runway slots, including those initially absent at zero length.
        """
        return tuple(range(0, len(self.initial), 4))

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

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Recompose isometric folds with bank-dependent flat caps and fixed extra runway.

        The necessary staggered flat leads change with the bank angle. Their
        original extra margins are retained; this is part of the mathematical
        candidate, never a native geometry repair or independently fitted lane.
        """
        if len(values) != 4 * len(self.folds) + 1:
            raise ValueError("Supply four coordinates per fold and one final runway slot")
        if any(
            not math.isfinite(v) or not self.bounds(i)[0] <= v <= self.bounds(i)[1]
            for i, v in enumerate(values)
        ):
            raise ValueError("Layout-relaxation coordinate outside its declared bounds")
        target = self.original.targets
        pose = Pose(target.start, target.start_tangent, target.start_width)
        output = []
        for index in range(len(self.folds) + 1):
            geometries: list[Piece] = []
            length = values[4 * index] * self.scale
            if length > 1e-12:
                geometries.append(Straight(length))
            if index < len(self.folds):
                original = self.folds[index]
                angle, bank, radius = values[4 * index + 1 : 4 * index + 4]
                old_lead = original.width_mm / 2 * abs(math.tan(original.bank_radians))
                lead = original.width_mm / 2 * abs(math.tan(bank))
                geometries.append(
                    CylindricalFold(
                        radius * self.scale,
                        angle,
                        bank,
                        original.width_mm,
                        lead + max(0.0, original.before_mm - old_lead),
                        lead + max(0.0, original.after_mm - old_lead),
                    )
                )
            for geometry in geometries:
                placed = PlacedPiece(
                    pose, geometry, f"Layout-relaxed material piece{len(output) + 1}"
                )
                output.append(placed)
                pose = placed.end_pose()
        return tuple(output)

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reuse complete ordered-frame closure while normalizing position by layout length.
        """
        original = super().residual(values)
        ratio = self.original.targets.diameter_mm / self.scale
        return tuple(v * ratio for v in original[:3]) + original[3:]

    def score(self, values: tuple[float, ...]) -> float:
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

    def gradient(self, values: tuple[float, ...]) -> list[float]:
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

    def length(self, values: tuple[float, ...]) -> float:
        """
        Return common material length normalized by the immutable initial layout length.
        """
        return math.fsum(p.geometry.material_length_mm for p in self.pieces(values)) / self.scale

    def length_gradient(self, values: tuple[float, ...]) -> list[float]:
        """
        Differentiate all straight, curved and required staggered-lead material lengths.
        """
        gradient = [1.0 if i % 4 == 0 else 0.0 for i in range(len(values))]
        for i in range(0, len(values) - 1, 4):
            angle, bank, radius = values[i + 1 : i + 4]
            cosine = math.cos(bank)
            gradient[i + 1] = math.copysign(1, angle) * radius / cosine
            gradient[i + 2] = radius * abs(angle) * math.tan(bank) / cosine
            if bank:
                gradient[i + 2] += (
                    self.folds[i // 4].width_mm / self.scale * math.copysign(1, bank) / cosine**2
                )
            gradient[i + 3] = abs(angle) / cosine
        return gradient
