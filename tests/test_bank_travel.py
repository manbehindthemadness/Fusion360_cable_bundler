"""
Verify bank budgeting, exact control preservation and ordered circular cap jets.
"""

import math

import pytest

from cable_bundler.routing.geometry import difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.bank_travel import travel_controls
from experiments.experiment_ribbon_cap_transition.distributed_bend import distributed_controls
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_lateral import lateral_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases
from experiments.experiment_ribbon_cap_transition.trace_diagnostic import (
    curvature_radius,
    shared_lane_jet,
)


@pytest.mark.parametrize(
    "case,bank_angle", ((reference_cases()[1], math.pi / 2), (lateral_cases()[-1], math.pi))
)
def test_budget_counts_entry_and_exit_bank_separately(
    case: EndpointCase, bank_angle: float
) -> None:
    """
    Equal endpoint roll does not erase the lateral turn's entry/exit bank motion.
    """
    _previous, baseline = distributed_controls(case)
    _points, metadata = travel_controls(case)
    assert metadata["bank_entry_radians"] + metadata["bank_exit_radians"] == pytest.approx(
        bank_angle
    )
    expected = baseline["minimum_envelope_radius_mm"] * bank_angle
    assert metadata["additional_bank_allowance_mm"] == pytest.approx(expected)
    assert metadata["nominal_travel_scale_mm"] == pytest.approx(baseline["cap_speed_mm"] + expected)


@pytest.mark.parametrize("case", (endpoint_cases()[0], reference_cases()[0]))
def test_zero_bank_controls_retain_exact_baseline_curve(case: EndpointCase) -> None:
    """
    Straight and planar-return polynomials are identical to the arc-jet baseline.
    """
    previous, _old = distributed_controls(case)
    points, metadata = travel_controls(case)
    assert points == previous
    assert metadata["additional_bank_allowance_mm"] == 0


@pytest.mark.parametrize("case", (reference_cases()[1], lateral_cases()[-1]))
def test_additional_travel_preserves_caps_and_lane_radius(case: EndpointCase) -> None:
    """
    Added nominal speed preserves every ordered cap and its previous circular radius.
    """
    _previous, baseline = distributed_controls(case)
    points, metadata = travel_controls(case)
    for u, endpoint, tangent, width in (
        (0.0, case.start, case.start_tangent, case.start_width),
        (1.0, case.end, case.end_tangent, case.end_width),
    ):
        for lane in range(case.lines):
            offset = (lane - (case.lines - 1) / 2) * case.diameter_mm
            position, velocity, acceleration = shared_lane_jet(points, u, offset)
            assert magnitude(difference(position, endpoint.translated(width, offset))) < 1e-8
            assert magnitude(difference(unit(velocity), tangent)) < 1e-8
            assert magnitude(velocity) == pytest.approx(
                metadata["nominal_travel_scale_mm"], abs=1e-6
            )
            assert curvature_radius(velocity, acceleration) == pytest.approx(
                baseline["cap_radius_mm"], abs=1e-5
            )
