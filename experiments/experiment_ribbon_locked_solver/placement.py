"""
Avoid an ill-conditioned midpoint frame before allocating the same two guide features.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import rotation_choices


def guide_parameters(
    boundary: Boundary,
    frames: Frames,
    checkpoint: Callable[[], None],
    record: Callable[[dict[str, Any]], None],
) -> tuple[float, ...]:
    """
    Retain the midpoint unless its minimum flat fold runways exceed the whole reference guide.

    Count only before/after material, excluding required curved fold material.
    Such a frame demands nonlocal runways before any straight allocation. Replace
    that one reference by the cumulative-turn midpoint of the existing257sample
    guide, rather than testing alternate headings or adding features. The algebraic
    root count, radii and subsequent construction budgets remain unchanged. This
    is a placement preference, not a physical length bound or feasibility proof.
    """
    checkpoint()
    target = boundary.targets
    middle = frames.at(0.5)
    endpoints = (
        Pose(target.start, target.start_tangent, target.start_width),
        Pose(target.end, target.end_tangent, target.end_width),
    )
    choices = tuple(
        rotation_choices(a, b, boundary.radius_mm, boundary.half_width_mm * 2)
        for a, b in ((endpoints[0], middle), (middle, endpoints[1]))
    )
    if any(not options for options in choices):
        return (0.5,)
    minimum = math.fsum(
        min(math.fsum(fold.before_mm + fold.after_mm for fold in group) for group in options)
        for options in choices
    )
    length = frames.guide.distances[-1]
    parameter = 0.5
    if minimum > length and frames.turns[-1] > 1e-12:
        parameter = frames.turn_parameter(frames.turns[-1] / 2)
    record(
        {
            "stage": "feature_placement",
            "status": "midpoint" if parameter == 0.5 else "cumulative_turn_midpoint",
            "parameters": (parameter,),
            "minimum_midpoint_runway_mm": minimum,
            "guide_length_mm": length,
        }
    )
    checkpoint()
    return (parameter,)
