"""
Derive an exact alternative for two complete bends bracketed by actual flat material.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Straight
from experiments.experiment_ribbon_joint_route.frames import rotation_choices

from .ledger import Ledger


@dataclass(frozen=True)
class Bracket:
    """
    Retain ordered fold identities and inverse-verified current material coordinates.
    """

    folds: tuple[int, int]
    pieces: tuple[int, int]
    witness: Penetration
    source: FoldRoute


def bracket(route: FoldRoute, witness: Penetration) -> Bracket | None:
    """
    Recognize exactly two complete bends between strict flat occupied locations.

    Straight splitting and flat travel inside the bracket do not change its
    ordered fold identities. Curved endpoints, reversed phases, custom primitives
    and nonpenetrating world points grant no paired action.
    """
    first, last = witness.pieces
    if any(type(i) is not int for i in witness.pieces) or not 0 <= first < last < len(route.pieces):
        raise ValueError("Use ordered existing material pieces")
    coordinates = []
    for index in (first, last):
        point = occupied_coordinates(
            route.pieces[index], witness.point, route.targets.lines, route.targets.diameter_mm
        )
        if point is None:
            return None
        coordinates.append(point)
    for index, point, incoming in ((first, coordinates[0], True), (last, coordinates[1], False)):
        geometry = route.pieces[index].geometry
        if type(geometry) is CylindricalFold:
            low, high = geometry.bend_interval(point[1])
            if (incoming and point[0] > low) or (not incoming and point[0] < high):
                return None
        elif type(geometry) is not Straight:
            return None
    all_folds = [
        i for i, piece in enumerate(route.pieces) if type(piece.geometry) is CylindricalFold
    ]
    selected = [i for i in all_folds if first <= i <= last]
    if len(selected) != 2:
        return None
    ordinal = all_folds.index(selected[0])
    verified = Penetration(witness.pieces, coordinates[0], coordinates[1], witness.point)
    return Bracket((ordinal, ordinal + 1), (selected[0], selected[1]), verified, route)


def alternate(route: FoldRoute, pair: Bracket, ledger: Ledger) -> FoldRoute | None:
    """
    Select the unique entry-reversing balanced factorization, preserving ordered orientation.

    Every generated root consumes the pre-reserved original pool. No ranking,
    second branch trial or added bend follows an ambiguous/unsupported result.
    Each original radius and width remains unchanged; positional closure and
    all physical certificates are still absent from the returned route.
    """
    if pair.source is not route:
        raise ValueError("A paired action requires its identical measured source")
    ledger.reserve_factors()
    first, last = pair.pieces
    original = tuple(route.pieces[i].geometry for i in (first, last))
    if not all(type(fold) is CylindricalFold for fold in original):
        return None
    choices = rotation_choices(
        route.pieces[first].pose,
        route.pieces[last].end_pose(),
        route.radius_mm,
        route.half_width_mm * 2,
    )
    ledger.derived_roots += len(choices)
    if len(choices) > 2:
        raise ArithmeticError("Balanced orientation exceeded its reserved algebraic roots")
    matching = [
        factors
        for factors in choices
        if len(factors) == 2
        and math.copysign(1, original[0].angle_radians)
        != math.copysign(1, factors[0].angle_radians)
    ]
    if len(matching) != 1:
        return None
    factors = matching[0]
    pose = route.pieces[first].pose
    for factor in factors:
        pose = PlacedPiece(pose, factor, "Orientation verification").end_pose()
    expected = route.pieces[last].end_pose()
    if (
        max(
            magnitude(difference(pose.tangent, expected.tangent)),
            magnitude(difference(pose.width, expected.width)),
        )
        > 1e-10
    ):
        raise ArithmeticError("Alternate factors lost ordered end orientation")
    model = FlexibleModel(route)
    values = list(model.initial)
    for ordinal, factor in zip(pair.folds, factors):
        values[4 * ordinal + 1], values[4 * ordinal + 2] = factor.angle_radians, factor.bank_radians
    ledger.checkpoint()
    return FoldRoute(route.targets, model.pieces(tuple(values)), route.radius_mm)
