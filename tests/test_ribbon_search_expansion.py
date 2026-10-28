"""
Verify expanded search bounds leave the material model and ordinary paths intact.
"""

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart
from experiments.experiment_ribbon_search_expansion import SearchDomain, refine


def _case() -> EndpointCase:
    """
    Define a fixed ordered terminal-pose challenge independent of saved failures.
    """
    return EndpointCase(
        "domain control",
        Vector3(0, 0, 0),
        Vector3(80, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        19,
        1.5,
    )


@pytest.mark.parametrize("factor", (1.0, 1.1, 1.25, 1.5, 2.0, 3.0))
def test_expansion_changes_only_search_bounds(factor: float) -> None:
    """
    Preserve exact geometry for shared coordinates while admitting longer carriers.
    """
    case = _case()
    domain = SearchDomain(factor)
    lower, upper = domain.bounds(case)
    old_lower, old_upper = broad_chart.bounds(case)
    assert lower == old_lower and upper[:9] == old_upper[:9]
    assert upper[9] == factor * old_upper[9]
    values = (1.0, -0.2, 0.1, 0.0, 0.1, 0.1, -0.2, 0.1, 0.0, 2.0)
    baseline = broad_chart.integrate(case, values, 64, lambda: None)
    expanded = domain.integrate(case, values, 64, lambda: None)
    assert expanded.states == baseline.states and expanded.rates == baseline.rates


def test_new_domain_admits_carriers_without_loosening_other_coordinates() -> None:
    """
    Reject an out-of-range bend even when the carrier allowance increases.
    """
    case = _case()
    values = (0.0,) * 9 + (1.5 * broad_chart.carrier_maximum(case),)
    with pytest.raises(ValueError, match="search domain"):
        SearchDomain().integrate(case, values, 64, lambda: None)
    path = SearchDomain(2).integrate(case, values, 64, lambda: None)
    assert path.field.carrier_length_mm > broad_chart.carrier_maximum(case) * 80
    with pytest.raises(ValueError, match="search domain"):
        SearchDomain(2).integrate(case, (20.0,) + values[1:], 64, lambda: None)


def test_domain_is_scale_relative_and_fit_work_is_bounded() -> None:
    """
    Preserve the dimensionless envelope and fit an ordinary terminal pose.
    """
    case = _case()
    other = replace(case, end=Vector3(800, 0, 0), diameter_mm=15)
    assert SearchDomain(1.25).maximum(case) == pytest.approx(SearchDomain(1.25).maximum(other))
    path, metrics = refine(case, (0.0,) * 9 + (1.0,), SearchDomain(2), lambda: None)
    assert metrics["evaluations"] <= 158 and len(path.states) == 513
    assert max(abs(v) for v in path.states[-1][:3]) == pytest.approx(80)


@pytest.mark.parametrize("factor", (0.0, 0.9, 3.1, float("nan"), float("inf")))
def test_invalid_expansions_are_rejected(factor: float) -> None:
    """
    Keep malformed or out-of-plan domains from reaching numerical transport.
    """
    with pytest.raises(ValueError, match="Search expansion"):
        SearchDomain(factor)
