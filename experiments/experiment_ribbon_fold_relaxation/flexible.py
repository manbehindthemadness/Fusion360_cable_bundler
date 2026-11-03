"""
Share flexible material geometry across distinct routing and aesthetic objectives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation.model import Model as ClosureModel
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece


@dataclass(frozen=True)
class FlexibleModel(ClosureModel):
    """
    Relax signed angles, crease banks, radii and all straight slots with fixed targets.

    Linear coordinates use the complete initial material length, not conductor
    diameter. Diameter still governs the physical radius floor. No straight run is
    reserved: it can disappear or redistribute to accommodate broader folds.
    """

    label_prefix: ClassVar[str] = "Joint optimized material piece"

    @cached_property
    def scale(self) -> float:
        """
        Use immutable initial material length as the covariant layout scale.
        """
        return self.original.material_length_mm

    @cached_property
    def folds(self) -> tuple[CylindricalFold, ...]:
        """
        Retain the original ordered folds independently of omitted straight slots.
        """
        return tuple(
            p.geometry for p in self.original.pieces if isinstance(p.geometry, CylindricalFold)
        )

    @cached_property
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

    @cached_property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Identify all runway slots, including those initially absent at zero length.
        """
        return tuple(range(0, len(self.initial), 4))

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Free angle signs while preserving regular banks and the declared physical radius floor.
        """
        kind = index % 4
        if kind == 0:
            return 0.0, math.inf
        if kind == 1:
            return -math.pi, math.pi
        if kind == 2:
            return -math.pi / 2 + 1e-3, math.pi / 2 - 1e-3
        return self.original.radius_mm / self.scale, math.inf

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Recompose isometric folds with bank-dependent flat caps and fixed extra runway.

        A zero-angle fold becomes its flat leads; adjacent flats merge. The
        necessary staggered flat leads change with the bank angle. Their
        original extra margins are retained; this is part of the mathematical
        candidate, never a native geometry repair or independently fitted lane.
        """
        if len(values) != 4 * len(self.folds) + 1:
            raise ValueError("Supply four coordinates per fold and one final runway slot")
        if any(
            not math.isfinite(v) or not self.bounds(i)[0] <= v <= self.bounds(i)[1]
            for i, v in enumerate(values)
        ):
            raise ValueError("Flexible material coordinate outside its declared bounds")
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
                before = lead + max(0.0, original.before_mm - old_lead)
                after = lead + max(0.0, original.after_mm - old_lead)
                if angle == 0.0:
                    if before + after > 1e-12:
                        geometries.append(Straight(before + after))
                else:
                    geometries.append(
                        CylindricalFold(
                            self._radius_mm(index, radius),
                            angle,
                            bank,
                            original.width_mm,
                            before,
                            after,
                        )
                    )
            for geometry in geometries:
                if (
                    isinstance(geometry, Straight)
                    and output
                    and isinstance(output[-1].geometry, Straight)
                ):
                    previous = output.pop()
                    pose = previous.pose
                    geometry = Straight(
                        previous.geometry.material_length_mm + geometry.material_length_mm
                    )
                placed = PlacedPiece(pose, geometry, f"{self.label_prefix}{len(output) + 1}")
                output.append(placed)
                pose = placed.end_pose()
        return tuple(output)

    def _radius_mm(self, fold_index: int, coordinate: float) -> float:
        """
        Preserve exact physical anchors when undoing normalized radius coordinates.

        An unchanged coordinate denotes its original radius, and an active lower
        bound denotes the declared physical minimum. Dividing and multiplying
        either anchor can otherwise move it one floating-point step below its
        bound. Other coordinates retain ordinary scaling; input bounds stay strict.
        """
        source = self.folds[fold_index].radius_mm
        minimum = self.original.radius_mm
        if coordinate == source / self.scale and source >= minimum:
            return source
        if coordinate == minimum / self.scale:
            return minimum
        return coordinate * self.scale

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Reuse complete ordered-frame closure while normalizing position by layout length.
        """
        original = super().residual(values)
        ratio = self.original.targets.diameter_mm / self.scale
        return tuple(v * ratio for v in original[:3]) + original[3:]

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
            gradient[i + 1] = math.copysign(1, angle) * radius / cosine if angle else 0.0
            gradient[i + 2] = radius * abs(angle) * math.tan(bank) / cosine
            if bank:
                gradient[i + 2] += (
                    self.folds[i // 4].width_mm / self.scale * math.copysign(1, bank) / cosine**2
                )
            gradient[i + 3] = abs(angle) / cosine
        return gradient
