"""
Verify local developability, material-coordinate inversion and terminal identity.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.closure_schedule import initial
from experiments.experiment_ribbon_cap_transition.coupled_motion import ZERO, CoupledMotion
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.material_allocation import construct
from experiments.experiment_ribbon_cap_transition.material_guides import audit, spline_controls
from experiments.experiment_ribbon_cap_transition.material_policy import (
    minimum_travel,
    place,
    prototypes,
)
from experiments.experiment_ribbon_cap_transition.material_strip import (
    MaterialSpan,
    MaterialStrip,
    normal_section_peak_extension,
    ruling_slope,
)

X, Y = Vector3(1, 0, 0), Vector3(0, 1, 0)


def _strip() -> MaterialStrip:
    """
    Build a synthetic flat/cylindrical/flat strip with regular ruling transitions.
    """
    approach = CoupledMotion(ZERO, X, Y, Y, 0, 30)
    turn = CoupledMotion(approach.jet(1)[0], X, Y, unit(Vector3(1, 1, 0)), 1.2, 80)
    tangent, width = turn.frame(1)
    departure = CoupledMotion(turn.jet(1)[0], tangent, width, width, 0, 30)
    return MaterialStrip(
        (MaterialSpan(approach, 0, 1), MaterialSpan(turn, 1, 1), MaterialSpan(departure, 1, 0)), 10
    )


@pytest.mark.parametrize("offset", (-10.0, -3.0, 0.0, 7.0, 10.0))
def test_material_lanes_have_unit_speed_and_exact_terminal_positions(offset: float) -> None:
    """
    Isometric lanes preserve reference length and end tangents without length repair.
    """
    strip = _strip()
    assert strip.length_mm == 140
    for distance in (0.0, 12.0, 35.0, 70.0, 105.0, 128.0, 140.0):
        position, velocity, acceleration = strip.jet(distance, offset)
        assert all(math.isfinite(v) for v in (position.x, position.y, position.z))
        assert magnitude(velocity) == pytest.approx(1)
        assert abs(dot(velocity, acceleration)) < 1e-12
    for distance, span, u in ((0.0, strip.spans[0], 0.0), (140.0, strip.spans[-1], 1.0)):
        assert strip.jet(distance, offset)[0] == span.motion.jet(u, offset)[0]
        assert strip.jet(distance, offset)[1] == span.motion.frame(u)[0]


@pytest.mark.parametrize("offset", (-8.0, 0.0, 8.0))
def test_analytic_lane_jets_match_material_coordinate_finite_differences(offset: float) -> None:
    """
    Shifted coordinates produce the derivatives of the actual material path.
    """
    strip = _strip()
    h = 1e-3
    for distance in (15.0, 60.0, 90.0, 125.0):
        position, velocity, acceleration = strip.jet(distance, offset)
        before = strip.jet(distance - h, offset)[0]
        after = strip.jet(distance + h, offset)[0]
        numerical_velocity = ZERO.translated(after, 1 / (2 * h)).translated(before, -1 / (2 * h))
        numerical_acceleration = (
            ZERO.translated(after, 1 / h**2)
            .translated(position, -2 / h**2)
            .translated(before, 1 / h**2)
        )
        assert magnitude(ZERO.translated(numerical_velocity, 1).translated(velocity, -1)) < 1e-7
        assert (
            magnitude(ZERO.translated(numerical_acceleration, 1).translated(acceleration, -1))
            < 1e-6
        )


def test_material_surface_metric_preserves_width_and_orthogonality() -> None:
    """
    Material cross-sections have unit transverse speed even where they curve.
    """
    strip = _strip()
    h = 1e-4
    for distance in (25.0, 60.0, 115.0):
        _, tangent, _ = strip.jet(distance, 3)
        before, after = strip.jet(distance, 3 - h)[0], strip.jet(distance, 3 + h)[0]
        transverse = ZERO.translated(after, 1 / (2 * h)).translated(before, -1 / (2 * h))
        assert magnitude(transverse) == pytest.approx(1, abs=1e-7)
        assert abs(dot(tangent, transverse)) < 1e-7


def test_near_straight_twist_exposes_old_extension_and_principal_curvature_cost() -> None:
    """
    Nonzero bend alone cannot disguise predominantly twisting motion as compatible.
    """
    motion = CoupledMotion(ZERO, X, Y, unit(Vector3(1, 0.01, 0)), math.pi / 2, 80)
    slope = ruling_slope(motion)
    span = MaterialSpan(motion, slope, slope)
    assert normal_section_peak_extension(motion, 10) > 0.05
    assert span.maximum_principal_curvature() > 1000 * motion.maximum_curvature()
    with pytest.raises(ValueError, match="Pure twist"):
        ruling_slope(replace(motion, axis=X))


def test_rejects_incompatible_rulings_and_finite_width_singularity() -> None:
    """
    Incorrect twist/bend relations and intersecting material coordinates fail closed.
    """
    strip = _strip()
    with pytest.raises(ValueError, match="local developability"):
        MaterialSpan(strip.spans[1].motion, 0, 0)
    with pytest.raises(ValueError, match="regularity"):
        replace(strip, half_width_mm=30)
    with pytest.raises(ValueError, match="terminal"):
        replace(strip, spans=(strip.spans[1],))


def test_material_policy_bounds_surface_curvature_and_preserves_terminal_pose() -> None:
    """
    A new synthetic schedule produces regular spans without a closure assertion.
    """
    case = EndpointCase(
        "synthetic-material-policy", ZERO, Vector3(95, 23, 17), X, X, Y, Vector3(0, 0, 1)
    )
    selected = initial(case)
    spans = prototypes(selected)
    lengths = minimum_travel(case, spans)
    strip = place(case, spans, lengths)
    reach = math.hypot(strip.half_width_mm, case.diameter_mm / 2)
    assert all(span.minimum_jacobian(strip.half_width_mm) > 0 for span in strip.spans)
    assert all(span.maximum_principal_curvature() * reach <= 0.8 for span in strip.spans)
    assert strip.jet(0)[0] == case.start
    assert strip.jet(strip.length_mm)[1].x == pytest.approx(case.end_tangent.x, abs=1e-8)
    final = strip.spans[-1].motion.frame(1)
    assert final[1].z == pytest.approx(case.end_width.z, abs=1e-8)


def test_material_solver_has_fixed_work_and_retains_unclosed_endpoints() -> None:
    """
    The bounded solver returns the actual compatible strip without endpoint snapping.
    """
    case = EndpointCase(
        "synthetic-material-solve", ZERO, Vector3(110, 24, 19), X, X, Y, Vector3(0, 0, 1)
    )
    plan = construct(case)
    assert plan.updates <= 6 and plan.projection_calls <= 19
    assert plan.checked_bases_total <= 1197
    actual = magnitude(plan.strip.jet(plan.strip.length_mm)[0].translated(case.end, -1))
    assert actual == pytest.approx(plan.endpoint_gap_mm)
    assert plan.connected == (actual <= 1e-8)
    assert all(span.minimum_jacobian(plan.strip.half_width_mm) > 0 for span in plan.strip.spans)


def test_material_guide_control_points_retain_true_material_endpoints() -> None:
    """
    Each cubic guide starts and ends on its lane and has a valid knot count.
    """
    strip = _strip()
    for offset in (-strip.half_width_mm, 0.0, strip.half_width_mm):
        points, knots = spline_controls(strip, offset)
        assert points[0] == strip.jet(0, offset)[0]
        assert points[-1] == strip.jet(strip.length_mm, offset)[0]
        assert len(knots) == len(points) + 4
        assert list(knots) == sorted(knots)


def test_material_audit_keeps_exact_straight_control() -> None:
    """
    Existing analytic control geometry remains connected with no reference findings.
    """
    case = EndpointCase("synthetic-straight-material", ZERO, Vector3(74, 0, 0), X, X, Y, Y)
    plan = construct(case)
    row = audit(case, plan)
    assert plan.connected and plan.updates == 0
    assert row["analytic_common_material_lane_length_mm"] == pytest.approx(74)
    assert row["analytic_principal_curvature_ratio"] == 0
    assert row["findings"] == []
