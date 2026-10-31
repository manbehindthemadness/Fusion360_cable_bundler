"""
Derive finite-fold translations without canceling an overshoot by folding backward.
"""

from __future__ import annotations

import math
from typing import Union

from cable_bundler.routing.geometry import Vector3, difference
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .contact_bounds import Cell, Span, projection
from .geometry import ZERO, PlacedPiece, Pose, Straight, extend

Piece = Union[Straight, CylindricalFold]


def fold(radius: float, width: float, angle: float, bank: float, runway: float) -> CylindricalFold:
    """
    Retain flat terminal material profiles and the explicitly requested extra runway.
    """
    lead = width / 2 * abs(math.tan(bank)) + runway
    return CylindricalFold(radius, angle, bank, width, lead, lead)


def signed_distance(
    distance: float, radius: float, width: float, runway: float
) -> tuple[Piece, ...]:
    """
    Use positive material travel for a signed forward-axis displacement.

    A negative displacement still requires two half-turns, whose offsets cancel.
    This is reserved for actual negative forward residual, never for correcting
    overshot lateral or height steering folds.
    """
    if abs(distance) < 1e-12:
        return ()
    if distance > 0:
        return (Straight(distance),)
    half_turn = fold(radius, width, -math.pi, 0.0, runway)
    return half_turn, Straight(-distance), half_turn


def _lateral_offset(bank: float, radius: float, width: float, runway: float) -> float:
    """
    Return the positive lateral offset of a diagonal half-turn pair.
    """
    s, c = math.sin(bank), math.cos(bank)
    return 2 * width * s * s + 4 * runway * s * c + 2 * math.pi * radius * s


def _bank(distance: float, radius: float, width: float, runway: float) -> float:
    """
    Invert the strictly increasing finite-fold offset on zero through45degrees.

    With no added runway a quadratic in sin(bank) gives the angle directly.
    Extra runway uses52bounded bisections of the same monotone scalar equation;
    these locate an algebraic fold dimension, not alternative route guesses.
    """
    if runway == 0:
        sine = distance / (
            math.pi * radius + math.sqrt((math.pi * radius) ** 2 + 2 * width * distance)
        )
        return math.asin(sine)
    low, high = 0.0, math.pi / 4
    for _ in range(52):
        middle = (low + high) / 2
        if _lateral_offset(middle, radius, width, runway) < distance:
            low = middle
        else:
            high = middle
    return (low + high) / 2


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


def translation(
    residual: Vector3,
    radius: float,
    width: float,
    runway: float,
    half_thickness: float,
    following: tuple[Piece, ...],
) -> tuple[Piece, ...]:
    """
    Close a displacement with frame-returning folds and nonnegative steering runs.

    Small lateral moves reduce the diagonal crease angle; small height moves
    reduce the transverse turn. Larger moves use at most45/90degree steering
    and a forward run. The second diagonal fold continues into a separate normal
    layer; its4R height offset is included in subsequent height closure. Complete
    module envelopes set forward spacing, using the existing2(R-h)inner clearance.
    Subtract their actual combined forward offset once. The following arrival
    module participates in spacing but is appended separately by the caller.
    All pieces retain the same material map; global contact is checked separately.
    """
    modules: list[tuple[Piece, ...]] = []
    width_height = 0.0
    lateral = abs(residual.y)
    if lateral > 1e-10:
        maximum = _lateral_offset(math.pi / 4, radius, width, runway)
        bank = _bank(lateral, radius, width, runway) if lateral < maximum else math.pi / 4
        # Keep this folded layer opposite the subsequent height move.
        direction = -math.copysign(math.pi, residual.z)
        turn = fold(radius, width, direction, -math.copysign(bank, residual.y), runway)
        middle = (Straight(lateral - maximum),) if lateral > maximum else ()
        returning = fold(radius, width, -direction, -math.copysign(bank, residual.y), runway)
        modules.append((turn, *middle, returning))
        width_height = math.copysign(4 * radius, direction)
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
    sequence: list[Piece] = []
    pose = identity
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
    offset = extend(identity, tuple(sequence)).origin
    remaining = difference(residual, offset)
    return signed_distance(remaining.x, radius, width, runway) + tuple(sequence)
