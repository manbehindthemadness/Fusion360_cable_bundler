"""
Protect split-end size limits independently of native geometry success.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_diagnosis.compact import compact_cases, length_bounds
from experiments.experiment_ribbon_diagnosis.end_sections import CappedConnectionTurns
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import UnsafeRibbon, certify_curvature


@pytest.mark.parametrize("case", compact_cases(), ids=lambda case: case.name)
def test_each_end_is_bounded_without_overriding_curvature(case: RibbonStressCase) -> None:
    """
    Bound both ends and retain rejection when a prescribed 90-degree turn cannot fit.
    """
    policy = CappedConnectionTurns(case)
    trunk_lower, _ = length_bounds(case.route.curves)
    for sign in (-1, 1):
        route = policy(
            Vector3(0, 0, 0),
            Vector3(sign, 0, 0),
            Vector3(0, 0, sign),
            8 * case.lines * case.diameter_mm,
            f"end {sign}",
        )
        _, upper = length_bounds(route.curves)
        assert upper <= 0.06 * trunk_lower + 1e-9
        minimum_turn_length = math.pi / 2 * case.diameter_mm / 0.8
        if upper < minimum_turn_length:
            with pytest.raises(UnsafeRibbon):
                certify_curvature(route, case.diameter_mm)
        else:
            assert certify_curvature(route, case.diameter_mm).maximum_ratio <= 0.8
    assert len(policy.observations) == 2


def test_cap_does_not_lengthen_an_already_short_transition() -> None:
    """
    Six percent is a maximum, not a required target size.
    """
    policy = CappedConnectionTurns(compact_cases()[0])
    policy(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1), 0.001, "short")
    assert policy.observations[0]["radius_mm"] == 0.001
