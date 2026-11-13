"""
Select witnessed interval turns and restrict early transfer to unreflected material.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps


def select_fold(route: FoldRoute, witness: Penetration) -> int | None:
    """
    Choose the largest accumulated lane turn between the two actual colliding material locations.

    Each endpoint uses its own occupied lane and bend fraction. Interior folds
    contribute their complete turn; flat runways contribute none. Accumulated
    tangent turning is bend angle times cosine of bank, independent of rigid
    placement, length scale and primitive adjacency. Ties keep material order.
    This is a deterministic correction choice, never a clearance or feasibility
    certificate. No alternative fold is tried after its correction fails.
    """
    first, last = witness.pieces
    if any(type(i) is not int for i in witness.pieces) or not 0 <= first < last < len(route.pieces):
        raise ValueError("A crossing must identify ordered existing material pieces")
    for coordinates in (witness.first, witness.second):
        u, q, _ = coordinates
        if (
            any(isinstance(v, bool) or not math.isfinite(v) for v in coordinates)
            or not 0 <= u <= 1
            or abs(q) > route.half_width_mm
        ):
            raise ValueError("Crossing coordinates must lie within the occupied material domain")
    selected, largest, ordinal = None, 0.0, 0
    for index, piece in enumerate(route.pieces):
        geometry = piece.geometry
        if not isinstance(geometry, CylindricalFold):
            continue
        if first <= index <= last:
            low, high = 0.0, 1.0
            if index in (first, last):
                u, q, _ = witness.first if index == first else witness.second
                entry, bend_end = geometry.bend_interval(q)
                fraction = min(1.0, max(0.0, (u - entry) / (bend_end - entry)))
                if index == first:
                    low = fraction
                else:
                    high = fraction
            turn = (high - low) * abs(geometry.angle_radians) * math.cos(geometry.bank_radians)
            if turn > largest:
                selected, largest = ordinal, turn
        ordinal += 1
    return selected


@dataclass(frozen=True)
class UnreflectedReturns:
    """
    Select an untried interval turn or the bend carrying a witnessed outgoing flat.

    The owning sequence records the current selected turn before entering its
    stage. This immutable set grants neither another motion nor acceptance; the
    caller must still debit and guard its original complete work allocation.
    """

    reflected_folds: frozenset[int]

    def __post_init__(self) -> None:
        """
        Require immutable explicit nonnegative ordered fold identities.
        """
        if not isinstance(self.reflected_folds, frozenset) or any(
            type(index) is not int or index < 0 for index in self.reflected_folds
        ):
            raise ValueError("Reflected folds require immutable nonnegative integer identities")

    def select(self, route: FoldRoute, witness: Penetration) -> int | None:
        """
        Preserve first choices, then permit an untried departure owner at a repeated return.

        A first witness on a fold's AFTER flat inherits that fold's rotation,
        although its bend lies outside the occupied interval. Once the interval's
        dominant turn was reflected and the current ordered caps have closed,
        this directly incident event can receive the next bounded correction.
        Open-cap transient crossings do not preempt the ongoing reclosure.
        Curved/BEFORE points, custom material and previously reflected owners
        grant no alternative or flip-back action.
        This is guidance selection only; strict current-pose evidence, remaining
        work and all final physical certificates remain the caller's responsibility.
        """
        selected = select_fold(route, witness)
        if selected not in self.reflected_folds:
            return selected
        first = witness.pieces[0]
        geometry = route.pieces[first].geometry
        if type(geometry) is not CylindricalFold:
            return None
        if not ordered_mating_caps(route.pieces, route.targets):
            return None
        _, bend_end = cast(CylindricalFold, geometry).bend_interval(witness.first[1])
        if witness.first[0] < bend_end:
            return None
        owner = sum(isinstance(piece.geometry, CylindricalFold) for piece in route.pieces[:first])
        return owner if owner not in self.reflected_folds else None
