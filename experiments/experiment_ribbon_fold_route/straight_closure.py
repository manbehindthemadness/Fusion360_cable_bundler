"""
Derive one actual-cap correction in an unchanged ordered fixed-fold straight space.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference
from devtools.ribbon_analysis.contracts import TargetPose
from experiments.experiment_ribbon_bend_reduction.closure import affine_projection

from .geometry import PlacedPiece, Pose, Straight, pose_error
from .mating import fixed_fold_frames_match, ordered_mating_caps


class SourceReadiness(Enum):
    """
    Preserve legacy closed-route entry or explicitly permit positional correction after strict orientation.

    The owner still validates material/native eligibility and certifies actual
    final closure. This policy changes source admission, never target accuracy.
    """

    FINAL_SHAPE = "final_shape"
    ORIENTED_MATERIAL = "oriented_material"


@dataclass(frozen=True)
class ClosureSpace:
    """
    Bind exact ordered straight directions and the measured defect to one current placement.
    """

    directions: tuple[Vector3, ...]
    offset: Vector3
    active: tuple[int, ...]
    already_closed: bool


def prepare(
    pieces: tuple[PlacedPiece, ...],
    targets: TargetPose,
    lengths_mm: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    fixed_slots: frozenset[int] = frozenset(),
    readiness: SourceReadiness = SourceReadiness.FINAL_SHAPE,
) -> ClosureSpace | None:
    """
    Validate and prepare one fixed-fold correction space in millimeters.

    Preserve slot order through actual folds, including absent boundary slots.
    Supplied lengths must describe these exact pieces; no guessed index mapping,
    target shift, orientation change or active-set search is allowed. Position
    ordinarily meets1e-7route closure and frames the existing strict mating
    criterion. Explicit oriented entry permits an open position with those
    same strict frames. Preparation grants no correction, native eligibility or
    physical certificate. Different projectors share this same slot/frame contract.
    """
    checkpoint()
    if not isinstance(readiness, SourceReadiness):
        raise ValueError("Select explicit source closure readiness")
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
    already_closed = ordered_mating_caps(pieces, targets)
    expected = Pose(targets.end, targets.end_tangent, targets.end_width)
    actual = pieces[-1].end_pose()
    if not already_closed and (
        not fixed_fold_frames_match(pieces, targets)
        or (readiness is SourceReadiness.FINAL_SHAPE and max(pose_error(actual, expected)) > 1e-7)
    ):
        return None
    checkpoint()
    active = tuple(i for i, length in enumerate(lengths_mm) if length > 0 and i not in fixed_slots)
    offset = difference(targets.end, actual.origin)
    return ClosureSpace(tuple(directions), offset, active, already_closed)


def correction(
    pieces: tuple[PlacedPiece, ...],
    targets: TargetPose,
    lengths_mm: tuple[float, ...],
    checkpoint: Callable[[], None],
    *,
    fixed_slots: frozenset[int] = frozenset(),
    readiness: SourceReadiness = SourceReadiness.FINAL_SHAPE,
) -> tuple[float, ...] | None:
    """
    Project one actual-cap defect using the original affine arithmetic and occupied slot order.

    This returns one proposal, not closure proof. Adapters must recompose their
    actual model, enforce bounds/native sizes/quality and check ordered mating.
    """
    space = prepare(
        pieces, targets, lengths_mm, checkpoint, fixed_slots=fixed_slots, readiness=readiness
    )
    if space is None:
        return None
    if space.already_closed:
        return (0.0,) * len(lengths_mm)
    active, directions, offset = space.active, space.directions, space.offset
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
