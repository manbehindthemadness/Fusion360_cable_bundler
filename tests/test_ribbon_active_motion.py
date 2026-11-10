"""
Keep projected corrections consistent with exact active coordinate bounds at every motion scale.
"""

from __future__ import annotations

import math
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit


@pytest.mark.parametrize("residual", (1e-13, 1e-11, 1e-9))
@pytest.mark.parametrize("side", (-1, 1))
def test_tiny_outward_motion_is_frozen_without_blocking_the_feasible_correction(
    residual: float, side: int
) -> None:
    """
    Move a free coordinate to close the equation instead of letting bound dust force a zero step.
    """
    model = Mock(spec=MovableBends)
    model.straight_indices = (0,)
    model.bounds.side_effect = lambda i: (
        ((0.0, math.inf) if side == -1 else (-math.inf, 0.0)) if i == 0 else (-math.inf, math.inf)
    )
    values = (0.0, 0.0)
    direction = projected(model, values, [[1.0, 1.0]], [side * residual], [0.0, 0.0])
    assert direction is not None and direction[0] == 0.0
    assert direction[1] == pytest.approx(side * residual, rel=1e-12, abs=0.0)
    step = step_limit(model, values, direction, 1.0)
    assert step == 1.0
    after = advance(model, values, direction, step)
    assert math.fsum(after) == pytest.approx(side * residual, rel=1e-12, abs=0.0)


def test_small_legal_motion_from_nearby_interior_is_not_mistaken_for_an_active_bound() -> None:
    """
    Preserve an interior coordinate's legal tiny approach to its bound without clipping its equation.
    """
    model = Mock(spec=MovableBends)
    model.straight_indices = (0,)
    model.bounds.return_value = (0.0, math.inf)
    values = (1e-11,)
    direction = projected(model, values, [[1.0]], [-1e-11], [0.0])
    assert direction == (-1e-11,)
    assert advance(model, values, direction, step_limit(model, values, direction, 1.0)) == (0.0,)
