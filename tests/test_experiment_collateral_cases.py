"""
Protect stable collateral identities and differing mechanics without solving geometry.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import dot, unit
from experiments.experiment_ribbon_cap_transition.fixtures import development_cases
from experiments.experiment_ribbon_cap_transition.regression_cases import (
    PURPOSES,
    collateral_cases,
    comparison_cases,
)
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase


def test_collateral_registry_preserves_the_original_failure_and_controls() -> None:
    """
    Add three stable independent inputs, not three policies or reruns of one input.
    """
    cases = collateral_cases()
    assert cases == collateral_cases()
    assert tuple(case.name for case in cases) == tuple(PURPOSES)
    assert len({case.route.cable_id for case in cases}) == 3
    combined = comparison_cases()
    assert len(combined) == len({case.name for case in combined}) == 11
    assert combined[:8] == development_cases()
    assert combined[8:] == cases
    assert len(cases[0].route.curves) == 1
    assert len(cases[1].route.curves) == 2
    assert cases[2].route.curves[0].start != cases[0].route.curves[0].start


@pytest.mark.parametrize("case", collateral_cases(), ids=lambda case: case.name)
def test_material_and_cap_contracts_are_fixed(case: RibbonStressCase) -> None:
    """
    Preserve equal material/sphere scale and endpoint width-plane compatibility.
    """
    assert case.lines == 19 and case.diameter_mm == 1.5
    assert case.end_boundary.diameter_mm == 5 * case.lines * case.diameter_mm
    for width, tangent in (
        (case.start_width, case.route.curves[0].derivative(0)),
        (case.end_width, case.route.curves[-1].derivative(1)),
    ):
        assert abs(dot(unit(width), unit(tangent))) < 1e-10
