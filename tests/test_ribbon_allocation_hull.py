"""
Check negative convex travel certificates against analytical feasible allocations and residual slack.
"""

from __future__ import annotations

import math
import random

import pytest

from experiments.experiment_ribbon_feature_insertion.allocation_bounds import StraightReach
from experiments.experiment_ribbon_feature_insertion.allocation_hull import separate


@pytest.mark.parametrize("angle", (0.0, 0.37, 1.8))
def test_oblique_separation_with_overlapping_coordinate_ranges(angle: float) -> None:
    """
    A rotated simplex facet separates unreachable travel without requiring a world-axis special case.
    """
    c, s = math.cos(angle), math.sin(angle)
    rows = ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    right = (0.6 * (c - s), 0.6 * (s + c), 0.6)
    reach = StraightReach(rows, right, 1.0)
    certificate = separate(reach, lambda: None)
    assert certificate is not None
    assert 0 < certificate.distance_lower_bound <= math.sqrt(3) * 0.6
    assert (
        certificate.target[1] < certificate.travel[0]
        or certificate.target[0] > certificate.travel[1]
    )
    if angle == 0:
        assert not reach.excludes((0, 1, 2))


@pytest.mark.parametrize("scale", (1e-200, 1e-9, 1.0, 1e8, 1e100))
def test_feasible_travel_and_original_slack_never_separate(scale: float) -> None:
    """
    Preserve actual nonnegative allocations, including active sum faces and component residual allowance.
    """
    generator = random.Random(2644)
    for size in range(1, 8):
        for _ in range(8):
            rows = tuple(tuple(generator.uniform(-2, 2) for _ in range(size)) for _ in range(3))
            values = tuple(generator.random() * scale for _ in range(size))
            budget = math.fsum(values)
            right = tuple(math.fsum(a * b for a, b in zip(row, values)) for row in rows)
            perturbed = tuple(value + 1e-8 for value in right)
            assert separate(StraightReach(rows, perturbed, budget), lambda: None) is None
    rows = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    assert separate(StraightReach(rows, (1.0 + 2e-8, 1e-8, 1e-8), 1.0), lambda: None) is None


def test_degenerate_overflow_unbounded_and_checkpoint_behavior() -> None:
    """
    Uncertain support declines acceleration; cancellation always propagates before certificate work.
    """
    rows = ((1e308, 0.0, 0.0), (0.0, 1e308, 0.0), (0.0, 0.0, 1e308))
    assert separate(StraightReach(rows, (-1e308,) * 3, 1e308), lambda: None) is None
    assert separate(StraightReach(rows, (1.0,) * 3, None), lambda: None) is None
    assert separate(StraightReach(((0.0,),) * 3, (1.0,) * 3, 1.0), lambda: None) is None

    def stop() -> None:
        """
        Model the original caller's cancellation guard.
        """
        raise TimeoutError("original guard")

    with pytest.raises(TimeoutError, match="original guard"):
        separate(StraightReach(rows, (1.0,) * 3, 1.0), stop)
