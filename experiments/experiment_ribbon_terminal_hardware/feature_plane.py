"""
Keep measured finite-hardware feature constraints active while all bend directions remain fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
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


class FeatureCoverage(Enum):
    """
    Distinguish legacy terminalward material from complete occupied internal fold neighborhoods.
    """

    TERMINAL_RUNWAY = "terminal_runway"
    ADJOINING_INTERNAL = "adjoining_internal"


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

    def admissible(self, values: tuple[float, ...]) -> bool:
        """
        Keep constraint probes and trial steps inside their ordered material-region domain.

        Off-target cap poses are permitted while differentiating and solving.
        Vanished folds are not: their original region identities no longer exist.
        Specialized joint models retain their own explicit radius/sign policy.
        Invalid vector sizes, nonfinite coordinates and exact bound violations
        return False before placement. In particular, a rounded negative runway
        proposal is rejected, never snapped or allowed to abort the whole solve.
        """
        if len(values) != len(self.initial) or any(
            not math.isfinite(value) or not self.bounds(i)[0] <= value <= self.bounds(i)[1]
            for i, value in enumerate(values)
        ):
            return False
        route = self.route(values)
        return route is not None and self.preserves(route)


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

    def _selected_axis(self, piece: PlacedPiece) -> Vector3:
        """
        Evaluate the fixed selected family with identical arithmetic, omitting unused directions.
        """
        family = self.family
        if not 0 <= family < 15:
            return self._axes(piece)[family]
        if family < 3:
            return self.box.axes[family]
        index = family - 3 if family < 6 else (family - 6) % 3
        local = (
            piece.pose.tangent
            if index == 0
            else piece.pose.width
            if index == 1
            else unit(cross(piece.pose.tangent, piece.pose.width))
        )
        return local if family < 6 else cross(self.box.axes[(family - 6) // 3], local)

    @cached_property
    def _material_cell(self) -> Cell:
        """
        Retain the same immutable full-width/thickness material cell for this fixed source model.
        """
        source = self.model.original
        return Cell(
            0,
            Span(0, 1),
            Span(-source.half_width_mm, source.half_width_mm),
            Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
        )

    def _span(self, pieces: tuple[PlacedPiece, ...], axis: Vector3) -> Span:
        """
        Enclose every occupied width/thickness coordinate of all actual grouped material regions.
        """
        source = self.model.original
        cell = self._material_cell
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
        *,
        coverage: FeatureCoverage = FeatureCoverage.TERMINAL_RUNWAY,
    ) -> FeaturePlane | None:
        """
        Derive one moving plane from demonstrated intrusion, retaining actual adjacent feature material.

        A fold includes an existing terminalward runway, not an absent synthetic
        slab. A straight includes its neighboring fold away from that terminal.
        The mating fold remains separate. No axis family or event is searched later.
        Explicit complete coverage includes both currently occupied internal
        adjoining runways, excluding absent slots and mating terminal straights.
        An added own-mating straight never joins the corrective group: its fixed
        cap must touch the connector face. Actual witnessed material is retained,
        and final hardware certification still checks the entire route.
        """
        if not isinstance(coverage, FeatureCoverage):
            raise ValueError("Supply an explicit feature coverage policy")
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
        if coverage is FeatureCoverage.ADJOINING_INTERNAL:
            placed = model.route(values)
            if placed is None:
                return None
            occupied = regions(placed)
            for member in tuple(members):
                if not member.straight:
                    for adjacent in (Region(member.fold, True), Region(member.fold + 1, True)):
                        if (
                            0 < adjacent.fold < len(model.folds)
                            and adjacent in occupied
                            and adjacent not in members
                        ):
                            members.append(adjacent)
        box = next(b for b in hardware.boxes if b.terminal.value == witness.terminal)
        mating = Region(0 if witness.terminal == "start" else len(model.folds), True)
        members = [member for member in members if member != mating or member == reference]
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

    def _axis(self, pieces: tuple[PlacedPiece, ...]) -> Vector3:
        """
        Resolve the selected nondegenerate world axis through the same actual material feature.
        """
        piece = locate(self.model.original, pieces, self.reference)
        raw = self._selected_axis(piece)
        if magnitude(raw) < 1e-10:
            raise ValueError("Selected feature-plane axis family became degenerate")
        return unit(raw)

    def separation_direction(self, values: tuple[float, ...]) -> Vector3:
        """
        Return the unit rigid-translation direction that increases this complete feature's signed gap.
        """
        axis = self._axis(self.model.pieces(values))
        return axis if self.side is Side.AFTER else axis.translated(axis, -2)

    def _gap(self, values: tuple[float, ...]) -> float:
        """
        Follow the selected family and complete feature through joint motion, including derivatives.
        """
        pieces = self.model.pieces(values)
        axis = self._axis(pieces)
        bound = self._span(pieces, axis)
        coordinates = tuple(dot(p, axis) for p in self.corners)
        value = (
            bound.low - max(coordinates)
            if self.side is Side.AFTER
            else min(coordinates) - bound.high
        )
        return value / self.model.scale
