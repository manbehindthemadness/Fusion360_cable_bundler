"""
Construct a bounded fold route algebraically from both fixed endpoint poses.

This direct sufficient construction does not search route guesses or establish
minimum length, minimum fold count, collision freedom or native sweep success.
"""

from __future__ import annotations

import math
from typing import Callable, Union

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from devtools.ribbon_analysis.contracts import TargetPose, Targets
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.pinch import PinchLimit

from .geometry import ZERO, FoldRoute, PlacedPiece, Pose, Straight, extend, pose_error, relative

Piece = Union[Straight, CylindricalFold]
DEFAULT_LIMIT = PinchLimit()


def _fold(radius: float, width: float, angle: float, bank: float) -> CylindricalFold:
    """
    Use just enough flat material for both terminal profiles to clear the crease.
    """
    lead = width / 2 * abs(math.tan(bank))
    return CylindricalFold(radius, angle, bank, width, lead, lead)


def _orientation(start: Pose, end: Pose, radius: float, width: float) -> tuple[Piece, ...]:
    """
    Decompose the relative frame into rotations about two orthogonal diagonal creases.

    Proper A-B-A Euler angles use A=(T+W)/sqrt(2), B=(-T+W)/sqrt(2).
    These fixed45degree creases avoid singular longitudinal folds. A common
    width direction instead uses one transverse fold. All angles come from the
    requested poses; no route initialization, coefficient fitting or retry occurs.
    """
    if magnitude(difference(start.width, end.width)) < 1e-10:
        angle = math.atan2(
            dot(end.tangent, cross(start.tangent, start.width)), dot(end.tangent, start.tangent)
        )
        return () if abs(angle) < 1e-12 else (_fold(radius, width, angle, 0.0),)
    root = math.sqrt(0.5)
    axes = (Vector3(root, root, 0), Vector3(-root, root, 0), Vector3(0, 0, 1))
    columns = tuple(
        relative(start, axis) for axis in (end.tangent, end.width, cross(end.tangent, end.width))
    )

    def rotate(vector: Vector3) -> Vector3:
        """
        Apply the requested relative orientation in departure-frame coordinates.
        """
        return (
            ZERO.translated(columns[0], vector.x)
            .translated(columns[1], vector.y)
            .translated(columns[2], vector.z)
        )

    matrix = tuple(tuple(dot(a, rotate(b)) for b in axes) for a in axes)
    middle = math.acos(max(-1.0, min(1.0, matrix[0][0])))
    if abs(math.sin(middle)) < 1e-10:
        first, last = math.atan2(matrix[2][1], matrix[1][1]), 0.0
    else:
        first = math.atan2(matrix[1][0], -matrix[2][0])
        last = math.atan2(matrix[0][1], matrix[0][2])
    return tuple(
        _fold(radius, width, -angle, bank)
        for angle, bank in ((first, -math.pi / 4), (middle, math.pi / 4), (last, -math.pi / 4))
        if abs(angle) >= 1e-12
    )


def _signed_distance(distance: float, radius: float, width: float) -> tuple[Piece, ...]:
    """
    Advance a signed displacement without ever reversing material progression.

    Negative displacement uses two rounded transverse half-turns around a forward
    straight run. Their offsets cancel and their orientation returns to identity.
    This adds physical path length, not a negative-speed or stretched guide.
    """
    if abs(distance) < 1e-12:
        return ()
    if distance > 0:
        return (Straight(distance),)
    half_turn = _fold(radius, width, math.pi, 0.0)
    return half_turn, Straight(-distance), half_turn


def _simple(start: Pose, end: Pose, radius: float, width: float) -> tuple[Piece, ...] | None:
    """
    Solve straight or one-plane turns directly before using spatial steering.
    """
    if magnitude(difference(start.width, end.width)) >= 1e-10:
        return None
    delta = difference(end.origin, start.origin)
    angle = math.atan2(
        dot(end.tangent, cross(start.tangent, start.width)), dot(end.tangent, start.tangent)
    )
    if abs(angle) < 1e-12:
        lateral = delta.translated(start.tangent, -dot(delta, start.tangent))
        if magnitude(lateral) < 1e-10:
            return _signed_distance(dot(delta, start.tangent), radius, width)
        return None
    if abs(math.sin(angle)) < 1e-10:
        return None
    fold = _fold(radius, width, angle, 0.0)
    offset = difference(extend(start, (fold,)).origin, start.origin)
    residual = difference(delta, offset)
    b = dot(residual, cross(start.tangent, start.width)) / math.sin(angle)
    a = dot(residual, start.tangent) - math.cos(angle) * b
    if abs(dot(residual, start.width)) > 1e-10 or min(a, b) < -1e-10:
        return None
    return (
        tuple([Straight(a)] if a > 1e-12 else [])
        + (fold,)
        + tuple([Straight(b)] if b > 1e-12 else [])
    )


def connect(
    source: TargetPose,
    limit: PinchLimit = DEFAULT_LIMIT,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> FoldRoute:
    """
    Connect fixed ordered poses by isometric folds and algebraic displacement closure.

    Straight distances are solved after subtracting finite-fold offsets. Spatial
    steering returns to the departure frame before the arrival orientation is
    applied. All pieces preserve material length and the same profile coordinates.
    A declared1e-9relative radius inset avoids a floating boundary classification;
    numerical cap residuals must remain below1e-7, without moving targets.
    """
    targets = Targets.capture(source)
    if magnitude(difference(targets.start, targets.end)) <= 1e-8:
        raise ValueError("Coincident endpoints need a separately specified loop construction.")
    if checkpoint is not None:
        checkpoint()
    radius = targets.diameter_mm / 2 / limit.fraction * (1 + 1e-9)
    width = 2 * (targets.lines * targets.diameter_mm / 2 + targets.diameter_mm * 0.1)
    start = Pose(targets.start, targets.start_tangent, targets.start_width)
    end = Pose(targets.end, targets.end_tangent, targets.end_width)
    simple = _simple(start, end, radius, width)
    if simple is not None:
        geometries = simple
    else:
        orientation = _orientation(start, end, radius, width)
        oriented = extend(start, orientation)
        residual = relative(start, difference(end.origin, oriented.origin))
        width_sign = math.copysign(1.0, residual.y)
        height_sign = math.copysign(1.0, residual.z)
        width_turn = _fold(radius, width, math.pi, -width_sign * math.pi / 4)
        height_turn = _fold(radius, width, height_sign * math.pi / 2, 0.0)
        height_return = _fold(radius, width, -height_sign * math.pi / 2, 0.0)
        width_active, height_active = abs(residual.y) > 1e-10, abs(residual.z) > 1e-10
        identity = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
        width_offset = extend(identity, (width_turn, width_turn)).origin if width_active else ZERO
        height_offset = (
            extend(identity, (height_turn, height_return)).origin if height_active else ZERO
        )
        travel = difference(difference(residual, width_offset), height_offset)
        sequence = list(_signed_distance(travel.x, radius, width))
        if width_active:
            sequence.extend(
                (width_turn, *_signed_distance(width_sign * travel.y, radius, width), width_turn)
            )
        if height_active:
            sequence.extend(
                (
                    height_turn,
                    *_signed_distance(height_sign * travel.z, radius, width),
                    height_return,
                )
            )
        geometries = tuple(sequence) + orientation
    pose = start
    pieces = []
    for index, geometry in enumerate(geometries):
        if checkpoint is not None:
            checkpoint()
        label = f"{'Fold' if isinstance(geometry, CylindricalFold) else 'Straight'} {index + 1}"
        piece = PlacedPiece(pose, geometry, label)
        pieces.append(piece)
        pose = piece.end_pose()
    gap, frame_gap = pose_error(pose, end)
    if not pieces or max(gap, frame_gap) > 1e-7:
        raise ValueError(f"Algebraic construction failed cap closure: {gap=}, {frame_gap=}.")
    return FoldRoute(targets, tuple(pieces), radius)
