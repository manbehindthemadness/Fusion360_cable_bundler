"""
Verify fixed cap jets and ordered analytic interpolation independently of builds.
"""

import pytest

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.endpoint_clamped import (
    analytic_paths,
    clamped_controls,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    EndpointCase,
    derivative,
    endpoint_cases,
    evaluate,
)
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.trace_diagnostic import shared_lane_jet


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1], reference_cases()[0]))
def test_all_offset_lanes_inherit_cap_headings(case: EndpointCase) -> None:
    """
    Both caps retain position/order, speed, curvature and stationary binormal.
    """
    points = clamped_controls(case)
    first = derivative(points)
    second = derivative(first)
    third = derivative(second)
    distance = magnitude(difference(case.end, case.start))
    zero = Vector3(0, 0, 0)
    for u, position, heading, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        assert magnitude(difference(evaluate(points, u), position)) < 1e-10
        assert magnitude(difference(evaluate(first, u), zero.translated(heading, distance))) < 1e-9
        expected_acceleration = zero.translated(cross(width, heading), distance)
        assert magnitude(difference(evaluate(second, u), expected_acceleration)) < 1e-8
        assert magnitude(evaluate(third, u)) < 1e-8
        for lane in range(case.lines):
            offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
            lane_position, velocity, _acceleration = shared_lane_jet(points, u, offset)
            assert magnitude(difference(lane_position, position.translated(width, offset))) < 1e-9
            assert magnitude(difference(unit(velocity), heading)) < 1e-9


@pytest.mark.parametrize(
    "case", (endpoint_cases()[0], reference_cases()[1], lateral_cases()[-1], reference_cases()[0])
)
def test_interpolation_preserves_all_lanes_caps_and_c1_jets(case: EndpointCase) -> None:
    """
    Analytic interpolation preserves ordered caps and shared tangent derivatives.
    """
    paths, _certificate = analytic_paths(case)
    assert len(paths) == case.lines
    for number, path in enumerate(paths, 1):
        assert path.number == number
        offset = (number - 1 - (case.lines - 1) / 2) * case.diameter_mm
        assert (
            magnitude(difference(path.controls[0], case.start.translated(case.start_width, offset)))
            < 1e-9
        )
        assert (
            magnitude(difference(path.controls[-1], case.end.translated(case.end_width, offset)))
            < 1e-9
        )
        assert len(path.controls) == 97
        assert len(path.knots) == 101
        for curve, u, heading in (
            (path.curves[0], 0.0, case.start_tangent),
            (path.curves[-1], 1.0, case.end_tangent),
        ):
            assert magnitude(difference(unit(curve.derivative(u)), heading)) < 1e-9
        for left, right in zip(path.curves, path.curves[1:]):
            assert left.end == right.start
            assert magnitude(difference(left.derivative(1), right.derivative(0))) < 1e-9
