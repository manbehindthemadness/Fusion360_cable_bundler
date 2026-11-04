"""
Include an attached straight that demonstrably intersects the same opposing material sheet.
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.straight_witness import straight_witness

from .separation import Region, Separation, regions


class RegionPolicy(Enum):
    """
    Preserve single-witness recovery or include confirmed intersecting attached straights.
    """

    WITNESS = "witness"
    ATTACHED_STRAIGHTS = "attached_straights"


def with_attached_straights(
    bound: Separation, route: FoldRoute, measurement: ContactResult
) -> Separation:
    """
    Expand only a colliding fold's region by directly adjacent, confirmed intersecting straight pieces.

    Use stable material-region identities through later omitted/redistributed slots.
    The same complete thick projection and signed halfspace must clear the union.
    No guessed neighbors, blanket feature exemption or additional route candidates.
    """
    if measurement.witness is None:
        return bound
    tags = regions(route)
    extras: list[tuple[int, Region]] = []
    for side, index in enumerate(measurement.witness.pieces):
        other = measurement.witness.pieces[1 - side]
        if not isinstance(route.pieces[index].geometry, CylindricalFold) or not isinstance(
            route.pieces[other].geometry, Straight
        ):
            continue
        for neighbor in (index - 1, index + 1):
            if not 0 <= neighbor < len(route.pieces) or neighbor == other:
                continue
            first, second = sorted((neighbor, other))
            if straight_witness(route, first, second) is not None:
                extras.append((side, tags[neighbor]))
    return replace(bound, extra_regions=tuple(extras)) if extras else bound
