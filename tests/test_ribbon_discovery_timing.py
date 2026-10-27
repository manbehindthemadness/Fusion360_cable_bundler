"""
Verify construction timing remains distinct from graphics and enforces the ratio.
"""

from __future__ import annotations

import pytest

from experiments.experiment_ribbon_route_discovery.timing import ConstructionTiming


@pytest.mark.parametrize("authoring,kernel,ceiling", [(0.2, 0.3, 0.5), (4.0, 6.0, 5.0)])
def test_measured_construction_limits_solve_and_matched_ratio(
    authoring: float, kernel: float, ceiling: float
) -> None:
    """
    Apply both the experimental cap and the user's own-candidate comparison.
    """
    measured = ConstructionTiming(authoring, kernel)
    assert measured.provisional_solve_ceiling == ceiling
    assert measured.allows(measured.construction_seconds)
    assert not measured.allows(measured.construction_seconds + 0.001)


@pytest.mark.parametrize("authoring,kernel", [(0, 0), (-1, 2), (1, float("nan"))])
def test_missing_or_invalid_construction_cannot_authorize_a_solve(
    authoring: float, kernel: float
) -> None:
    """
    Refuse to invent a positive solve budget from absent construction evidence.
    """
    with pytest.raises(ValueError):
        ConstructionTiming(authoring, kernel)
