"""
Keep measured finite-hardware feature constraints active while all bend directions remain fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side, locate, regions
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight

from .check import Report
from .model import Box, Hardware
from .reversal_model import ordered_residual


class SignedJoints(MovableBends):
    """
    Move existing angles/banks/runways while preserving every fold sign and radius.
    """

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep all original turn directions alongside the shared bank and runway bounds.
        """
        low, high = super().bounds(index)
        if self.indices[index] % 4 == 1:
            if self.initial[index] > 0:
                low = 0.0
            else:
                high = 0.0
        return low, high

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Check complete ordered frames, including half-turn mismatches.
        """
        return ordered_residual(self, values)

    def preserves(self, route: FoldRoute) -> bool:
        """
        Require original ordered fold count, signs, radii and joined-profile width.
        """
        folds = tuple(p.geometry for p in route.pieces if isinstance(p.geometry, CylindricalFold))
        return len(folds) == len(self.folds) and all(
            a.radius_mm == b.radius_mm
            and a.width_mm == b.width_mm
            and math.copysign(1, a.angle_radians) == math.copysign(1, b.angle_radians)
            for a, b in zip(folds, self.folds)
        )


@dataclass(frozen=True)
class FeaturePlane:
    """
    Follow one selected SAT axis family and bound the complete witnessed bend/runway feature.
    """

    model: SignedJoints
    reference: Region
    members: tuple[Region, ...]
    box: Box
    family: int
    side: Side

    @cached_property
    def corners(self) -> tuple[Vector3, ...]:
        """
        Retain the exact eight fixed hardware corners for every derivative probe.
        """
        return self.box.corners()

    def _axes(self, piece: PlacedPiece) -> tuple[Vector3, ...]:
        """
        Recompute the same 15 algebraic frame directions as the reference feature moves.
        """
        local = (
            piece.pose.tangent,
            piece.pose.width,
            unit(cross(piece.pose.tangent, piece.pose.width)),
        )
        return self.box.axes + local + tuple(cross(a, b) for a in self.box.axes for b in local)

    def _span(self, pieces: tuple[PlacedPiece, ...], axis: Vector3) -> Span:
        """
        Enclose every occupied width/thickness coordinate of all actual grouped material regions.
        """
        source = self.model.original
        cell = Cell(
            0,
            Span(0, 1),
            Span(-source.half_width_mm, source.half_width_mm),
            Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
        )
        spans = tuple(
            projection(locate(source, pieces, member), cell, axis) for member in self.members
        )
        return Span(min(s.low for s in spans), max(s.high for s in spans))

    @classmethod
    def create(
        cls,
        model: SignedJoints,
        route: FoldRoute,
        report: Report,
        hardware: Hardware,
        values: tuple[float, ...],
    ) -> FeaturePlane | None:
        """
        Derive one moving plane from demonstrated intrusion, retaining actual adjacent feature material.

        A fold includes an existing terminalward runway, not an absent synthetic
        slab. A straight includes its neighboring fold away from that terminal.
        The mating fold remains separate. No axis family or event is searched later.
        """
        witness = report.witness
        if report.status != "blocked" or witness is None:
            return None
        if route.targets != model.original.targets or route.targets != hardware.targets:
            raise ValueError("Feature constraints require the same fixed targets")
        tags = regions(route)
        piece = route.pieces[witness.piece]
        reference = tags[witness.piece]
        members = [reference]
        if isinstance(piece.geometry, Straight):
            folds = tuple(
                i for i, p in enumerate(route.pieces) if isinstance(p.geometry, CylindricalFold)
            )
            neighbor = (
                next((i for i in reversed(folds) if i < witness.piece), None)
                if witness.terminal == "end"
                else next((i for i in folds if i > witness.piece), None)
            )
            if neighbor is not None:
                members.append(tags[neighbor])
        else:
            neighbor = witness.piece + 1 if witness.terminal == "end" else witness.piece - 1
            if 0 <= neighbor < len(route.pieces) and isinstance(
                route.pieces[neighbor].geometry, Straight
            ):
                members.append(tags[neighbor])
        box = next(b for b in hardware.boxes if b.terminal.value == witness.terminal)
        prototype = cls(model, reference, tuple(members), box, 0, Side.BEFORE)
        choices: list[tuple[float, FeaturePlane]] = []
        pieces = model.pieces(values)
        for family, raw in enumerate(prototype._axes(piece)):
            if magnitude(raw) < 1e-10:
                continue
            axis = unit(raw)
            span = prototype._span(pieces, axis)
            coordinates = tuple(dot(p, axis) for p in prototype.corners)
            for side, gap in (
                (Side.AFTER, span.low - max(coordinates)),
                (Side.BEFORE, min(coordinates) - span.high),
            ):
                constraint = cls(model, reference, tuple(members), box, family, side)
                choices.append((gap, constraint))
        return max(choices, key=lambda item: item[0])[1]

    @cached_property
    def _gaps(self) -> Callable[[tuple[float, ...]], float]:
        """
        Own at most 64 gap evaluations without retaining other feature constraints.
        """
        return lru_cache(maxsize=64)(self._gap)

    def gap(self, values: tuple[float, ...]) -> float:
        """
        Reuse one immutable normalized feature-gap measurement.
        """
        return self._gaps(values)

    def _gap(self, values: tuple[float, ...]) -> float:
        """
        Follow the selected family and complete feature through joint motion, including derivatives.
        """
        pieces = self.model.pieces(values)
        piece = locate(self.model.original, pieces, self.reference)
        raw = self._axes(piece)[self.family]
        if magnitude(raw) < 1e-10:
            raise ValueError("Selected feature-plane axis family became degenerate")
        axis = unit(raw)
        bound = self._span(pieces, axis)
        coordinates = tuple(dot(p, axis) for p in self.corners)
        value = (
            bound.low - max(coordinates)
            if self.side is Side.AFTER
            else min(coordinates) - bound.high
        )
        return value / self.model.scale
