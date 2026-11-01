"""
Combine equal-crease bend groups and reclose their unchanged complete route frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import difference
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.geometry import (
    FoldRoute,
    PlacedPiece,
    Pose,
    Straight,
    extend,
    pose_error,
)
from experiments.experiment_ribbon_fold_route.primitives import Piece

from .closure import close_lengths


@dataclass(frozen=True)
class Rewrite:
    """
    Identify one deterministic equal-crease replacement by original piece indices.
    """

    first: int
    last: int
    removed_folds: int
    replacement: CylindricalFold | None


def fold_count(route: FoldRoute) -> int:
    """
    Count finite material bends independently of native surface subdivision.
    """
    return sum(isinstance(piece.geometry, CylindricalFold) for piece in route.pieces)


def rewrites(route: FoldRoute) -> tuple[Rewrite, ...]:
    """
    List same-bank/radius groups, largest fold reduction first, then route order.

    Straight runs inside a group do not alter its rotation. Sum signed fold
    angles about their common carried crease and use its principal rotation;
    an identity becomes one flat connector. This removes solver-authored path
    winding only; no externally prescribed winding/landmark input is supported.
    Both half-turn signs are explicit equivalent rotation branches, principal sign
    first. Their positions and full-ribbon contact are subsequently rechecked.
    """
    folds = [
        (i, piece.geometry)
        for i, piece in enumerate(route.pieces)
        if isinstance(piece.geometry, CylindricalFold)
    ]
    proposals = []
    for start, (first_index, first) in enumerate(folds):
        group = [first]
        for last_index, following in folds[start + 1 :]:
            if (
                max(
                    abs(following.bank_radians - first.bank_radians),
                    abs(following.radius_mm - first.radius_mm),
                    abs(following.width_mm - first.width_mm),
                )
                > 1e-10
            ):
                break
            group.append(following)
            total = math.fsum(item.angle_radians for item in group)
            angle = math.remainder(total, 2 * math.pi)
            if abs(angle) < 1e-10:
                proposals.append(Rewrite(first_index, last_index, len(group), None))
                continue
            angles = (angle, -angle) if abs(abs(angle) - math.pi) < 1e-10 else (angle,)
            for value in angles:
                replacement = CylindricalFold(
                    first.radius_mm,
                    value,
                    first.bank_radians,
                    first.width_mm,
                    first.before_mm,
                    following.after_mm,
                )
                proposals.append(Rewrite(first_index, last_index, len(group) - 1, replacement))
    return tuple(sorted(proposals, key=lambda item: (-item.removed_folds, item.first, item.last)))


def reclose(route: FoldRoute, rewrite: Rewrite) -> FoldRoute | None:
    """
    Replace one group, solve all straight lengths and independently verify closure.

    A replacement bend receives one nonnegative connector slot at either side;
    an identity receives one slot. Outside straights retain their old lengths as
    the least-change projection reference. Numerically zero slots are omitted;
    the independent cap check still bounds their complete positional effect.
    All unaffected folds retain their original objects. Radius/width, material
    identity and ordered endpoint frames remain fixed; contact is a separate gate.
    """
    before = tuple(piece.geometry for piece in route.pieces[: rewrite.first])
    after = tuple(piece.geometry for piece in route.pieces[rewrite.last + 1 :])
    middle: tuple[Piece | None, ...] = (
        (None,) if rewrite.replacement is None else (None, rewrite.replacement, None)
    )
    template: tuple[Piece | None, ...] = before + middle + after
    start = Pose(route.targets.start, route.targets.start_tangent, route.targets.start_width)
    pose = start
    directions = []
    reference = []
    for geometry in template:
        if geometry is None or isinstance(geometry, Straight):
            directions.append(pose.tangent)
            reference.append(geometry.material_length_mm if geometry is not None else 0.0)
        else:
            pose = extend(pose, (geometry,))
    expected = Pose(route.targets.end, route.targets.end_tangent, route.targets.end_width)
    if pose_error(Pose(expected.origin, pose.tangent, pose.width), expected)[1] > 1e-7:
        raise ArithmeticError("Common-crease rewrite changed terminal orientation.")
    lengths = close_lengths(
        tuple(directions), difference(expected.origin, pose.origin), tuple(reference)
    )
    if lengths is None:
        return None
    values = iter(lengths)
    result = []
    pose = start
    for geometry in template:
        if geometry is None or isinstance(geometry, Straight):
            length = next(values)
            if length <= 1e-10:
                continue
            geometry = Straight(length)
            if result and isinstance(result[-1].geometry, Straight):
                previous = result.pop()
                pose = previous.pose
                geometry = Straight(previous.geometry.material_length_mm + length)
        placed = PlacedPiece(pose, geometry, f"Bend reduction piece {len(result) + 1}")
        result.append(placed)
        pose = placed.end_pose()
    if not result:
        return None
    candidate = FoldRoute(route.targets, tuple(result), route.radius_mm)
    if cap_error(candidate) > 1e-7 or fold_count(candidate) >= fold_count(route):
        raise ArithmeticError("Rewrite lost endpoint closure or failed to reduce bends.")
    return candidate
