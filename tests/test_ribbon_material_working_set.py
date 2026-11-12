"""
Retire only currently inactive guidance while preserving strict contact acceptance.
"""

from __future__ import annotations

import math
from typing import cast
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Side
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from experiments.experiment_ribbon_terminal_hardware.material_working_set import (
    InactiveGuidance,
    least_binding,
)


@pytest.mark.parametrize("scale", (0.01, 1.0, 100.0))
def test_release_uses_strict_current_material_gap_and_stable_slack_order(scale: float) -> None:
    """
    Reject violated, exact-boundary and nonfinite rows; preserve scale and first ties.
    """
    gaps_mm = (-1.0, 0.0, 1e-8, math.nan, math.inf, -math.inf, 0.2, 1.0, 1.0)
    bounds = [Mock(spec=MaterialConstraint) for _ in gaps_mm]
    for bound, gap_mm in zip(bounds, gaps_mm):
        bound.gap.return_value = gap_mm / scale
    constraints = [(cast(MaterialConstraint, bound), Side.AFTER) for bound in bounds]
    checkpoint = Mock()
    values = (0.2, 0.4)
    selected = least_binding(constraints, values, scale, checkpoint)
    assert selected == InactiveGuidance(7, 1.0 / scale)
    assert checkpoint.call_count == len(bounds)
    for bound in bounds:
        bound.gap.assert_called_once_with(values, Side.AFTER)
    assert len(constraints) == len(bounds)
    assert least_binding(constraints[:6], values, scale, Mock()) is None


def test_no_inactive_row_keeps_capacity_stop_and_checkpoint_interrupts_before_evaluation() -> None:
    """
    Empty or violated sets cannot free guidance; cancellation propagates without mutation.
    """
    bound = Mock(spec=MaterialConstraint)
    bound.gap.return_value = -0.2
    constraints = [(cast(MaterialConstraint, bound), Side.BEFORE)]
    assert least_binding([], (), 1.0, Mock()) is None
    assert least_binding(constraints, (), 1.0, Mock()) is None
    bound.gap.reset_mock()
    checkpoint = Mock(side_effect=TimeoutError("original recovery clock"))
    with pytest.raises(TimeoutError, match="original recovery clock"):
        least_binding(constraints, (), 1.0, checkpoint)
    bound.gap.assert_not_called()
    assert len(constraints) == 1
