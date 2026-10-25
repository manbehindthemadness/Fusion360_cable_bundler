"""
Check adaptive turn orientation and continuous reference-lane curvature bounds.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.banked_schedule import ScheduleKind, schedule
from experiments.experiment_ribbon_cap_transition.conductor_allocation import (
    construct,
    curvature_coefficients,
    lane_bound,
    minimum_travel,
)
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO, CoupledMotion, rotate
from experiments.experiment_ribbon_cap_transition.coupled_route import (
    construct as original_construct,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


@pytest.mark.parametrize(
    ("end_tangent", "end_width", "kind"),
    (
        (Y, Vector3(-1, 0, 0), ScheduleKind.BANKED_TURN),
        (Y, Z, ScheduleKind.BANKED_TURN),
        (X, Z, ScheduleKind.CHORD_AXES),
        (X, Vector3(0, 0, -1), ScheduleKind.CHORD_AXES),
        (unit(Vector3(1, 0, 0.3)), Vector3(0, -1, 0), ScheduleKind.BANKED_TURN),
    ),
)
def test_adaptive_schedule_preserves_ordered_poses_and_admissible_turns(
    end_tangent: Vector3, end_width: Vector3, kind: ScheduleKind
) -> None:
    """
    Both structural policies, including the half-turn branch, close orientation.
    """
    case = EndpointCase(
        "orientation-contract", ZERO, Vector3(60, 20, 12), X, end_tangent, Y, end_width
    )
    selected = schedule(case)
    assert selected.kind is kind
    assert len(selected.motions) == 7
    tangent, width = selected.motions[-1].frame(1)
    assert magnitude(difference(tangent, end_tangent)) < 1e-8
    assert magnitude(difference(width, end_width)) < 1e-8
    assert sum(m.angle != 0 for m in selected.motions) <= 3
    for motion in selected.motions:
        assert abs(dot(motion.axis, cross(motion.tangent, motion.width))) < 1e-8
        if abs(motion.angle) > 1e-10:
            assert magnitude(cross(motion.axis, motion.tangent)) > 1e-10
    for a, b in zip(selected.motions, selected.motions[1:]):
        assert magnitude(difference(a.frame(1)[0], b.tangent)) < 1e-8
        assert magnitude(difference(a.frame(1)[1], b.width)) < 1e-8


@pytest.mark.parametrize("angle", (0.01, -0.12, 1.3, math.pi))
@pytest.mark.parametrize("tilt", (0.2, 0.7))
def test_conductor_bound_includes_small_angle_banking_acceleration(
    angle: float, tilt: float
) -> None:
    """
    Analytical lane bounds dominate actual curvature throughout eased rotation.
    """
    case = endpoint_cases()[0]
    axis = unit(Vector3(math.cos(tilt), math.sin(tilt), 0))
    prototype = CoupledMotion(ZERO, X, Y, axis, angle, 1)
    floor = minimum_travel(case, (prototype,))[0]
    motion = replace(prototype, length=floor)
    bound = lane_bound(case, (motion,))
    assert bound <= 1 / (3 * case.diameter_mm)
    a, c = curvature_coefficients(case, motion)
    assert c > 0 and a > 0
    for index in range(33):
        for offset in (-13.5, 0, 13.5):
            _, velocity, acceleration = motion.jet(index / 32, offset)
            actual = magnitude(cross(velocity, acceleration)) / magnitude(velocity) ** 3
            assert actual <= bound + 1e-12


@pytest.mark.parametrize("case", (endpoint_cases()[0], reference_cases()[0]))
def test_exact_controls_keep_geometry_and_analytic_lane_bound(case: EndpointCase) -> None:
    """
    The new policy does not replace previously valid straight and circular geometry.
    """
    plan = construct(case)
    assert plan.schedule_kind is ScheduleKind.ANALYTIC_CONTROL
    assert plan.motions == original_construct(case)
    assert plan.connected and plan.endpoint_gap_mm < 1e-8
    assert plan.lane_curvature_bound_per_mm <= 1 / (3 * case.diameter_mm)


def test_quarter_bank_tie_is_invariant_under_world_rotation() -> None:
    """
    Roundoff around a perpendicular bank must not reverse the selected lift side.
    """
    case = EndpointCase(
        "quarter-bank-invariance", ZERO, Vector3(60, 20, 12), X, Y, Y, Vector3(-1, 0, 0)
    )
    axis, angle = unit(Vector3(1, -2, 3)), 0.73
    moved = replace(
        case,
        start=rotate(case.start, axis, angle),
        end=rotate(case.end, axis, angle),
        start_tangent=rotate(case.start_tangent, axis, angle),
        end_tangent=rotate(case.end_tangent, axis, angle),
        start_width=rotate(case.start_width, axis, angle),
        end_width=rotate(case.end_width, axis, angle),
    )
    original, transformed = schedule(case), schedule(moved)
    assert original.kind is transformed.kind
    for a, b in zip(original.motions, transformed.motions):
        assert a.angle == pytest.approx(b.angle, abs=1e-10)
        assert magnitude(difference(rotate(a.axis, axis, angle), b.axis)) < 1e-8
        assert magnitude(difference(rotate(a.tangent, axis, angle), b.tangent)) < 1e-8
