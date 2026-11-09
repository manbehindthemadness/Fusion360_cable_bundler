"""
Follow ordered material features when zero straight slots appear or neighboring straights merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight


@dataclass(frozen=True)
class Landmark:
    """
    Name an ordered fold or intervening straight slot and its normalized material fraction.

    Primitive list positions are representation details. This identity deliberately
    does not survive removal/reordering of a fold or disappearance of its own slot.
    """

    kind: Literal["fold", "straight_slot"]
    ordinal: int
    fraction: float
    fold_count: int


def identify(route: FoldRoute, piece_index: int, u: float) -> Landmark:
    """
    Bind a selected material coordinate to ordered features, including merged straight slots.
    """
    if type(piece_index) is not int or not 0 <= piece_index < len(route.pieces) or not 0 <= u <= 1:
        raise ValueError("Choose a material point inside an existing piece")
    pieces = route.pieces
    ordinal = sum(not isinstance(p.geometry, Straight) for p in pieces[:piece_index])
    count = sum(not isinstance(p.geometry, Straight) for p in pieces)
    if not isinstance(pieces[piece_index].geometry, Straight):
        return Landmark("fold", ordinal, u, count)
    indices = _slot(route, ordinal)
    total = sum(pieces[i].geometry.material_length_mm for i in indices)
    before = sum(pieces[i].geometry.material_length_mm for i in indices if i < piece_index)
    fraction = (before + u * pieces[piece_index].geometry.material_length_mm) / total
    return Landmark("straight_slot", ordinal, fraction, count)


def _slot(route: FoldRoute, ordinal: int) -> list[int]:
    """
    Locate all straight fragments between the same ordered pair of folds.
    """
    found = []
    current = 0
    for index, piece in enumerate(route.pieces):
        if isinstance(piece.geometry, Straight):
            if current == ordinal:
                found.append(index)
        else:
            current += 1
    return found


def locate(route: FoldRoute, landmark: Landmark) -> tuple[int, float] | None:
    """
    Return the corresponding material point without inventing identity across removed folds or slots.
    """
    folds = [i for i, p in enumerate(route.pieces) if not isinstance(p.geometry, Straight)]
    if len(folds) != landmark.fold_count:
        return None
    if landmark.kind == "fold":
        return folds[landmark.ordinal], landmark.fraction
    indices = _slot(route, landmark.ordinal)
    distance = landmark.fraction * sum(route.pieces[i].geometry.material_length_mm for i in indices)
    for index in indices:
        length = route.pieces[index].geometry.material_length_mm
        if distance <= length or index == indices[-1]:
            return index, min(1.0, max(0.0, distance / length))
        distance -= length
    return None
