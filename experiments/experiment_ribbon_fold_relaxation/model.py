"""
Parameterize straight travel and signed fold angles with unchanged material creases.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import cross, difference
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import Piece


@dataclass(frozen=True)
class Model:
    """
    Normalize straight lengths by diameter; retain fold radii, banks, leads and order.
    """

    original: FoldRoute

    @property
    def initial(self) -> tuple[float, ...]:
        """
        Capture one coordinate per original straight or finite fold.
        """
        return tuple(
            p.geometry.material_length_mm / self.original.targets.diameter_mm
            if isinstance(p.geometry, Straight)
            else p.geometry.angle_radians
            for p in self.original.pieces
        )

    @property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Identify the coordinates directly driven by the contraction objective.
        """
        return tuple(
            i for i, p in enumerate(self.original.pieces) if isinstance(p.geometry, Straight)
        )

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Retain nonnegative straight travel and injective folds of at most a half-turn.
        """
        return (
            (0.0, math.inf)
            if isinstance(self.original.pieces[index].geometry, Straight)
            else (-math.pi, math.pi)
        )

    def pieces(self, values: tuple[float, ...]) -> tuple[PlacedPiece, ...]:
        """
        Recompose the same material primitives, omitting numerical zero pieces.

        A zero-angle fold becomes its unchanged flat lead length, not a new twist
        or radius. Adjacent straight pieces merge. Existing side order, width and
        thickness stay authoritative even if an angle crosses zero.
        """
        if len(values) != len(self.original.pieces):
            raise ValueError("Supply one coordinate per original material piece.")
        pose = Pose(
            self.original.targets.start,
            self.original.targets.start_tangent,
            self.original.targets.start_width,
        )
        output = []
        for index, (original, value) in enumerate(zip(self.original.pieces, values)):
            low, high = self.bounds(index)
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Relaxation coordinate outside declared bounds.")
            geometry: Piece
            if isinstance(original.geometry, Straight):
                length = value * self.original.targets.diameter_mm
                if length <= 1e-12:
                    continue
                geometry = Straight(length)
            elif abs(value) <= 1e-12:
                length = original.geometry.before_mm + original.geometry.after_mm
                if length <= 1e-12:
                    continue
                geometry = Straight(length)
            else:
                geometry = replace(original.geometry, angle_radians=value)
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
            placed = PlacedPiece(pose, geometry, f"Relaxed material piece {len(output) + 1}")
            output.append(placed)
            pose = placed.end_pose()
        return tuple(output)

    def route(self, values: tuple[float, ...]) -> FoldRoute | None:
        """
        Preserve fixed targets while constructing a nonempty parameterized route.
        """
        pieces = self.pieces(values)
        return FoldRoute(self.original.targets, pieces, self.original.radius_mm) if pieces else None

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Measure normalized position and local ordered-frame rotation residuals.

        The rotation residual is local and vanishes also at a half-turn; final
        acceptance separately measures actual ordered tangent/width vectors.
        """
        pieces = self.pieces(values)
        target = self.original.targets
        end = (
            pieces[-1].end_pose()
            if pieces
            else Pose(target.start, target.start_tangent, target.start_width)
        )
        displacement = difference(end.origin, target.end)
        rotation = (
            cross(end.tangent, target.end_tangent)
            .translated(cross(end.width, target.end_width), 1)
            .translated(
                cross(cross(end.tangent, end.width), cross(target.end_tangent, target.end_width)), 1
            )
        )
        return tuple(getattr(displacement, a) / target.diameter_mm for a in "xyz") + tuple(
            getattr(rotation, a) / 2 for a in "xyz"
        )

    def jacobian(self, values: tuple[float, ...]) -> list[list[float]]:
        """
        Differentiate six closure equations with bounded diameter-scaled differences.
        """
        columns = []
        for index, value in enumerate(values):
            low, high = self.bounds(index)
            before = min(1e-5, value - low)
            after = min(1e-5, high - value)
            first = list(values)
            last = list(values)
            first[index] -= before
            last[index] += after
            a, b = self.residual(tuple(first)), self.residual(tuple(last))
            columns.append(tuple((y - x) / (before + after) for x, y in zip(a, b)))
        return [[column[row] for column in columns] for row in range(6)]

    def straight_length(self, values: tuple[float, ...]) -> float:
        """
        Return the combined length of the original straight-run coordinates in mm.
        """
        return (
            math.fsum(values[i] for i in self.straight_indices) * self.original.targets.diameter_mm
        )
