"""
Select three admissible turns from the net endpoint rotation and displacement.

Spatial heading changes use bank/turn/unbank conjugation. Roll-dominant poses
use a chord-projected orthogonal basis instead of fixed45degree axes. These
are deterministic structural cases, not alternative solutions tried after failure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .coupled_motion import ZERO, CoupledMotion
from .coupled_route import CoupledRejection
from .endpoint_first import EndpointCase, controls


class ScheduleKind(Enum):
    """
    Identify the preselected orientation policy independently of allocation success.
    """

    BANKED_TURN = "bank-turn-unbank"
    CHORD_AXES = "chord-projected rotation axes"
    ANALYTIC_CONTROL = "unchanged analytic control"


@dataclass(frozen=True)
class TurnSchedule:
    """
    Retain three eased turns interleaved with four optional straight motions.
    """

    kind: ScheduleKind
    motions: tuple[CoupledMotion, ...]


def _net_rotation(case: EndpointCase) -> tuple[Vector3, float]:
    """
    Extract the endpoint frame's world rotation axis and principal angle.

    These fixtures prescribe ordered frames, not additional full winding. A
    half-turn uses corresponding-axis sums and the chord to orient its axis.
    Identity rotation has no unique axis and rejects outside analytic controls.
    """
    start_normal = cross(case.start_tangent, case.start_width)
    end_normal = cross(case.end_tangent, case.end_width)
    pairs = (
        (case.start_tangent, case.end_tangent),
        (case.start_width, case.end_width),
        (start_normal, end_normal),
    )
    skew = ZERO
    for a, b in pairs:
        skew = skew.translated(cross(a, b), 1)
    sine = magnitude(skew) / 2
    cosine = max(-1.0, min(1.0, (sum(dot(a, b) for a, b in pairs) - 1) / 2))
    angle = math.atan2(sine, cosine)
    if sine > 1e-10:
        return unit(skew), angle
    if cosine > 0:
        raise CoupledRejection("Identity-frame displaced route needs a separate schedule.")
    axis = unit(max((a.translated(b, 1) for a, b in pairs), key=magnitude))
    chord = difference(case.end, case.start)
    for reference in (chord, case.start_tangent, case.start_width, start_normal):
        projection = dot(axis, reference)
        if abs(projection) > 1e-10:
            if projection < 0:
                axis = ZERO.translated(axis, -1)
            break
    return axis, math.pi


def _banked_turn(
    case: EndpointCase, net_axis: Vector3, net_angle: float
) -> tuple[CoupledMotion, ...]:
    """
    Conjugate the net rotation by a coupled bank into its admissible turning plane.

    The banked normal is perpendicular to both the net axis and chord. This
    places the main rotation axis in the ribbon tangent/width plane. The final
    inverse body rotation restores the exact ordered endpoint frame.
    """
    normal = cross(case.start_tangent, case.start_width)
    bank_normal = cross(net_axis, unit(difference(case.end, case.start)))
    if magnitude(bank_normal) <= 1e-10:
        raise CoupledRejection("Net rotation and chord do not define a unique banking plane.")
    bank_normal = unit(bank_normal)
    normal_alignment = dot(normal, bank_normal)
    if normal_alignment < -1e-10:
        bank_normal = ZERO.translated(bank_normal, -1)
    elif abs(normal_alignment) <= 1e-10:
        # At an exact quarter bank, choose lift toward the endpoint's normal offset.
        candidate_axis = unit(cross(normal, bank_normal))
        bend_sign = dot(cross(candidate_axis, case.start_tangent), normal)
        target_sign = -1 if dot(difference(case.end, case.start), normal) < -1e-10 else 1
        if bend_sign * target_sign < 0:
            bank_normal = ZERO.translated(bank_normal, -1)
    bank_axis = unit(cross(normal, bank_normal))
    angle = math.atan2(magnitude(cross(normal, bank_normal)), dot(normal, bank_normal))
    a, b = dot(bank_axis, case.start_tangent), dot(bank_axis, case.start_width)
    first = CoupledMotion(ZERO, case.start_tangent, case.start_width, bank_axis, angle, 1)
    tangent, width = first.frame(1)
    middle = CoupledMotion(ZERO, tangent, width, net_axis, net_angle, 1)
    tangent, width = middle.frame(1)
    last_axis = unit(ZERO.translated(tangent, a).translated(width, b))
    last = CoupledMotion(ZERO, tangent, width, last_axis, -angle, 1)
    return first, middle, last


def _chord_axes(case: EndpointCase) -> tuple[CoupledMotion, ...]:
    """
    Factor the net frame change about a chord-projected local orthogonal basis.

    Chord projection onto the start tangent/width plane fixes the basis before
    allocation. Degenerate projections or a nonzero straight twist reject rather
    than introducing a fixed-angle fallback or an alternate decomposition.
    """
    chord = difference(case.end, case.start)
    x, y = dot(chord, case.start_tangent), dot(chord, case.start_width)
    norm = math.hypot(x, y)
    if norm <= 1e-10:
        raise CoupledRejection("Chord projection does not define rotation axes.")
    c, s = x / norm, y / norm
    a = ZERO.translated(case.start_tangent, c).translated(case.start_width, s)
    b = ZERO.translated(case.start_tangent, s).translated(case.start_width, -c)
    end_a = ZERO.translated(case.end_tangent, c).translated(case.end_width, s)
    end_b = ZERO.translated(case.end_tangent, s).translated(case.end_width, -c)
    basis, target = (a, b, cross(a, b)), (end_a, end_b, cross(end_a, end_b))
    matrix = tuple(tuple(dot(p, q) for q in target) for p in basis)
    sine = math.hypot(matrix[1][0], matrix[2][0])
    beta = math.atan2(sine, matrix[0][0])
    angles = (
        (math.atan2(matrix[2][1], matrix[1][1]), beta, 0.0)
        if sine <= 1e-10
        else (math.atan2(matrix[1][0], -matrix[2][0]), beta, math.atan2(matrix[0][1], matrix[0][2]))
    )
    tangent, width, motions = case.start_tangent, case.start_width, []
    for index, angle in enumerate(angles):
        u, v = (c, s) if index != 1 else (s, -c)
        axis = unit(ZERO.translated(tangent, u).translated(width, v))
        motion = CoupledMotion(ZERO, tangent, width, axis, angle, 1)
        motions.append(motion)
        tangent, width = motion.frame(1)
    return tuple(motions)


def schedule(case: EndpointCase) -> TurnSchedule:
    """
    Choose one three-turn family and enforce pose closure and no straight twisting.

    Straight travel at four fixed frame poses adds allocation freedom without
    adding rotation phases. There is no geometry search or retry on another family.
    """
    controls(case)
    axis, angle = _net_rotation(case)
    normal = cross(case.start_tangent, case.start_width)
    kind = ScheduleKind.BANKED_TURN if abs(dot(axis, normal)) > 1e-8 else ScheduleKind.CHORD_AXES
    turns = (
        _banked_turn(case, axis, angle) if kind is ScheduleKind.BANKED_TURN else _chord_axes(case)
    )
    end_tangent, end_width = turns[-1].frame(1)
    if (
        max(
            magnitude(difference(end_tangent, case.end_tangent)),
            magnitude(difference(end_width, case.end_width)),
        )
        > 1e-8
    ):
        raise RuntimeError("Three-turn schedule failed ordered endpoint orientation closure.")
    motions = [CoupledMotion(ZERO, case.start_tangent, case.start_width, case.start_width, 0, 1)]
    for turn in turns:
        if abs(turn.angle) > 1e-10 and magnitude(cross(turn.axis, turn.tangent)) <= 1e-10:
            raise CoupledRejection("Straight twisting is excluded from the three-turn schedule.")
        motions.append(turn)
        tangent, width = turn.frame(1)
        motions.append(CoupledMotion(ZERO, tangent, width, width, 0, 1))
    return TurnSchedule(kind, tuple(motions))
