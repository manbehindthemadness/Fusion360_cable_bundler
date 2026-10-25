"""
Check bounded closure mechanics on synthetic inputs without tuning the live matrix.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.closure_allocation import (
    closest_travel,
    construct,
)
from experiments.experiment_ribbon_cap_transition.closure_schedule import initial, schedule
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


@pytest.mark.parametrize("angle", (-0.37, 0.0, 0.29))
@pytest.mark.parametrize(("end_tangent", "end_width"), ((Y, Vector3(-1, 0, 0)), (X, Z)))
def test_internal_angle_preserves_external_frames_and_admissible_bending(
    angle: float, end_tangent: Vector3, end_width: Vector3
) -> None:
    """
    Both continuation policies retain conductor ordering, frame joins and axis rules.
    """
    case = EndpointCase(
        "synthetic-continuation", ZERO, Vector3(83, 17, 21), X, end_tangent, Y, end_width
    )
    baseline = initial(case)
    selected = schedule(case, baseline, angle)
    assert selected.kind is baseline.kind
    if angle == 0:
        assert selected is baseline
    tangent, width = selected.motions[-1].frame(1)
    assert magnitude(difference(tangent, end_tangent)) < 1e-8
    assert magnitude(difference(width, end_width)) < 1e-8
    for motion in selected.motions:
        assert abs(dot(motion.axis, cross(motion.tangent, motion.width))) < 1e-8
        if abs(motion.angle) > 1e-10:
            assert magnitude(cross(motion.axis, motion.tangent)) > 1e-10
    for a, b in zip(selected.motions, selected.motions[1:]):
        assert magnitude(difference(a.frame(1)[0], b.tangent)) < 1e-8
        assert magnitude(difference(a.frame(1)[1], b.width)) < 1e-8


def test_projection_closes_reachable_target_and_retains_unreachable_residual() -> None:
    """
    Positive travel closes available coordinates without inventing reverse motion.
    """
    columns = (X, Y, Z)
    closed = closest_travel(columns, (2, 3, 4), Vector3(8, 9, 10))
    assert closed.lengths == pytest.approx((8, 9, 10))
    assert magnitude(closed.residual) < 1e-8
    failed = closest_travel(columns, (2, 3, 4), Vector3(1, 9, 10))
    assert failed.lengths == pytest.approx((2, 9, 10))
    assert failed.residual == Vector3(-1, 0, 0)
    assert failed.checked_bases == 7


def test_projection_rank_deficiency_and_seven_column_work_cap() -> None:
    """
    Dependent directions remain bounded and cannot erase an unsupported coordinate.
    """
    projected = closest_travel((X,) * 7, (0,) * 7, Vector3(8, 2, 0))
    assert sum(projected.lengths) == pytest.approx(8)
    assert projected.residual == Vector3(0, 2, 0)
    assert projected.checked_bases == 63


def test_solver_preserves_pose_radius_and_fixed_work_budget_on_synthetic_boundary() -> None:
    """
    A complete bounded solve retains its measured gap, frames and curvature floors.
    """
    case = EndpointCase(
        "synthetic-bounded-solve", ZERO, Vector3(121, 37, 28), X, Y, Y, Vector3(-1, 0, 0)
    )
    plan = construct(case)
    assert plan.updates <= 6
    assert plan.projection_calls <= 19
    assert plan.checked_bases_total <= 1197
    assert len(plan.history) == plan.updates + 1
    assert plan.lane_curvature_bound_per_mm <= 1 / (3 * case.diameter_mm)
    actual_gap = magnitude(difference(plan.motions[-1].jet(1)[0], case.end))
    assert plan.endpoint_gap_mm == pytest.approx(actual_gap)
    assert plan.connected == (actual_gap <= 1e-8)
    assert plan.history[-1][1] == pytest.approx(actual_gap, abs=1e-8)
    tangent, width = plan.motions[-1].frame(1)
    assert magnitude(difference(tangent, case.end_tangent)) < 1e-8
    assert magnitude(difference(width, case.end_width)) < 1e-8


def test_solver_retains_analytic_straight_control_without_updates() -> None:
    """
    The control branch keeps exact travel instead of invoking nonlinear closure.
    """
    case = EndpointCase("synthetic-straight", ZERO, Vector3(73, 0, 0), X, X, Y, Y)
    plan = construct(case)
    assert plan.connected and plan.endpoint_gap_mm < 1e-8
    assert sum(m.length for m in plan.motions) == pytest.approx(73)
    assert plan.updates == plan.projection_calls == plan.checked_bases_total == 0
    assert plan.lane_curvature_bound_per_mm == 0


@pytest.mark.parametrize("floor", (-1, math.inf, math.nan))
def test_projection_rejects_invalid_bounds(floor: float) -> None:
    """
    Invalid external numeric data cannot become accepted travel.
    """
    with pytest.raises(ValueError):
        closest_travel((X,), (floor,), X)
