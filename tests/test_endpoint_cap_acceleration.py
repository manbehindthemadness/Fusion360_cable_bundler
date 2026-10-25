"""
Verify zero cap-width derivatives and fixed ordered interpolation contracts.
"""

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.endpoint_cap_acceleration import (
    cap_acceleration_controls,
    cap_acceleration_paths,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    EndpointCase,
    derivative,
    endpoint_cases,
    evaluate,
)
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.trace_diagnostic import (
    curvature_radius,
    shared_lane_jet,
)
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1], reference_cases()[0]))
def test_all_cap_lanes_share_centerline_velocity_and_acceleration(case: EndpointCase) -> None:
    """
    Offset lanes inherit fixed cap positions, headings and centerline curvature.
    """
    points = cap_acceleration_controls(case)
    derivatives = [points]
    for _order in range(4):
        derivatives.append(derivative(derivatives[-1]))
    distance = magnitude(difference(case.end, case.start))
    zero = Vector3(0, 0, 0)
    for u, endpoint, heading, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        assert magnitude(evaluate(derivatives[3], u)) < 1e-7
        assert magnitude(evaluate(derivatives[4], u)) < 1e-6
        for lane in range(case.lines):
            offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
            position, velocity, acceleration = shared_lane_jet(points, u, offset)
            assert magnitude(difference(position, endpoint.translated(width, offset))) < 1e-8
            assert magnitude(difference(velocity, zero.translated(heading, distance))) < 1e-7
            assert (
                magnitude(
                    difference(acceleration, zero.translated(cross(width, heading), distance))
                )
                < 1e-6
            )
            assert curvature_radius(velocity, acceleration) == pytest.approx(distance, abs=1e-6)


@pytest.mark.parametrize("case", (endpoint_cases()[0], lateral_cases()[-1], reference_cases()[0]))
def test_paths_preserve_order_caps_and_c1(case: EndpointCase) -> None:
    """
    The unchanged cubic layout preserves all lanes, ordered targets and headings.
    """
    paths, points, _certificate = cap_acceleration_paths(case)
    assert len(points) == 10
    assert len(paths) == case.lines
    for number, path in enumerate(paths, 1):
        assert path.number == number
        assert len(path.controls) == 97
        assert len(path.knots) == 101
        offset = (number - 1 - (case.lines - 1) / 2) * case.diameter_mm
        for curve, u, endpoint, heading, width in (
            (path.curves[0], 0.0, case.start, case.start_tangent, case.start_width),
            (path.curves[-1], 1.0, case.end, case.end_tangent, case.end_width),
        ):
            assert magnitude(difference(curve.point(u), endpoint.translated(width, offset))) < 1e-8
            assert magnitude(difference(unit(curve.derivative(u)), heading)) < 1e-8
        for left, right in zip(path.curves, path.curves[1:]):
            assert left.end == right.start
            assert magnitude(difference(left.derivative(1), right.derivative(0))) < 1e-8


def test_uncertified_crossover_produces_no_trace_paths() -> None:
    """
    Valid cap jets cannot override the unchanged shared-path rejection guard.
    """
    with pytest.raises(UnsafeRibbon, match="uncertified at fixed depth; no repair"):
        cap_acceleration_paths(reference_cases()[1])
