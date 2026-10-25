"""
Check circular cap derivatives, width dependence and the shared straight adapter.
"""

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.analytic_scaffold import scaffold_paths
from experiments.experiment_ribbon_cap_transition.distributed_bend import distributed_controls
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.trace_diagnostic import (
    curvature_radius,
    shared_lane_jet,
)


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1], reference_cases()[0]))
def test_circular_caps_preserve_lane_headings_and_curvature(case: EndpointCase) -> None:
    """
    Nonzero circular jerk/snap keep the binormal stationary through second order.
    """
    points, metadata = distributed_controls(case)
    for u, endpoint, heading, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        _p, center_velocity, center_acceleration = shared_lane_jet(points, u, 0)
        for lane in range(case.lines):
            offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
            position, velocity, acceleration = shared_lane_jet(points, u, offset)
            assert magnitude(difference(position, endpoint.translated(width, offset))) < 1e-8
            assert magnitude(difference(unit(velocity), heading)) < 1e-8
            assert magnitude(difference(velocity, center_velocity)) < 1e-6
            assert magnitude(difference(acceleration, center_acceleration)) < 1e-5
            assert curvature_radius(velocity, acceleration) == pytest.approx(
                metadata["cap_radius_mm"], abs=1e-5
            )


def test_width_can_set_radius_without_moving_endpoint_poses() -> None:
    """
    A sufficiently wide input raises the nominal radius to the envelope requirement.
    """
    case = reference_cases()[1]
    _ordinary, narrow = distributed_controls(case)
    points, wide = distributed_controls(replace(case, lines=101))
    assert wide["cap_radius_mm"] > narrow["cap_radius_mm"]
    assert wide["cap_radius_mm"] == wide["minimum_envelope_radius_mm"]
    assert points[0] == case.start
    assert points[-1] == case.end


def test_singular_full_turn_chord_rule_rejects_without_fallback() -> None:
    """
    Opposed chord approaches cannot request an infinite circular-chord radius.
    """
    case = replace(
        endpoint_cases()[0], start_tangent=Vector3(-1, 0, 0), end_tangent=Vector3(-1, 0, 0)
    )
    with pytest.raises(ValueError, match="singular nominal turn"):
        distributed_controls(case)


def test_straight_scaffold_preserves_order_and_c1_paths() -> None:
    """
    Exact straight interpolation needs no bend-frame fallback or extra geometry.
    """
    case = endpoint_cases()[0]
    points, metadata = distributed_controls(case)
    paths, _certificate = scaffold_paths(case, points)
    assert metadata["nominal_turn_radians"] == 0
    assert len(paths) == case.lines
    for number, path in enumerate(paths, 1):
        assert path.number == number
        assert len(path.controls) == 97
        assert len(path.knots) == 101
        assert magnitude(difference(unit(path.curves[0].derivative(0)), Vector3(1, 0, 0))) < 1e-8
        for left, right in zip(path.curves, path.curves[1:]):
            assert left.end == right.start
            assert magnitude(difference(left.derivative(1), right.derivative(0))) < 1e-8
