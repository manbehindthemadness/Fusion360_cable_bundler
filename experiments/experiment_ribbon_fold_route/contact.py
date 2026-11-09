"""
Reject thick ribbon self-intersection using analytic envelopes and volume witnesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Callable, Literal, Protocol

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_bounds import Cell, Span, prepare_projection
from .contact_cap_support import CapPolicy, cap_region
from .contact_caps import straight_bridge_pairs
from .contact_inverse import occupied_coordinates, profile_height
from .contact_profile import clip_profile
from .geometry import FoldRoute, pose_error


@dataclass(frozen=True)
class Penetration:
    """
    Retain one world point occupied by two distinct interior material locations.
    """

    pieces: tuple[int, int]
    first: tuple[float, float, float]
    second: tuple[float, float, float]
    point: Vector3


@dataclass(frozen=True)
class ContactResult:
    """
    Separate envelope clearance, demonstrated penetration and unresolved near-contact.

    A depth-limited result retains its undecided material boxes for diagnostic or
    constraint initialization. Those boxes are neither a penetration witness nor
    permission to accept geometry without a later separation certificate.
    """

    status: str
    pairs_checked: int
    witness: Penetration | None = None
    unresolved_pieces: tuple[int, int] | None = None
    reason: str = ""
    limit: Literal["pairs", "depth"] | None = None
    unresolved_regions: tuple[Cell, Cell] | None = None


class ProjectionReuse(Enum):
    """
    Keep historical evaluation available beside bounded identical cell-projection reuse.
    """

    PREPARATIONS = "preparations"
    CELLS = "cells"


class ProbeOrder(Enum):
    """
    Screen all original pairs first or retain the original depth-first material traversal.
    """

    ORIGINAL_PAIRS = "original_pairs"
    MATERIAL_CELLS = "material_cells"


@dataclass(frozen=True)
class ProbeResult:
    """
    Account optional negative-only work without treating a missed witness as clearance.
    """

    pairs_checked: int
    witness: Penetration | None = None
    limit: Literal["pairs", "supports"] | None = None


class WitnessProbe(Protocol):
    """
    Propose a strict interior witness while sharing the caller's remaining pair allowance.
    """

    def __call__(
        self,
        route: FoldRoute,
        first: int,
        second: int,
        remaining_pairs: int,
        checkpoint: Callable[[], None] | None,
    ) -> ProbeResult:
        """
        Return all compared probe pairs; a miss leaves the complete interval proof mandatory.
        """
        ...


def inspect_contact(
    route: FoldRoute,
    *,
    maximum_pairs: int = 20000,
    maximum_depth: int = 36,
    checkpoint: Callable[[], None] | None = None,
    cap_policy: CapPolicy = CapPolicy.MONOTONE,
    witness_probe: WitnessProbe | None = None,
    probe_order: ProbeOrder = ProbeOrder.ORIGINAL_PAIRS,
    projection_reuse: ProjectionReuse = ProjectionReuse.PREPARATIONS,
) -> ContactResult:
    """
    Enclose every pair of original pieces through bounded material-box subdivision.

    Single regular plane-cylinder-plane folds are injective for |angle|<=pi and
    R>half-thickness. Cap neighborhoods are excluded only through a local half-space
    argument, including certified positive plane gaps across straight bridges.
    Nonadjacent thick regions are never ignored for being close along
    the centerline. Positive separation uses outward floating interval envelopes;
    it is not a formal exact-arithmetic proof or native-solid validation.
    Joined-profile bounds remove only empty space outside the actual lobed section.
    Each call reuses at most 64 immutable piece/axis preparations and each fixed
    adjacent-frame comparison. Every material cell still receives its own cap
    proof and unchanged analytic projection; no route or result cache is global.
    Optional analytic cap support strengthens the same halfspace certificate;
    historical calls retain their original monotonicity proof and traversal.
    An optional negative-only probe screens nonmating original pairs before any
    subdivision, in the historical stack order. Every compared probe pair shares
    the same allowance; missed probes omit no material cells. Probe support-query
    exhaustion disables only the accelerator, leaving the full proof mandatory.
    Cell reuse caches at most512identical projections within this call, changing
    neither arithmetic nor the mandatory pair count or acceptance criteria.
    Explicit material-cell probe order retains the original depth-first witness
    sequence instead of screening all original pairs before subdivision. The
    optional probe still runs only once per original nonmating pair, after its
    ordinary point and separation checks, within the same comparison allowance.
    """
    if not isinstance(cap_policy, CapPolicy):
        raise ValueError("Supply an explicit cap separation policy")
    if not isinstance(projection_reuse, ProjectionReuse):
        raise ValueError("Supply an explicit contact projection reuse policy")
    if not isinstance(probe_order, ProbeOrder):
        raise ValueError("Supply an explicit contact probe order")
    if (
        isinstance(maximum_pairs, bool)
        or not isinstance(maximum_pairs, int)
        or maximum_pairs < 1
        or isinstance(maximum_depth, bool)
        or not isinstance(maximum_depth, int)
        or maximum_depth < 1
    ):
        raise ValueError("Positive finite contact budgets required.")
    half, thickness = route.half_width_mm, route.targets.diameter_mm / 2
    for piece in route.pieces:
        if isinstance(piece.geometry, CylindricalFold) and piece.geometry.radius_mm <= thickness:
            return ContactResult(
                "unresolved", 0, reason="Single-piece thickness map is not regular."
            )
    cells = [
        Cell(i, Span(0.0, 1.0), Span(-half, half), Span(-thickness, thickness))
        for i in range(len(route.pieces))
    ]
    axes = (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    prepared = lru_cache(maxsize=64)(prepare_projection)

    def project(region: Cell, direction: Vector3) -> Span:
        """
        Evaluate one immutable material-cell projection through the original analytic bound.
        """
        return prepared(route.pieces[region.piece], direction)(region)

    evaluated = (
        lru_cache(maxsize=512)(project) if projection_reuse is ProjectionReuse.CELLS else project
    )
    joined: dict[tuple[int, int], bool] = {}
    cache: dict[Cell, tuple[Span, ...]] = {}

    def bounds(region: Cell) -> tuple[Span, ...]:
        """
        Cache only the three world-coordinate broad-phase bounds.
        """
        if region not in cache:
            cache[region] = tuple(evaluated(region, direction) for direction in axes)
        return cache[region]

    pending = [(a, b) for i, a in enumerate(cells) for b in cells[i + 1 :]]
    original_pending: list[tuple[Cell, Cell]] = []
    if witness_probe is not None and probe_order is ProbeOrder.ORIGINAL_PAIRS:
        original_pending, pending = pending, []
    probe_enabled = witness_probe is not None
    bridges = straight_bridge_pairs(route)
    checked = 0
    while pending or original_pending:
        if checkpoint is not None and checked % 64 == 0:
            checkpoint()
        first, second = original_pending.pop() if original_pending else pending.pop()
        if checked >= maximum_pairs:
            return ContactResult(
                "unresolved",
                checked,
                unresolved_pieces=(first.piece, second.piece),
                reason="Contact subdivision budget exhausted.",
                limit="pairs",
            )
        checked += 1
        first = clip_profile(first, route.targets.lines, route.targets.diameter_mm)
        second = clip_profile(second, route.targets.lines, route.targets.diameter_mm)
        if first is None or second is None:
            continue
        a, b = route.pieces[first.piece], route.pieces[second.piece]
        pair = first.piece, second.piece
        if pair not in joined:
            joined[pair] = (
                second.piece == first.piece + 1 and max(pose_error(a.end_pose(), b.pose)) < 1e-10
            ) or pair in bridges
        if (
            joined[pair]
            and cap_region(a, first, True, cap_policy)
            and cap_region(b, second, False, cap_policy)
        ):
            continue
        if any(x.high < y.low or y.high < x.low for x, y in zip(bounds(first), bounds(second))):
            continue
        for cell, other, reversed_pair in ((first, second, False), (second, first, True)):
            u = (cell.u.low + cell.u.high) / 2
            q = (cell.q.low + cell.q.high) / 2
            height = (cell.height.low + cell.height.high) / 2
            if (
                profile_height(q, route.targets.lines, route.targets.diameter_mm) - abs(height)
                <= 1e-8
            ):
                continue
            piece = route.pieces[cell.piece]
            p, v, w, _ = piece.surface(u, q)
            point = p.translated(unit(cross(v, w)), height)
            coordinates = occupied_coordinates(
                route.pieces[other.piece], point, route.targets.lines, route.targets.diameter_mm
            )
            if coordinates is not None:
                local = (u, q, height)
                witness = Penetration(
                    (first.piece, second.piece),
                    coordinates if reversed_pair else local,
                    local if reversed_pair else coordinates,
                    point,
                )
                return ContactResult(
                    "penetration",
                    checked,
                    witness=witness,
                    reason="A world point occupies two strict material interiors.",
                )
        separating = False
        for piece, cell in ((a, first), (b, second)):
            _, v, w, _ = piece.surface(
                (cell.u.low + cell.u.high) / 2, (cell.q.low + cell.q.high) / 2
            )
            for axis in (unit(v), w, unit(cross(v, w))):
                x, y = evaluated(first, axis), evaluated(second, axis)
                if x.high < y.low or y.high < x.low:
                    separating = True
                    break
            if separating:
                break
        if separating:
            continue
        if probe_enabled and first.depth == second.depth == 0 and not joined[pair]:
            assert witness_probe is not None
            allowance = maximum_pairs - checked
            probe = witness_probe(route, first.piece, second.piece, allowance, checkpoint)
            if type(probe.pairs_checked) is not int or not 0 <= probe.pairs_checked <= allowance:
                raise ArithmeticError("Optional contact probe exceeded its shared pair allowance")
            checked += probe.pairs_checked
            if probe.witness is not None:
                if probe.witness.pieces != pair:
                    raise ArithmeticError(
                        "Optional contact witness changed original piece identities"
                    )
                first_coordinates = occupied_coordinates(
                    a, probe.witness.point, route.targets.lines, route.targets.diameter_mm
                )
                second_coordinates = occupied_coordinates(
                    b, probe.witness.point, route.targets.lines, route.targets.diameter_mm
                )
                if first_coordinates is None or second_coordinates is None:
                    raise ArithmeticError(
                        "Optional contact probe returned no strict material witness"
                    )
                witness = Penetration(
                    pair, first_coordinates, second_coordinates, probe.witness.point
                )
                return ContactResult(
                    "penetration",
                    checked,
                    witness=witness,
                    reason="Both original strict inverse maps verify an optional flat-region witness.",
                )
            if probe.limit == "pairs":
                return ContactResult(
                    "unresolved",
                    checked,
                    unresolved_pieces=pair,
                    reason="Shared witness/certificate comparison budget exhausted.",
                    limit="pairs",
                )
            if probe.limit == "supports":
                probe_enabled = False
        if max(first.depth, second.depth) >= maximum_depth:
            return ContactResult(
                "unresolved",
                checked,
                unresolved_pieces=(first.piece, second.piece),
                reason="Near-contact interval resolution exhausted.",
                limit="depth",
                unresolved_regions=(first, second),
            )
        size_a = max(
            (first.u.high - first.u.low) * a.geometry.material_length_mm,
            first.q.high - first.q.low,
            first.height.high - first.height.low,
        )
        size_b = max(
            (second.u.high - second.u.low) * b.geometry.material_length_mm,
            second.q.high - second.q.low,
            second.height.high - second.height.low,
        )
        if size_a >= size_b:
            pending.extend((child, second) for child in first.split(a.geometry.material_length_mm))
        else:
            pending.extend((first, child) for child in second.split(b.geometry.material_length_mm))
    return ContactResult(
        "separated",
        checked,
        reason="Thick envelopes separated; monotone shared caps and certified straight-bridge cap gaps excluded.",
    )
