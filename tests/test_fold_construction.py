"""
Check explicit sweep construction bounds without weakening material-fold rules.
"""

import math

import pytest

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.construction import (
    ConstructionPolicy,
    enclosing_profile_radius,
)
from experiments.experiment_ribbon_fold_route.solver import FoldStrategy, construct_candidate
from tests.test_fold_route import CASES, _check


def test_spatial_sweep_policy_retains_targets_and_material_compatibility() -> None:
    """
    Prevent the observed local collapse while retaining the same gym boundary data.
    """
    case = CASES[0]
    baseline = construct_candidate(case, strategy=FoldStrategy.CONTINUOUS)
    route = construct_candidate(
        case,
        strategy=FoldStrategy.CONTINUOUS,
        construction=ConstructionPolicy.RIGID_PERPENDICULAR,
    )
    _check(route)
    assert route.targets == baseline.targets
    assert route.radius_mm > baseline.radius_mm
    rho = enclosing_profile_radius(case)
    assert baseline.radius_mm < rho
    for placed in route.pieces:
        piece = placed.geometry
        if isinstance(piece, CylindricalFold):
            low, high = piece.bend_interval(0)
            _, velocity, _, acceleration = placed.surface((low + high) / 2, 0)
            speed_squared = velocity.x**2 + velocity.y**2 + velocity.z**2
            curvature = math.sqrt(acceleration.x**2 + acceleration.y**2 + acceleration.z**2)
            assert rho * curvature / speed_squared < 0.996


@pytest.mark.parametrize("case_index", [1, 2])
def test_planar_and_straight_solutions_keep_their_original_tightness(case_index: int) -> None:
    """
    Avoid imposing the full-width orientation envelope on aligned planar sections.
    """
    case = CASES[case_index]
    assert construct_candidate(case) == construct_candidate(
        case, construction=ConstructionPolicy.RIGID_PERPENDICULAR
    )


def test_ambiguous_construction_policy_is_rejected() -> None:
    """
    Reject stale string settings rather than silently using a material-only route.
    """
    with pytest.raises(ValueError, match="ConstructionPolicy"):
        construct_candidate(CASES[0], construction="rigid_perpendicular")  # type: ignore[arg-type]
