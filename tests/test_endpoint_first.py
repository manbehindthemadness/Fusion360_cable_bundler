"""
Check endpoint construction contracts without claiming native geometry coverage.
"""

from dataclasses import replace

import pytest

from cable_bundler.domain import CableGroupType
from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude
from experiments.experiment_ribbon_cap_transition.endpoint_first import (
    EndpointCase,
    certify,
    construct,
    controls,
    derivative,
    endpoint_cases,
    evaluate,
    ribbon_group,
)
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon


@pytest.mark.parametrize("case", endpoint_cases(), ids=lambda case: case.name)
def test_exact_endpoint_jets(case: EndpointCase) -> None:
    """
    Fixed poses determine positions, tangents and signed bend binormals.
    """
    points = controls(case)
    first, second = derivative(points), derivative(derivative(points))
    assert points[0] == case.start
    assert points[-1] == case.end
    for u, tangent, width in (
        (0, case.start_tangent, case.start_width),
        (1, case.end_tangent, case.end_width),
    ):
        assert magnitude(cross(evaluate(first, u), tangent)) < 1e-8
        bend = cross(evaluate(first, u), evaluate(second, u))
        if case.name != "control":
            assert magnitude(cross(bend, width)) < 1e-8


def test_straight_control_and_containment_rejection() -> None:
    """
    An independently dimensioned straight ribbon retains order and equal lanes.
    """
    case = replace(endpoint_cases()[0], start=Vector3(-25, 0, 0), end=Vector3(25, 0, 0), lines=11)
    frames, report = construct(case)
    assert frames[0].origin == case.start
    assert frames[-1].origin == case.end
    assert all(magnitude(difference(f.width, case.start_width)) < 1e-10 for f in frames)
    assert report["sampled_length_spread"] == pytest.approx(0)
    with pytest.raises(UnsafeRibbon, match="uncertified"):
        certify(controls(case), 1, Vector3(0, 0, 0), 10)


def test_reject_bad_poses_and_singular_cusp() -> None:
    """
    Invalid input and a polynomial with zero speed never acquire fallback frames.
    """
    case = endpoint_cases()[0]
    with pytest.raises(ValueError, match="perpendicular"):
        controls(replace(case, start_width=case.start_tangent))
    with pytest.raises(UnsafeRibbon, match="Coincident"):
        controls(replace(case, end=case.start))
    with pytest.raises(UnsafeRibbon, match="uncertified"):
        certify((Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 0)), 1, Vector3(0, 0, 0), 10)


def test_native_profile_metadata_uses_ribbon_construction() -> None:
    """
    Native profile setup accepts a nondefault line count without loose-wire validation.
    """
    case = replace(endpoint_cases()[0], lines=11, diameter_mm=2)
    group = ribbon_group(case)
    assert group.group_type is CableGroupType.RIBBON
    assert group.ribbon_lines == 11
    assert group.diameter_mm == 2
    assert group.cable_group_id == ribbon_group(case).cable_group_id


def test_curved_certificate_bounds_known_midpoint_curvature() -> None:
    """
    Subdivision retains a conservative bound for a nonstraight regular cubic.
    """
    points = (
        Vector3(0, 0, 0),
        Vector3(0, 0, 100),
        Vector3(100, 0, 100),
        Vector3(100, 0, 0),
    )
    certificate = certify(points, 1, Vector3(50, 0, 50), 200)
    assert certificate["certified_intervals"] > 1
    assert 8 / 300 <= certificate["maximum_ratio"] <= 0.8
