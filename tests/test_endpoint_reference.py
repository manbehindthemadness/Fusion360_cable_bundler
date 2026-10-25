"""
Check endpoint construction on reverse-heading and rolled reference challenges.
"""

import pytest

from cable_bundler.routing.geometry import cross, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    controls,
    derivative,
    evaluate,
)
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases


@pytest.mark.parametrize("index", range(3))
def test_reference_caps_retain_signed_width_and_heading(index: int) -> None:
    """
    Opposed and banked endpoint poses retain the prescribed binormal orientation.
    """
    case = reference_cases()[index]
    points = controls(case)
    velocity = derivative(points)
    acceleration = derivative(velocity)
    assert points[0] == case.start
    assert points[-1] == case.end
    for u, tangent, width in (
        (0, case.start_tangent, case.start_width),
        (1, case.end_tangent, case.end_width),
    ):
        actual_tangent = unit(evaluate(velocity, u))
        actual_width = unit(cross(evaluate(velocity, u), evaluate(acceleration, u)))
        assert magnitude(difference(actual_tangent, tangent)) < 1e-8
        assert magnitude(difference(actual_width, width)) < 1e-8
