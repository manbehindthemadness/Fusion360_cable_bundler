"""
Resolve stable material identity only after verifying the complete current model placement.
"""

from __future__ import annotations

import math

from experiments.experiment_ribbon_feature_insertion.separation import Region, regions
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute

from .feature_plane import SignedJoints


def current_regions(
    route: FoldRoute, model: SignedJoints, values: tuple[float, ...]
) -> tuple[Region, ...] | None:
    """
    Decline incomplete, stale, changed or ambiguous material rather than guessing indexed ownership.

    Exact actual poses, geometry and targets must agree with this model's
    complete coordinates. Identity authorizes guidance only, never clearance.
    """
    if len(values) != len(model.initial) or any(not math.isfinite(value) for value in values):
        return None
    placed = model.pieces(values)
    if (
        route.targets != model.original.targets
        or not model.preserves(route)
        or len(placed) != len(route.pieces)
        or any(a.pose != b.pose or a.geometry != b.geometry for a, b in zip(placed, route.pieces))
    ):
        return None
    tags = regions(route)
    return tags if len(set(tags)) == len(tags) else None
