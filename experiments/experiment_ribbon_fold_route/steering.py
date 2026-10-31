"""
Derive finite-fold translations without canceling an overshoot by folding backward.
"""

from __future__ import annotations

import math
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference

from .contact_bounds import Cell, Span, projection
from .geometry import ZERO, PlacedPiece, Pose, Straight, extend
from .lateral import halfturn_pair
from .primitives import Piece
from .primitives import fold as fold


def signed_distance(
    distance: float,
    radius: float,
    width: float,
    runway: float,
    *,
    arrival_height: float = 0.0,
) -> tuple[Piece, ...]:
    """
    Use positive material travel for a signed forward-axis displacement.

    A negative displacement still requires two half-turns, whose offsets cancel.
    This is reserved for actual negative forward residual, never for correcting
    overshot lateral or height steering folds. Choose the mirrored pair that
    bows away from the opposite cap along the departure normal. Both mirrors
    have the same final pose and material length; coplanar caps retain the old
    direction. This local choice does not replace the full contact gate.
    """
    if abs(distance) < 1e-12:
        return ()
    if distance > 0:
        return (Straight(distance),)
    angle = -math.copysign(math.pi, arrival_height) if abs(arrival_height) > 1e-10 else -math.pi
    half_turn = fold(radius, width, angle, 0.0, runway)
    return half_turn, Straight(-distance), half_turn


def _extent(pose: Pose, pieces: tuple[Piece, ...], width: float, half_thickness: float) -> Span:
    """
    Bound an entire module along the departure tangent, including width/thickness.
    """
    spans = []
    for geometry in pieces:
        piece = PlacedPiece(pose, geometry, "steering support")
        cell = Cell(
            0, Span(0, 1), Span(-width / 2, width / 2), Span(-half_thickness, half_thickness)
        )
        spans.append(projection(piece, cell, Vector3(1, 0, 0)))
        pose = piece.end_pose()
    return Span(min(span.low for span in spans), max(span.high for span in spans))


def _assemble(
    modules: list[tuple[Piece, ...]],
    following: tuple[Piece, ...],
    radius: float,
    width: float,
    half_thickness: float,
) -> tuple[Piece, ...]:
    """
    Separate the chosen frame-returning module order along the departure tangent.
    """
    pose = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
    sequence: list[Piece] = []
    for index, module in enumerate(modules):
        bounds = _extent(pose, module, width, half_thickness)
        sequence.extend(module)
        pose = extend(pose, module)
        next_module = modules[index + 1] if index + 1 < len(modules) else following
        if next_module:
            next_bounds = _extent(pose, next_module, width, half_thickness)
            gap = bounds.high - next_bounds.low + 2 * (radius - half_thickness)
            if gap > 1e-12:
                advance = Straight(gap)
                sequence.append(advance)
                pose = extend(pose, (advance,))
    return tuple(sequence)


def translation(
    residual: Vector3,
    radius: float,
    width: float,
    runway: float,
    half_thickness: float,
    following: tuple[Piece, ...],
    *,
    lateral_builder: Callable[
        [float, float, float, float, float], tuple[Piece, ...]
    ] = halfturn_pair,
) -> tuple[Piece, ...]:
    """
    Close a displacement with frame-returning folds and nonnegative steering runs.

    The lateral builder selects the half-turn baseline or continuously sized
    S-folds; height steering minimizes local material within its two-bend family.
    The second diagonal fold continues into a separate normal layer; its actual
    height offset is included in subsequent height closure. Complete
    module envelopes set forward spacing, using the existing2(R-h)inner clearance.
    Subtract their actual combined forward offset once. The following arrival
    module participates in spacing but is appended separately by the caller.
    All pieces retain the same material map; global contact is checked separately.
    When backward departure is needed and the target normal signs agree, perform
    height steering before lateral steering. This keeps those steering modules
    opposite the mirrored departure run instead of crossing back through it.
    """
    modules: list[tuple[Piece, ...]] = []
    width_height = 0.0
    lateral_distance = abs(residual.y)
    if lateral_distance > 1e-10:
        module = lateral_builder(residual.y, residual.z, radius, width, runway)
        modules.append(module)
        identity = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
        width_height = extend(identity, module).origin.z
    height_target = residual.z - width_height
    height = abs(height_target)
    if height > 1e-10:
        maximum = 2 * (radius + runway)
        if height < maximum:
            tangent = height / (
                2 * runway + math.sqrt(4 * runway**2 + height * (4 * radius - height))
            )
            angle = 2 * math.atan(tangent)
        else:
            angle = math.pi / 2
        signed = math.copysign(angle, height_target)
        middle = (Straight(height - maximum),) if height > maximum else ()
        modules.append(
            (
                fold(radius, width, signed, 0.0, runway),
                *middle,
                fold(radius, width, -signed, 0.0, runway),
            )
        )
    identity = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
    sequence = _assemble(modules, following, radius, width, half_thickness)
    offset = extend(identity, sequence).origin
    remaining = difference(residual, offset)
    arrival_height = residual.z + extend(identity, following).origin.z
    if len(modules) == 2 and remaining.x < -1e-12 and arrival_height * residual.z > 0:
        sequence = _assemble(list(reversed(modules)), following, radius, width, half_thickness)
        remaining = difference(residual, extend(identity, sequence).origin)
    return (
        signed_distance(remaining.x, radius, width, runway, arrival_height=arrival_height)
        + sequence
    )
