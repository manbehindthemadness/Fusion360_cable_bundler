"""
Check coupled ribbon kinematics and direct fixed-pose closure independently of Fusion.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.coupled_motion import (
    ZERO,
    AngleLaw,
    CoupledMotion,
    orientation_angles,
    rotate,
)
from experiments.experiment_ribbon_cap_transition.coupled_route import (
    CoupledRejection,
    construct,
    spline_controls,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases

X, Y, Z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1)


def test_helical_motion_banks_while_bending_without_edgewise_curvature() -> None:
    """
    Analytic jets agree with position differences while the center leaves its plane.
    """
    motion = CoupledMotion(ZERO, X, Y, unit(X.translated(Y, 1)), math.pi / 2, 80)
    for u in (0.17, 0.5, 0.83):
        p, v, a = motion.jet(u)
        tangent, width = motion.frame(u)
        step = 1e-4
        before, after = motion.jet(u - step)[0], motion.jet(u + step)[0]
        numerical_velocity = ZERO.translated(difference(after, before), 1 / (2 * step))
        numerical_acceleration = ZERO.translated(
            after.translated(before, 1).translated(p, -2), 1 / step**2
        )
        assert magnitude(difference(v, numerical_velocity)) < 1e-5
        assert magnitude(difference(a, numerical_acceleration)) < 1e-4
        assert abs(dot(a, width)) < 1e-12
        assert abs(dot(tangent, width)) < 1e-12
    assert abs(motion.jet(1)[0].z) > 1
    assert magnitude(difference(motion.frame(1)[1], Y)) > 0.1
    for u in (0, 1):
        assert motion.angle_jet(u)[1:] == (0, 0)
        assert magnitude(motion.jet(u)[2]) == 0


@pytest.mark.parametrize("angle", (-1.2, 0.8))
def test_offset_lane_derivatives_include_width_motion(angle: float) -> None:
    """
    Edge acceleration includes both changing angular rate and rotating width.
    """
    motion = CoupledMotion(ZERO, X, Y, unit(X.translated(Y, -1)), angle, 75)
    u, step, offset = 0.37, 1e-4, 14.25
    p, v, a = motion.jet(u, offset)
    before, after = motion.jet(u - step, offset)[0], motion.jet(u + step, offset)[0]
    assert (
        magnitude(difference(v, ZERO.translated(difference(after, before), 1 / (2 * step)))) < 1e-5
    )
    numerical = ZERO.translated(after.translated(before, 1).translated(p, -2), 1 / step**2)
    assert magnitude(difference(a, numerical)) < 1e-4


@pytest.mark.parametrize(
    "angles", ((0.3, 1.1, -0.4), (-1.7, 0.8, 2.4), (0.6, 0, 0), (-0.3, math.pi, 0))
)
def test_orientation_factorization_reconstructs_ordered_frame(
    angles: tuple[float, float, float],
) -> None:
    """
    General and singular Euler branches retain both tangent and signed width.
    """
    tangent, width = X, Y
    for angle, sign in zip(angles, (1, -1, 1)):
        axis = unit(tangent.translated(width, sign))
        tangent, width = rotate(tangent, axis, angle), rotate(width, axis, angle)
    recovered = orientation_angles(X, Y, tangent, width)
    actual_tangent, actual_width = X, Y
    for angle, sign in zip(recovered, (1, -1, 1)):
        axis = unit(actual_tangent.translated(actual_width, sign))
        actual_tangent = rotate(actual_tangent, axis, angle)
        actual_width = rotate(actual_width, axis, angle)
    assert magnitude(difference(actual_tangent, tangent)) < 1e-8
    assert magnitude(difference(actual_width, width)) < 1e-8


def test_direct_length_solve_recovers_a_positive_fixed_pose() -> None:
    """
    Three position equations recover known travel without a shape search.
    """
    start, tangent, width = ZERO, X, Y
    expected_lengths = (50, 65, 80)
    for angle, sign, length in zip((0.6, 1.2, -0.9), (1, -1, 1), expected_lengths):
        motion = CoupledMotion(
            start, tangent, width, unit(tangent.translated(width, sign)), angle, length
        )
        start = motion.jet(1)[0]
        tangent, width = motion.frame(1)
    case = EndpointCase("synthetic-positive-inverse", ZERO, start, X, tangent, Y, width)
    motions = construct(case)
    assert [motion.length for motion in motions] == pytest.approx(expected_lengths, abs=1e-8)
    assert magnitude(difference(motions[-1].jet(1)[0], case.end)) < 1e-8
    for a, b in zip(motions, motions[1:]):
        assert magnitude(difference(a.jet(1)[0], b.jet(0)[0])) < 1e-8
        assert magnitude(cross(a.jet(1)[1], b.jet(0)[1])) < 1e-8
        assert magnitude(a.jet(1)[2]) == magnitude(b.jet(0)[2]) == 0
    points, knots = spline_controls(motions, 14.25)
    assert len(knots) == len(points) + 4
    assert points[0] == motions[0].jet(0, 14.25)[0]
    assert points[-1] == motions[-1].jet(1, 14.25)[0]


def test_controls_keep_exact_straight_and_circular_geometry() -> None:
    """
    New frame machinery preserves independent known geometries and their widths.
    """
    straight = construct(endpoint_cases()[0])
    assert sum(motion.length for motion in straight) == pytest.approx(80)
    assert all(motion.maximum_curvature() == 0 for motion in straight)
    loop = construct(reference_cases()[0])
    assert sum(motion.length for motion in loop) == pytest.approx(45 * math.pi)
    assert all(motion.maximum_curvature() == pytest.approx(1 / 45) for motion in loop)
    assert all(motion.law is AngleLaw.LINEAR for motion in loop)


def test_forbidden_axis_and_reverse_motion_are_rejected() -> None:
    """
    A sideways bend axis and negative travel cannot become accepted primitives.
    """
    with pytest.raises(ValueError, match="forbidden"):
        CoupledMotion(ZERO, X, Y, Z, 1, 50)
    with pytest.raises(ValueError, match="positive"):
        CoupledMotion(ZERO, X, Y, Y, 1, -50)


def test_singular_pose_does_not_fall_back_to_an_edgewise_bend() -> None:
    """
    An unchanged frame with lateral displacement rejects the fixed basis explicitly.
    """
    case = EndpointCase("singular-offset", ZERO, Vector3(80, 10, 0), X, X, Y, Y)
    with pytest.raises(CoupledRejection, match="singular"):
        construct(case)
    assert case.end == Vector3(80, 10, 0)


def test_nonpositive_length_solution_is_retained_as_rejection() -> None:
    """
    Direct position closure cannot reverse segment travel to manufacture a route.
    """
    endpoint, tangent, width = ZERO, X, Y
    for angle, sign, signed_length in zip((0.6, 1.2, -0.9), (1, -1, 1), (50, -65, 80)):
        motion = CoupledMotion(
            ZERO, tangent, width, unit(tangent.translated(width, sign)), angle, 1
        )
        endpoint = endpoint.translated(motion.displacement(1), signed_length)
        tangent, width = motion.frame(1)
    case = EndpointCase("negative-inverse", ZERO, endpoint, X, tangent, Y, width)
    with pytest.raises(CoupledRejection, match="nonpositive"):
        construct(case)
