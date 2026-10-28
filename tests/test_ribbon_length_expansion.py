"""
Verify width-relative expansion and preservation of the fixed carrier during fitting.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart, length_expansion


def _case() -> EndpointCase:
    """
    Supply a neutral boundary with a known chord for transport tests.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("expansion", Vector3(0, 0, 0), Vector3(100, 0, 0), x, x, y, y)


def test_expansion_is_scale_relative_and_respects_existing_bounds() -> None:
    """
    Rigid scaling preserves ratios; reaching the search ceiling produces no duplicates.
    """
    case = _case()
    scaled = replace(case, end=Vector3(200, 0, 0), diameter_mm=2 * case.diameter_mm)
    assert length_expansion.expanded_ratios(case, 1) == length_expansion.expanded_ratios(scaled, 1)
    maximum = broad_chart.carrier_maximum(case)
    assert length_expansion.expanded_ratios(case, maximum) == (maximum,)
    with pytest.raises(ValueError):
        length_expansion.expanded_ratios(case, 0)


def test_closed_control_requires_no_fitting() -> None:
    """
    A closed neutral route retains exact coordinates and avoids numerical polishing.
    """
    values = (0.0,) * 9 + (1.0,)
    path, metrics = length_expansion.refine(_case(), values, 1, lambda: None)
    assert metrics["evaluations"] == 2 and metrics["trials"] == []
    assert metrics["coordinates"] == values
    assert path.states[-1][:3] == pytest.approx((100, 0, 0))


def test_shape_updates_cannot_spend_the_fixed_length() -> None:
    """
    Nontrivial fitting changes shape while retaining the prescribed expanded carrier.
    """
    values = (1.0,) + (0.0,) * 8 + (1.0,)
    _, metrics = length_expansion.refine(_case(), values, 1.2, lambda: None)
    assert metrics["trials"]
    assert all(t["coordinates"][9] == 1.2 for t in metrics["trials"])
    assert metrics["coordinates"][9] == 1.2 and metrics["evaluations"] <= 262
