"""
Derive one finite-box separation plane for a demonstrated straight material sheet intrusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate, regions
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight

from .check import Report
from .model import Hardware
from .reversal_model import ReversalModel


@dataclass(frozen=True)
class Sheet:
    """
    Bind a stable straight slot and the closest complete-material/finite-box separating plane.
    """

    model: ReversalModel
    region: Region
    axis: Vector3
    side: Side
    limit: float

    @classmethod
    def create(
        cls, model: ReversalModel, route: FoldRoute, report: Report, hardware: Hardware
    ) -> Sheet | None:
        """
        Select the largest signed gap among the15algebraic straight/box SAT directions.

        Only a demonstrated straight intrusion is supported. This derives one
        plane, not trial bend angles. Full later checks remain authoritative.
        """
        witness = report.witness
        if report.status != "blocked" or witness is None:
            return None
        piece = route.pieces[witness.piece]
        if not isinstance(piece.geometry, Straight):
            return None
        box = next(b for b in hardware.boxes if b.terminal.value == witness.terminal)
        local = (
            piece.pose.tangent,
            piece.pose.width,
            unit(cross(piece.pose.tangent, piece.pose.width)),
        )
        axes = (*box.axes, *local, *(cross(a, b) for a in box.axes for b in local))
        tag = regions(route)[witness.piece]
        choices: list[tuple[float, Sheet]] = []
        for raw in axes:
            if magnitude(raw) < 1e-10:
                continue
            axis = unit(raw)
            coordinates = tuple(dot(point, axis) for point in box.corners())
            for side, limit in ((Side.AFTER, max(coordinates)), (Side.BEFORE, min(coordinates))):
                constraint = cls(model, tag, axis, side, limit)
                choices.append((constraint._gap_piece(piece), constraint))
        return max(choices, key=lambda pair: pair[0])[1]

    def _gap_piece(self, piece: PlacedPiece) -> float:
        """
        Project full width/thickness, never just the witnessed center point.
        """
        source = self.model.original
        cell = Cell(
            0,
            Span(0, 1),
            Span(-source.half_width_mm, source.half_width_mm),
            Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
        )
        bound = projection(piece, cell, self.axis)
        return bound.low - self.limit if self.side is Side.AFTER else self.limit - bound.high

    def gap(self, values: tuple[float, ...]) -> float:
        """
        Measure the same complete material slot through joint motion, normalized by layout length.
        """
        piece = locate(self.model.original, self.model.pieces(values), self.region)
        return self._gap_piece(piece) / self.model.scale

    def gradient(self, values: tuple[float, ...], checkpoint: Callable[[], None]) -> list[float]:
        """
        Differentiate the analytic plane gap with probes inside the fixed joint bounds.
        """
        gradient = []
        for index, value in enumerate(values):
            checkpoint()
            low, high = self.model.bounds(index)
            a, b = list(values), list(values)
            a[index], b[index] = max(low, value - 1e-5), min(high, value + 1e-5)
            gradient.append((self.gap(tuple(b)) - self.gap(tuple(a))) / (b[index] - a[index]))
        return gradient
