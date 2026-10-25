"""
Verify direct interior pose constraints and preservation of all circular cap jets.
"""

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.coordinated_bend import coordinated_controls
from experiments.experiment_ribbon_cap_transition.distributed_bend import distributed_controls
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    EndpointCase,
    derivative,
    endpoint_cases,
    evaluate,
)
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1], reference_cases()[0]))
def test_direct_midpoint_constraints_preserve_four_cap_derivatives(case: EndpointCase) -> None:
    """
    The interior changes without moving caps or changing their first four jets.
    """
    points, metadata = coordinated_controls(case)
    previous, previous_metadata = distributed_controls(case)
    assert len(points) == 13
    current, original = points, previous
    for _order in range(5):
        for u in (0.0, 1.0):
            assert magnitude(difference(evaluate(current, u), evaluate(original, u))) < 1e-5
        if _order < 4:
            current, original = derivative(current), derivative(original)
    position, tangent, width = (
        metadata[key] for key in ("middle_position_mm", "middle_tangent", "middle_width")
    )
    assert isinstance(position, Vector3)
    assert isinstance(tangent, Vector3)
    assert isinstance(width, Vector3)
    velocity, acceleration = derivative(points), derivative(derivative(points))
    assert magnitude(difference(evaluate(points, 0.5), position)) < 1e-8
    assert (
        magnitude(
            difference(
                evaluate(velocity, 0.5),
                Vector3(0, 0, 0).translated(tangent, previous_metadata["cap_speed_mm"]),
            )
        )
        < 1e-7
    )
    assert abs(dot(evaluate(acceleration, 0.5), width)) < 1e-7
    assert abs(dot(evaluate(acceleration, 0.5), tangent)) < 1e-7
    assert magnitude(evaluate(acceleration, 0.5)) == pytest.approx(
        previous_metadata["cap_speed_mm"] ** 2 / previous_metadata["cap_radius_mm"], abs=1e-7
    )


def test_straight_control_keeps_original_exact_curve() -> None:
    """
    Straight geometry needs no artificial midpoint frame or extra polynomial degree.
    """
    case = endpoint_cases()[0]
    previous, _old = distributed_controls(case)
    points, metadata = coordinated_controls(case)
    assert points == previous
    assert metadata["nominal_turn_radians"] == 0


def test_undefined_middle_width_rejects_without_orientation_fallback() -> None:
    """
    A cancelling ordered-width average is unresolved rather than silently rerolled.
    """
    case = replace(endpoint_cases()[0], end_width=Vector3(0, -1, 0))
    with pytest.raises(ValueError, match="middle width is undefined"):
        coordinated_controls(case)
