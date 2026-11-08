"""
Verify bounded linear projection independently of ribbon route construction.
"""

from __future__ import annotations

import math
import random
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware.active_projection import active_step
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.quality_projection import quality_step


def _model() -> SignedJoints:
    """
    Supply an unconstrained coordinate boundary for analytical linear-only contracts.
    """
    model = Mock(spec=SignedJoints)
    model.bounds.side_effect = lambda i: (-math.inf, math.inf)
    return model


def _caps() -> list[list[float]]:
    """
    Fix six independent synthetic cap coordinates, leaving two linear degrees of freedom.
    """
    return [[float(i == j) for j in range(8)] for i in range(6)]


@pytest.mark.parametrize(
    "rows,residual,expected",
    (
        (((-1, 0), (0, -1)), (1, 1), (1, 1)),
        (((-1, 0), (0, -1), (-1, -1)), (1, 1, 3), (1.5, 1.5)),
        (((-1, -1), (0, 1)), (3, -0.5), (2.5, 0.5)),
        (((-1, 0), (-0.8, -0.6), (-0.8, 0.6)), (1, 0.99, 0.99), (1.2375, 0)),
        (((-1, 0), (1, 0)), (1, 0), None),
        (((-1, 0),), (1.5e-13,), (1.5e-13, 0)),
        (tuple((-1, 0) for _ in range(13)), tuple(range(1, 14)), (13, 0)),
    ),
)
def test_known_minimum_norm_projections_and_infeasibility(
    rows: tuple[tuple[float, float], ...],
    residual: tuple[float, ...],
    expected: tuple[float, float] | None,
) -> None:
    """
    Cover dependent bounds, removal of a previously active bound, and precision below the nonlinear goal.
    """
    actual = active_step(
        _model(),
        (0.0,) * 8,
        _caps() + [[0.0] * 6 + list(row) for row in rows],
        (0.0,) * 6 + residual,
        lambda: None,
    )
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert actual[:6] == (0.0,) * 6
        assert actual[-2:] == pytest.approx(expected, abs=1e-15)


def test_small_systems_match_the_existing_complete_subset_solution() -> None:
    """
    Check the new working-set method against the existing independent enumerator on32linear systems.
    """
    rng = random.Random(387411)
    for _ in range(32):
        witness = [rng.uniform(-3, 3), rng.uniform(-3, 3)]
        directions = [
            (math.cos(a), math.sin(a)) for a in (rng.uniform(-math.pi, math.pi) for _ in range(4))
        ]
        residual = (0.0,) * 6 + tuple(
            -sum(a * b for a, b in zip(row, witness)) - rng.uniform(0.01, 1) for row in directions
        )
        rows = _caps() + [[0.0] * 6 + list(row) for row in directions]
        model = _model()
        actual = active_step(model, (0.0,) * 8, rows, residual, lambda: None)
        expected = quality_step(model, (0.0,) * 8, rows, residual, lambda: None)
        assert expected is not None and actual is not None
        assert actual == pytest.approx(expected, abs=2e-10)


def test_native_coordinate_bounds_are_not_omitted() -> None:
    """
    A linear clearance requirement cannot bypass an incompatible coordinate upper bound.
    """
    model = Mock(spec=SignedJoints)
    model.bounds.side_effect = lambda i: (0, 2) if i == 6 else (-math.inf, math.inf)
    assert (
        active_step(
            model,
            (0.0,) * 8,
            _caps() + [[0.0] * 6 + [-1, 0]],
            (0.0,) * 6 + (3,),
            lambda: None,
        )
        is None
    )


def test_cancellation_is_not_reclassified_as_optional_infeasibility() -> None:
    """
    Propagate the caller's hard scheduling/source guard.
    """
    check = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        active_step(_model(), (0.0,) * 8, _caps() + [[0.0] * 8], (0.0,) * 7, check)


@pytest.mark.parametrize("count", (6, 20))
def test_linear_input_capacity_remains_finite(count: int) -> None:
    """
    Reject missing physical inequalities and over-capacity systems before working-set iteration.
    """
    with pytest.raises(ValueError, match="thirteen"):
        active_step(_model(), (0.0,) * 8, [[0.0] * 8] * count, (0.0,) * count, lambda: None)
