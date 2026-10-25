"""
Verify exact circle construction, tangent closure and rational spline conversion.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.biarc_route import audit, biarc, rational_spline
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase, endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_reference import reference_cases


def _quarter_circle() -> EndpointCase:
    """
    Register a known45mm planar quarter-circle with compatible ordered widths.
    """
    return EndpointCase(
        "known_quarter",
        Vector3(0, 0, 0),
        Vector3(45, 45, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
    )


@pytest.mark.parametrize(
    "case", (_quarter_circle(), reference_cases()[0], endpoint_cases()[0], reference_cases()[1])
)
def test_biarc_preserves_positions_headings_and_join(case: EndpointCase) -> None:
    """
    One closed-form solution preserves both endpoints and the ordered G1 tangent.
    """
    arcs = biarc(case)
    assert arcs[0].start == case.start
    assert arcs[-1].end == case.end
    assert arcs[0].end == arcs[1].start
    assert magnitude(difference(arcs[0].tangent(0), case.start_tangent)) < 1e-8
    assert magnitude(difference(arcs[-1].tangent(1), case.end_tangent)) < 1e-8
    assert magnitude(difference(arcs[0].tangent(1), arcs[1].tangent(0))) < 1e-8


def test_known_circular_route_retains_radius_and_ribbon_findings() -> None:
    """
    Compatible planar circles pass named route checks; incompatible widths stay failed.
    """
    case = _quarter_circle()
    arcs = biarc(case)
    assert [arc.radius for arc in arcs] == pytest.approx([45, 45])
    record = audit(case, arcs)
    assert record["radius_ok"]
    assert record["hull_inside_sphere"]
    assert record["cap_width_rule_ok"]
    assert record["join_curvature_continuous"]
    spatial = reference_cases()[1]
    assert not audit(spatial, biarc(spatial))["cap_width_rule_ok"]


def test_rational_spans_are_exactly_on_the_known_circle() -> None:
    """
    Positive rational weights reproduce exact circular radii, without cubic fitting.
    """
    arcs = biarc(_quarter_circle())
    points, weights, knots = rational_spline(arcs)
    assert len(knots) == len(points) + 3
    assert min(weights) > 0
    for span in range((len(points) - 1) // 2):
        u = 0.37
        basis = ((1 - u) ** 2, 2 * u * (1 - u), u * u)
        coefficients = [basis[i] * weights[span * 2 + i] for i in range(3)]
        position = Vector3(0, 0, 0)
        for i, coefficient in enumerate(coefficients):
            position = position.translated(points[span * 2 + i], coefficient / sum(coefficients))
        assert magnitude(difference(position, Vector3(0, 45, 0))) == pytest.approx(45, abs=1e-10)
    straight = biarc(endpoint_cases()[0])
    assert all(math.isinf(arc.radius) for arc in straight)
