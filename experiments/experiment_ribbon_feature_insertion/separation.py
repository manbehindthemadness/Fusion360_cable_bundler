"""
Measure complete material-region separation while bend joints move and caps remain fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span, projection
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight


class Side(Enum):
    """
    Represent the two signed ways to separate complete projected material bounds.
    """

    BEFORE = 0
    AFTER = 1


class TopologyChanged(ValueError):
    """
    Reject a proposal whose vanished fold invalidates the original region identities.
    """


@dataclass(frozen=True)
class Region:
    """
    Identify an ordered fold or its preceding straight slot independently of omitted zero slots.
    """

    fold: int
    straight: bool


def regions(route: FoldRoute) -> tuple[Region, ...]:
    """
    Map actual source pieces to their stable ordered material slots.
    """
    result = []
    fold = 0
    for piece in route.pieces:
        result.append(Region(fold, isinstance(piece.geometry, Straight)))
        if isinstance(piece.geometry, CylindricalFold):
            fold += 1
    return tuple(result)


def _located(source: FoldRoute, pieces: tuple[PlacedPiece, ...], region: Region) -> PlacedPiece:
    """
    Locate a surviving slot, conservatively enclosing an absent straight with a tiny slab.

    The slab is analysis-only and never becomes route geometry. A missing fold
    rejects the proposal instead of silently measuring a different material event.
    Occupied and internal absent slots use existing piece poses. Only an absent
    trailing slot needs the actual last terminal frame; earlier frames are unused.
    """
    expected = sum(isinstance(p.geometry, CylindricalFold) for p in source.pieces)
    if sum(isinstance(p.geometry, CylindricalFold) for p in pieces) != expected:
        raise TopologyChanged("Joint separation requires the original ordered folds")
    fold = 0
    for piece in pieces:
        if fold == region.fold:
            if region.straight and isinstance(piece.geometry, Straight):
                return piece
            if not region.straight and isinstance(piece.geometry, CylindricalFold):
                return piece
            if region.straight and isinstance(piece.geometry, CylindricalFold):
                return PlacedPiece(piece.pose, Straight(1e-12), "Absent-slot bound")
        if isinstance(piece.geometry, CylindricalFold):
            fold += 1
    if region.straight and fold == region.fold:
        previous = (
            pieces[-1].end_pose()
            if pieces
            else Pose(
                source.targets.start, source.targets.start_tangent, source.targets.start_width
            )
        )
        return PlacedPiece(previous, Straight(1e-12), "Absent terminal-slot bound")
    raise TopologyChanged("Original material region is unavailable")


def locate(source: FoldRoute, pieces: tuple[PlacedPiece, ...], region: Region) -> PlacedPiece:
    """
    Resolve a stable material slot with the shared fold-count and absent-runway rules.
    """
    return _located(source, pieces, region)


@dataclass(frozen=True)
class Separation:
    """
    Retain a witness-derived sheet normal and two complete analytic material bounds.

    An explicit straight plane follows that material region through joint motion,
    including differentiation. Other constraints retain their historical world axis.
    """

    model: MovableBends
    pair: tuple[Region, Region]
    axis: Vector3
    extra_regions: tuple[tuple[int, Region], ...] = ()
    plane: Region | None = None

    @classmethod
    def from_measurement(
        cls, model: MovableBends, route: FoldRoute, measurement: ContactResult
    ) -> Separation | None:
        """
        Initialize a constraint from a witness or actual depth-limited material boxes.

        Preserve the existing penetration rule. For unresolved depth evidence,
        prefer a straight sheet normal; otherwise use the first undecided box's
        material midpoint normal. Missing, mismatched or malformed evidence stays
        unsupported. This chooses a constraint axis, never contact acceptance.
        """
        if measurement.status == "penetration" and measurement.witness is not None:
            return cls.create(model, route, measurement.witness)
        if measurement.status != "unresolved" or measurement.limit != "depth":
            return None
        pair, cells = measurement.unresolved_pieces, measurement.unresolved_regions
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not isinstance(cells, tuple)
            or len(cells) != 2
            or not all(isinstance(cell, Cell) for cell in cells)
            or any(type(i) is not int or not 0 <= i < len(route.pieces) for i in pair)
            or tuple(cell.piece for cell in cells) != pair
        ):
            return None
        flat = next(
            (i for i in reversed(pair) if isinstance(route.pieces[i].geometry, Straight)), None
        )
        if flat is not None:
            piece = route.pieces[flat]
            axis = unit(cross(piece.pose.tangent, piece.pose.width))
        else:
            first = cells[0]
            if (
                not isinstance(first.u, Span)
                or not isinstance(first.q, Span)
                or not all(
                    math.isfinite(v) for v in (first.u.low, first.u.high, first.q.low, first.q.high)
                )
                or not 0 <= first.u.low <= first.u.high <= 1
                or not -route.half_width_mm <= first.q.low <= first.q.high <= route.half_width_mm
            ):
                return None
            _, velocity, width, _ = route.pieces[pair[0]].surface(
                (first.u.low + first.u.high) / 2, (first.q.low + first.q.high) / 2
            )
            axis = unit(cross(velocity, width))
        tags = regions(route)
        return cls(model, (tags[pair[0]], tags[pair[1]]), axis)

    @classmethod
    def create(cls, model: MovableBends, route: FoldRoute, witness: Penetration) -> Separation:
        """
        Prefer a colliding straight's sheet normal, otherwise use the first witness's normal.
        """
        first, second = witness.pieces
        tags = regions(route)
        piece = (
            route.pieces[second]
            if isinstance(route.pieces[second].geometry, Straight)
            else route.pieces[first]
        )
        if isinstance(piece.geometry, Straight):
            axis = unit(cross(piece.pose.tangent, piece.pose.width))
        else:
            u, q, _ = witness.first
            _, velocity, width, _ = piece.surface(u, q)
            axis = unit(cross(velocity, width))
        return cls(model, (tags[first], tags[second]), axis)

    @classmethod
    def following_measurement(
        cls, model: MovableBends, route: FoldRoute, measurement: ContactResult
    ) -> Separation | None:
        """
        Follow a newly confirmed straight crossing after the initial joint correction.

        The first material sheet supplies the moving plane during differentiation
        and retraction. Initial branch prediction, fold contacts and undecided
        depth boxes retain their existing constraint axes. This chooses motion;
        acceptance still requires an independent complete contact certificate.
        """
        bound = cls.from_measurement(model, route, measurement)
        if (
            bound is not None
            and measurement.status == "penetration"
            and measurement.witness is not None
            and all(region.straight for region in bound.pair)
        ):
            return replace(bound, plane=bound.pair[0])
        return bound

    def gap(self, values: tuple[float, ...], side: Side) -> float:
        """
        Return a normalized signed gap, following an explicitly attached material plane when supplied.
        """
        source = self.model.original
        pieces = self.model.pieces(values)
        direction = self.axis
        if self.plane is not None:
            sheet = _located(source, pieces, self.plane)
            direction = unit(cross(sheet.pose.tangent, sheet.pose.width))
        spans = []
        for part_index, region in enumerate(self.pair):
            cell = Cell(
                0,
                Span(0, 1),
                Span(-source.half_width_mm, source.half_width_mm),
                Span(-source.targets.diameter_mm / 2, source.targets.diameter_mm / 2),
            )
            bound = projection(_located(source, pieces, region), cell, direction)
            for part, tag in self.extra_regions:
                if part == part_index:
                    extra = projection(_located(source, pieces, tag), cell, direction)
                    bound = Span(min(bound.low, extra.low), max(bound.high, extra.high))
            spans.append(bound)
        first, second = spans
        gap = second.low - first.high if side is Side.BEFORE else first.low - second.high
        return gap / self.model.scale

    def gradient(
        self, values: tuple[float, ...], side: Side, checkpoint: Callable[[], None]
    ) -> list[float]:
        """
        Differentiate the bound gap inside declared joint coordinates using bounded probes.
        """
        result = []
        for index, value in enumerate(values):
            checkpoint()
            low, high = self.model.bounds(index)
            before, after = max(low, value - 1e-5), min(high, value + 1e-5)
            a, b = list(values), list(values)
            a[index], b[index] = before, after
            result.append(
                (self.gap(tuple(b), side) - self.gap(tuple(a), side)) / (after - before)
                if after > before
                else 0.0
            )
        return result
