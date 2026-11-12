"""
Prioritize moved material by sampled spatial proximity without claiming contact or clearance.
"""

from __future__ import annotations

import math
from dataclasses import replace
from heapq import nsmallest
from typing import Callable, Iterator

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece

from .feature_plane import SignedJoints
from .material_pose import current_regions


def motion_priority(
    route: FoldRoute,
    model: SignedJoints,
    values: tuple[float, ...],
    checkpoint: Callable[[], None],
) -> tuple[tuple[int, int], ...]:
    """
    Suggest at most 32 current nonadjacent pairs involving actual model-owned motion.

    Compare with the same model's initial recomposition so source rounding does
    not invent movement. Appearing straight slots retain stable event identity.
    Nine actual zero-height material landmarks per member rank proximity only;
    they are neither an enclosure nor a collision test. The caller must run its
    original strict witness checks and retain every global remainder pair.
    All preparation, including sampling and ordering, uses the caller's clocks.
    """
    checkpoint()
    if values == model.initial:
        return ()
    tags = current_regions(route, model, values)
    if tags is None:
        return ()
    baseline = replace(model.original, pieces=model.pieces(model.initial))
    initial_tags = regions(baseline)
    if len(set(initial_tags)) != len(initial_tags):
        return ()
    before: dict[Region, PlacedPiece] = dict(zip(initial_tags, baseline.pieces))
    changed: set[int] = set()
    for index, (tag, piece) in enumerate(zip(tags, route.pieces)):
        checkpoint()
        old = before.get(tag)
        if old is None:
            changed.add(index)
        elif old.pose != piece.pose or old.geometry != piece.geometry:
            changed.add(index)
    if not changed:
        return ()
    landmarks: list[tuple[Vector3, ...]] = []
    for piece in route.pieces:
        checkpoint()
        points = tuple(
            piece.surface(u, q)[0]
            for u in (0.0, 0.5, 1.0)
            for q in (-route.half_width_mm, 0.0, route.half_width_mm)
        )
        if any(
            not math.isfinite(value) for point in points for value in (point.x, point.y, point.z)
        ):
            return ()
        landmarks.append(points)

    def ranked() -> Iterator[tuple[float, int, int]]:
        """
        Yield finite squared proximity and stable identity with bounded per-pair preparation.
        """
        for first in range(len(route.pieces)):
            for second in range(first + 2, len(route.pieces)):
                checkpoint()
                if first not in changed and second not in changed:
                    continue
                distance = math.inf
                for a in landmarks[first]:
                    for b in landmarks[second]:
                        dx, dy, dz = a.x - b.x, a.y - b.y, a.z - b.z
                        distance = min(distance, dx * dx + dy * dy + dz * dz)
                if math.isfinite(distance):
                    yield distance, first, second

    priority = tuple((first, second) for _, first, second in nsmallest(32, ranked()))
    checkpoint()
    return priority
