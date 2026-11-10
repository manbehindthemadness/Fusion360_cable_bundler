"""
Verify bounded linear projection independently of ribbon route construction.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import active_projection
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


@pytest.mark.parametrize("exponent", (10, 40, 80))
def test_normalized_stopping_respects_the_original_raw_inequality_gate(exponent: int) -> None:
    """
    Equivalent scaled rows must not stop early and then fail the unchanged raw feasibility check.
    """
    scale = 2.0**exponent
    required = 2.0**-50
    rows = _caps() + [[0.0] * 6 + [-scale, 0.0]]
    residual = (0.0,) * 6 + (scale * required,)
    assert residual[-1] > 1e-14
    assert residual[-1] / scale < 1e-14
    step = active_step(_model(), (0.0,) * 8, rows, residual, lambda: None)
    assert step is not None and step[6] == required and step[7] == 0.0
    assert residual[-1] - scale * step[6] <= 1e-14


def test_unfinished_receipt_is_cleared_for_exact_inconsistency_and_cancellation() -> None:
    """
    Stale or interrupted algebra must never supply a partial-restoration direction.
    """
    receipt = active_projection.UnfinishedProjection((123.0,), "raw_inequality")
    rows = _caps() + [[0.0] * 6 + [-1.0, 0.0], [0.0] * 6 + [1.0, 0.0]]
    result = active_step(
        _model(),
        (0.0,) * 8,
        rows,
        (0.0,) * 6 + (1.0, 0.0),
        lambda: None,
        unfinished=receipt,
    )
    assert result is None and receipt.step is None and receipt.stop_reason is None
    receipt.step = (123.0,)
    assert (
        active_step(_model(), (0.0,) * 8, rows, (0.0,) * 8, lambda: None, unfinished=receipt)
        == (0.0,) * 8
    )
    assert receipt.step is None and receipt.stop_reason is None
    receipt.step = (123.0,)
    check = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        active_step(
            _model(),
            (0.0,) * 8,
            rows,
            (0.0,) * 8,
            check,
            unfinished=receipt,
        )
    assert receipt.step is None and receipt.stop_reason is None


def test_raw_inequality_rejection_retains_only_an_uncertified_receipt() -> None:
    """
    Keep the unchanged strict return gate while exposing its already-computed vector only on request.
    """
    rows = [[0.0] for _ in range(6)] + [[1.0]]
    residual = (0.0,) * 6 + (-1.0 + 5e-14,)
    assert active_projection._checked_step([1.0], [0.0], rows, residual) is None
    receipt = active_projection.UnfinishedProjection()
    assert active_projection._checked_step([1.0], [0.0], rows, residual, unfinished=receipt) is None
    assert receipt.step == (1.0,) and receipt.stop_reason == "raw_inequality"


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


@dataclass(frozen=True)
class _CapBounds:
    """
    Bound one coordinate in each coupled equality while leaving its partner free.
    """

    pairs: int

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Force each equality's initial least-norm correction onto a distinct upper bound.
        """
        return -math.inf, 0.0 if index < self.pairs else math.inf


@pytest.mark.parametrize("required_updates", (15, 16, 17))
@pytest.mark.parametrize("row_scale", (0.2, 1.0, 10.0))
def test_last_permitted_update_receives_the_same_final_feasibility_check(
    required_updates: int,
    row_scale: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Accept completion at update16 without permitting the17th independent bound update.
    """
    pairs = required_updates - 13
    solves = Mock(wraps=vars(active_projection)["_solve"])
    monkeypatch.setitem(vars(active_projection), "_solve", solves)
    size = 2 * pairs + 13
    rows = [
        [float(j in (i, pairs + i)) if i < pairs else 0.0 for j in range(size)] for i in range(6)
    ]
    rows += [[float(j == 2 * pairs + i) for j in range(size)] for i in range(13)]
    residual = (-2.0,) * pairs + (0.0,) * (6 - pairs) + (1.0,) * 13
    rows = [[entry * row_scale for entry in row] for row in rows]
    residual = tuple(term * row_scale for term in residual)
    step = active_step(_CapBounds(pairs), (0.0,) * size, rows, residual, lambda: None)
    assert solves.call_count <= 15
    if required_updates == 17:
        assert step is None
    else:
        assert step is not None
        assert step[:pairs] == pytest.approx((0.0,) * pairs, abs=1e-14)
        assert step[pairs : 2 * pairs] == pytest.approx((2.0,) * pairs, abs=1e-14)
        assert step[2 * pairs :] == (-1.0,) * 13
        actual = tuple(
            r + math.fsum(a * b for a, b in zip(row, step)) for row, r in zip(rows, residual)
        )
        assert max(map(abs, actual[:6])) <= 1e-14
        assert max(actual[6:]) <= 1e-14
