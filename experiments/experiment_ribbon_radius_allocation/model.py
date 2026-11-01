"""
Express fixed-angle material routes as affine functions of travel and radius growth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import difference
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece


@dataclass(frozen=True)
class Model:
    """
    Keep original radii as lower bounds and normalize all allocation lengths by D.
    """

    original: FoldRoute

    @property
    def initial(self) -> tuple[float, ...]:
        """
        Retain original straight travel and zero growth above each existing radius.
        """
        return tuple(
            p.geometry.material_length_mm / self.original.targets.diameter_mm
            if isinstance(p.geometry, Straight)
            else 0.0
            for p in self.original.pieces
        )

    @property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Identify coordinates whose contribution to explicit straight travel is one.
        """
        return tuple(
            i for i, p in enumerate(self.original.pieces) if isinstance(p.geometry, Straight)
        )

    @property
    def costs(self) -> tuple[float, ...]:
        """
        Return exact dimensionless material-length coefficients for each coordinate.
        """
        return tuple(
            1.0
            if isinstance(p.geometry, Straight)
            else abs(p.geometry.angle_radians) / math.cos(p.geometry.bank_radians)
            for p in self.original.pieces
        )

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Recompose the unchanged material folds with nonnegative travel/radius growth.

        Only explicit straights at numerical zero1e-10D are omitted. Banks,
        angles, flat leads, conductor order, width and thickness never change.
        """
        if len(values) != len(self.original.pieces) or any(
            not math.isfinite(value) or value < 0 for value in values
        ):
            raise ValueError("Supply nonnegative finite travel/growth for each original piece.")
        target = self.original.targets
        pose = Pose(target.start, target.start_tangent, target.start_width)
        result = []
        for original, value in zip(self.original.pieces, values):
            geometry: Piece
            if isinstance(original.geometry, Straight):
                if value <= 1e-10:
                    continue
                geometry = Straight(value * target.diameter_mm)
            else:
                geometry = replace(
                    original.geometry,
                    radius_mm=original.geometry.radius_mm + value * target.diameter_mm,
                )
            if (
                isinstance(geometry, Straight)
                and result
                and isinstance(result[-1].geometry, Straight)
            ):
                previous = result.pop()
                pose = previous.pose
                geometry = Straight(
                    previous.geometry.material_length_mm + geometry.material_length_mm
                )
            piece = PlacedPiece(pose, geometry, f"Radius allocation piece {len(result) + 1}")
            result.append(piece)
            pose = piece.end_pose()
        return tuple(result)

    def endpoint(self, values: tuple[float, ...]) -> Pose:
        """
        Evaluate terminal pose even when a straight-only zero allocation is empty.
        """
        pieces = self.pieces(values)
        target = self.original.targets
        return (
            pieces[-1].end_pose()
            if pieces
            else Pose(target.start, target.start_tangent, target.start_width)
        )

    def route(self, values: tuple[float, ...]) -> FoldRoute | None:
        """
        Retain fixed target poses and the original radius lower-bound provenance.
        """
        pieces = self.pieces(values)
        return FoldRoute(self.original.targets, pieces, self.original.radius_mm) if pieces else None

    def equations(
        self,
    ) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float], float]:
        """
        Derive affine position columns and the material budget from the fixed frame.

        Fold orientation is independent of radius. Evaluating one D of growth or
        straight travel therefore gives its affine coefficient, not a local fit.
        Final candidate closure is checked independently after recomposition.
        """
        zero = (0.0,) * len(self.original.pieces)
        origin = self.endpoint(zero).origin
        columns = []
        for index in range(len(zero)):
            values = list(zero)
            values[index] = 1.0
            shift = difference(self.endpoint(tuple(values)).origin, origin)
            columns.append(
                tuple(getattr(shift, a) / self.original.targets.diameter_mm for a in "xyz")
            )
        delta = difference(self.original.targets.end, origin)
        right = tuple(getattr(delta, a) / self.original.targets.diameter_mm for a in "xyz")
        budget = math.fsum(self.initial[i] for i in self.straight_indices)
        return tuple(columns), right, budget

    def straight_length(self, values: tuple[float, ...]) -> float:
        """
        Return explicit straight travel in millimeters, excluding fixed fold leads.
        """
        return (
            math.fsum(values[i] for i in self.straight_indices) * self.original.targets.diameter_mm
        )
