"""
Check analytic offset-lane derivatives used only in bounded diagnostics.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.trace_diagnostic import (
    curvature_radius,
    shared_lane_jet,
)


@pytest.mark.parametrize("u", [0, 0.3, 1])
def test_planar_parabola_lane_jet_is_an_exact_translation(u: float) -> None:
    """
    A constant-binormal offset changes position but not velocity or acceleration.
    """
    controls = tuple(Vector3(i / 5, 0, i * (i - 1) / 20) for i in range(6))
    position, velocity, acceleration = shared_lane_jet(controls, u, 2)
    assert magnitude(difference(position, Vector3(u, -2, u**2))) < 1e-10
    assert magnitude(difference(velocity, Vector3(1, 0, 2 * u))) < 1e-10
    assert magnitude(difference(acceleration, Vector3(0, 0, 2))) < 1e-10


def test_nonplanar_lane_derivatives_match_position_differences() -> None:
    """
    A changing binormal's analytic derivatives agree with independent differencing.
    """
    controls = tuple(Vector3(i / 5, i * (i - 1) / 20, i * (i - 1) * (i - 2) / 60) for i in range(6))
    u, step = 0.4, 0.0001
    center, velocity, acceleration = shared_lane_jet(controls, u, 0.2)
    left = shared_lane_jet(controls, u - step, 0.2)[0]
    right = shared_lane_jet(controls, u + step, 0.2)[0]
    measured_velocity = Vector3(0, 0, 0).translated(difference(right, left), 1 / (2 * step))
    measured_acceleration = (
        Vector3(0, 0, 0)
        .translated(difference(right, center), 1 / step**2)
        .translated(difference(left, center), 1 / step**2)
    )
    assert magnitude(difference(velocity, measured_velocity)) < 1e-6
    assert magnitude(difference(acceleration, measured_acceleration)) < 1e-5


def test_radius_handles_straight_and_zero_speed() -> None:
    """
    Straight points have infinite radius; singular parameterizations are rejected.
    """
    assert curvature_radius(Vector3(0, 2, 0), Vector3(-2, 0, 0)) == pytest.approx(2)
    assert math.isinf(curvature_radius(Vector3(1, 0, 0), Vector3(0, 0, 0)))
    with pytest.raises(ValueError, match="zero speed"):
        curvature_radius(Vector3(0, 0, 0), Vector3(1, 0, 0))
