"""
Vary one internal scheduling angle while preserving both external ordered frames.

Reuse the frozen baseline's branch and chirality. The variable rotates its bank
plane or its orthogonal factorization axes; it never changes an endpoint target.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import cross, difference, dot, magnitude, unit

from .banked_schedule import (
    ScheduleKind,
    TurnSchedule,
    _net_rotation,
)
from .banked_schedule import (
    schedule as baseline_schedule,
)
from .coupled_motion import ZERO, CoupledMotion, rotate
from .coupled_route import CoupledRejection
from .endpoint_first import EndpointCase


def _banked(case: EndpointCase, baseline: TurnSchedule, angle: float) -> tuple[CoupledMotion, ...]:
    """
    Rebuild bank/turn/unbank after rotating its internal normal about the net axis.
    """
    net_axis, net_angle = _net_rotation(case)
    normal = cross(case.start_tangent, case.start_width)
    tangent, width = baseline.motions[1].frame(1)
    bank_normal = rotate(cross(tangent, width), net_axis, angle)
    axis_cross = cross(normal, bank_normal)
    sine, cosine = magnitude(axis_cross), dot(normal, bank_normal)
    if sine <= 1e-10 and cosine < 0:
        raise CoupledRejection("Antipodal bank normal has no unique continuation axis.")
    bank_axis = unit(axis_cross) if sine > 1e-10 else case.start_width
    bank_angle = math.atan2(sine, cosine)
    a, b = dot(bank_axis, case.start_tangent), dot(bank_axis, case.start_width)
    first = CoupledMotion(ZERO, case.start_tangent, case.start_width, bank_axis, bank_angle, 1)
    tangent, width = first.frame(1)
    middle = CoupledMotion(ZERO, tangent, width, net_axis, net_angle, 1)
    tangent, width = middle.frame(1)
    last_axis = unit(ZERO.translated(tangent, a).translated(width, b))
    return first, middle, CoupledMotion(ZERO, tangent, width, last_axis, -bank_angle, 1)


def _factored(
    case: EndpointCase, baseline: TurnSchedule, angle: float
) -> tuple[CoupledMotion, ...]:
    """
    Continue the baseline orthogonal-axis Euler factorization in its local plane.

    The fixed branch is the same A-B-A factorization used by the baseline. Its
    degenerate Euler case retains the original convention, without branch trials.
    """
    axis = baseline.motions[1].axis
    initial = math.atan2(dot(axis, case.start_width), dot(axis, case.start_tangent))
    c, s = math.cos(initial + angle), math.sin(initial + angle)
    a = ZERO.translated(case.start_tangent, c).translated(case.start_width, s)
    b = ZERO.translated(case.start_tangent, s).translated(case.start_width, -c)
    end_a = ZERO.translated(case.end_tangent, c).translated(case.end_width, s)
    end_b = ZERO.translated(case.end_tangent, s).translated(case.end_width, -c)
    matrix = tuple(
        tuple(dot(p, q) for q in (end_a, end_b, cross(end_a, end_b))) for p in (a, b, cross(a, b))
    )
    sine = math.hypot(matrix[1][0], matrix[2][0])
    beta = math.atan2(sine, matrix[0][0])
    angles = (
        (math.atan2(matrix[2][1], matrix[1][1]), beta, 0.0)
        if sine <= 1e-10
        else (math.atan2(matrix[1][0], -matrix[2][0]), beta, math.atan2(matrix[0][1], matrix[0][2]))
    )
    tangent, width, result = case.start_tangent, case.start_width, []
    for index, turn in enumerate(angles):
        u, v = (c, s) if index != 1 else (s, -c)
        axis = unit(ZERO.translated(tangent, u).translated(width, v))
        motion = CoupledMotion(ZERO, tangent, width, axis, turn, 1)
        result.append(motion)
        tangent, width = motion.frame(1)
    return tuple(result)


def schedule(case: EndpointCase, baseline: TurnSchedule, angle: float) -> TurnSchedule:
    """
    Continue one frozen motion family, checking orientation and the no-twist rule.

    Zero angle returns the identical original schedule. An invalid continuation
    rejects rather than changing families, chirality or endpoint orientations.
    """
    if not math.isfinite(angle) or abs(angle) > math.pi / 2:
        raise ValueError("Scheduling angle must be finite and within a quarter turn.")
    if angle == 0:
        return baseline
    turns = (
        _banked(case, baseline, angle)
        if baseline.kind is ScheduleKind.BANKED_TURN
        else _factored(case, baseline, angle)
    )
    tangent, width = turns[-1].frame(1)
    if (
        max(
            magnitude(difference(tangent, case.end_tangent)),
            magnitude(difference(width, case.end_width)),
        )
        > 1e-8
    ):
        raise RuntimeError("Schedule continuation changed the ordered endpoint frame.")
    result = [CoupledMotion(ZERO, case.start_tangent, case.start_width, case.start_width, 0, 1)]
    for turn in turns:
        if abs(turn.angle) > 1e-10 and magnitude(cross(turn.axis, turn.tangent)) <= 1e-10:
            raise CoupledRejection("Schedule continuation would introduce straight twisting.")
        result.append(turn)
        tangent, width = turn.frame(1)
        result.append(CoupledMotion(ZERO, tangent, width, width, 0, 1))
    return TurnSchedule(baseline.kind, tuple(result))


def initial(case: EndpointCase) -> TurnSchedule:
    """
    Select the original deterministic family once, independently of closure results.
    """
    return baseline_schedule(case)
