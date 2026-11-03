"""
Reject thick ribbon self-intersection using analytic envelopes and volume witnesses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from cable_bundler.routing.geometry import Vector3, cross, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_bounds import Cell, Span, cap_neighborhood, projection
from .contact_caps import straight_bridge_pairs
from .contact_inverse import occupied_coordinates, profile_height
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
    """

    status: str
    pairs_checked: int
    witness: Penetration | None = None
    unresolved_pieces: tuple[int, int] | None = None
    reason: str = ""
    limit: Literal["pairs", "depth"] | None = None


def inspect_contact(
    route: FoldRoute,
    *,
    maximum_pairs: int = 20000,
    maximum_depth: int = 36,
    checkpoint: Callable[[], None] | None = None,
) -> ContactResult:
    """
    Enclose every pair of original pieces through bounded material-box subdivision.

    Single regular plane-cylinder-plane folds are injective for |angle|<=pi and
    R>half-thickness. Cap neighborhoods are excluded only through a local half-space
    argument, including certified positive plane gaps across straight bridges.
    Nonadjacent thick regions are never ignored for being close along
    the centerline. Positive separation uses outward floating interval envelopes;
    it is not a formal exact-arithmetic proof or native-solid validation.
    """
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
    cache: dict[Cell, tuple[Span, ...]] = {}

    def bounds(region: Cell) -> tuple[Span, ...]:
        """
        Cache only the three world-coordinate broad-phase bounds.
        """
        if region not in cache:
            cache[region] = tuple(
                projection(route.pieces[region.piece], region, direction) for direction in axes
            )
        return cache[region]

    pending = [(a, b) for i, a in enumerate(cells) for b in cells[i + 1 :]]
    bridges = straight_bridge_pairs(route)
    checked = 0
    while pending:
        if checkpoint is not None and checked % 64 == 0:
            checkpoint()
        first, second = pending.pop()
        if checked >= maximum_pairs:
            return ContactResult(
                "unresolved",
                checked,
                unresolved_pieces=(first.piece, second.piece),
                reason="Contact subdivision budget exhausted.",
                limit="pairs",
            )
        checked += 1
        a, b = route.pieces[first.piece], route.pieces[second.piece]
        if (
            (
                (second.piece == first.piece + 1 and max(pose_error(a.end_pose(), b.pose)) < 1e-10)
                or (first.piece, second.piece) in bridges
            )
            and cap_neighborhood(a, first, True)
            and cap_neighborhood(b, second, False)
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
                x, y = projection(a, first, axis), projection(b, second, axis)
                if x.high < y.low or y.high < x.low:
                    separating = True
                    break
            if separating:
                break
        if separating:
            continue
        if max(first.depth, second.depth) >= maximum_depth:
            return ContactResult(
                "unresolved",
                checked,
                unresolved_pieces=(first.piece, second.piece),
                reason="Near-contact interval resolution exhausted.",
                limit="depth",
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
