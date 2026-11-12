"""
Derive one actual-cap correction in an unchanged ordered fixed-fold straight space.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import difference
from devtools.ribbon_analysis.contracts import TargetPose
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

from .geometry import PlacedPiece, Pose, Straight, pose_error
from .mating import matching_frame, ordered_mating_caps


def correction(
    pieces: tuple[PlacedPiece, ...],
    targets: TargetPose,
    lengths_mm: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    fixed_slots: frozenset[int] = frozenset(),
) -> tuple[float, ...] | None:
    """
    Project one measured endpoint defect onto occupied, unfixed straight directions in millimeters.

    Preserve slot order through actual folds, including absent boundary slots.
    Supplied lengths must describe these exact pieces; no guessed index mapping,
    target shift, orientation change or active-set search is allowed. Position
    must already meet ordinary1e-7route closure and frames the existing strict
    mating criterion. The result is one linear proposal only: adapters must
    recompose their actual model, enforce bounds/native sizes/quality, and check
    ordered mating frames. A small affine residual alone is not closure proof.
    """
    checkpoint()
    if any(not math.isfinite(v) or v < 0 for v in lengths_mm) or any(
        type(i) is not int or not 0 <= i < len(lengths_mm) for i in fixed_slots
    ):
        raise ValueError("Use finite nonnegative ordered lengths and existing fixed slots")
    if not pieces:
        return None
    measured = [0.0]
    directions = [pieces[0].pose.tangent]
    for piece in pieces:
        if isinstance(piece.geometry, Straight):
            measured[-1] += piece.geometry.material_length_mm
        else:
            measured.append(0.0)
            directions.append(piece.end_pose().tangent)
    if tuple(measured) != lengths_mm:
        raise ValueError("Straight coordinates must match the actual ordered placement")
    if ordered_mating_caps(pieces, targets):
        return (0.0,) * len(lengths_mm)
    expected = Pose(targets.end, targets.end_tangent, targets.end_width)
    actual = pieces[-1].end_pose()
    if (
        not matching_frame(
            pieces[0].pose, Pose(targets.start, targets.start_tangent, targets.start_width)
        )
        or not matching_frame(Pose(expected.origin, actual.tangent, actual.width), expected)
        or max(pose_error(actual, expected)) > 1e-7
    ):
        return None
    checkpoint()
    active = tuple(i for i, length in enumerate(lengths_mm) if length > 0 and i not in fixed_slots)
    offset = difference(targets.end, actual.origin)
    delta = affine_projection(
        [[getattr(directions[i], axis) for i in active] for axis in "xyz"],
        [getattr(offset, axis) for axis in "xyz"],
        [0.0] * len(active),
    )
    checkpoint()
    if delta is None:
        return None
    result = [0.0] * len(lengths_mm)
    for i, change in zip(active, delta):
        result[i] = change
    return tuple(result)
