"""
Verify fixed turning inputs and planar master sections without Fusion.
"""

import math

import pytest

from cable_bundler.routing.geometry import dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.fixtures import certificate_limit_case
from experiments.experiment_ribbon_cap_transition.master_frames import master_scaffold, sampled_roll
from experiments.experiment_ribbon_cap_transition.prescribed_twist import PrescribedTwistDiagnostic
from experiments.experiment_ribbon_cap_transition.turn_pair import (
    CERTIFICATE_RADIUS_MM,
    turn_fixtures,
)
from experiments.experiment_secure_discrete_ribbon.contract import (
    certify_curvature,
    discrete_profile_reach,
)


@pytest.mark.parametrize("index", (0, 1))
def test_fixed_turn_and_bounded_planar_scaffold(index: int) -> None:
    """
    Preserve parent arcs, certificate/material and perpendicular undeformed frames.
    """
    fixture = turn_fixtures()[index]
    case = fixture.case
    parent = certificate_limit_case(CERTIFICATE_RADIUS_MM)
    assert case.route.curves == parent.route.curves[: index + 1]
    assert case.end_boundary == parent.end_boundary
    assert (case.lines, case.diameter_mm) == (19, 1.5)
    start = unit(case.route.curves[0].derivative(0))
    end = unit(case.route.curves[-1].derivative(1))
    turn = math.degrees(math.acos(max(-1.0, min(1.0, dot(start, end)))))
    assert turn == pytest.approx(fixture.turn_degrees)
    assert fixture.requested_twist_degrees == 360
    assert fixture.actual_twist_degrees == 0
    certificate = certify_curvature(
        case.route, discrete_profile_reach(case.lines, case.diameter_mm)
    )
    assert certificate.maximum_ratio <= 0.8
    assert certificate.maximum_ratio > 0.7999
    scaffold = master_scaffold(
        case.route,
        case.start_width,
        case.end_width,
        28.5,
        twist=PrescribedTwistDiagnostic(fixture.actual_twist_degrees),
    )
    assert len(scaffold.frames) == 32
    assert sampled_roll(scaffold.frames)["net_roll_degrees"] == pytest.approx(0, abs=1e-8)
    for frame in scaffold.frames:
        assert magnitude(frame.width) == pytest.approx(1)
        assert magnitude(frame.thickness) == pytest.approx(1)
        assert dot(frame.width, frame.thickness) == pytest.approx(0, abs=1e-8)
        assert dot(frame.width, frame.tangent) == pytest.approx(0, abs=1e-8)
        assert dot(frame.thickness, frame.tangent) == pytest.approx(0, abs=1e-8)


def test_fixture_identity_is_stable_and_distinct() -> None:
    """
    Reauthoring cannot silently replace a case identity or conflate the two layouts.
    """
    first = turn_fixtures()
    assert first == turn_fixtures()
    assert first[0].case.route.cable_id != first[1].case.route.cable_id
