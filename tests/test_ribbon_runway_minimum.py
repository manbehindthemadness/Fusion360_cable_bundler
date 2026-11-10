"""
Verify bounded multidimensional runway minimization using analytical linear systems.
"""

from __future__ import annotations

import math
import random
from functools import cached_property
from itertools import combinations
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import straight_projection
from experiments.experiment_ribbon_terminal_hardware.active_projection import active_step
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.runway_minimum import LinearMinimum, minimize
from experiments.experiment_ribbon_terminal_hardware.straight_projection import shortest_run_step


class _Slots(SignedJoints):
    """
    Expose only analytical nonnegative runway coordinates, with no route construction.
    """

    _size: int

    def __init__(self, size: int) -> None:
        """
        Retain the dimension of one exact linear control independently of Fusion.
        """
        object.__setattr__(self, "_size", size)

    @cached_property
    def indices(self) -> tuple[int, ...]:
        """
        Identify every coordinate as a runway rather than a bend parameter.
        """
        return tuple(4 * i for i in range(self._size))

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep each independent runway nonnegative without a new physical length ceiling.
        """
        return 0.0, math.inf

    @cached_property
    def scale(self) -> float:
        """
        Interpret analytical coordinates as millimetres for optional evidence only.
        """
        return 1.0


@pytest.mark.parametrize("nullity", (1, 2, 3, 4, 6))
def test_clearance_uses_the_shortest_runways_in_each_supported_dimension(nullity: int) -> None:
    """
    Use the efficient slot, remove spare travel and preserve the independent cap equality exactly.
    """
    size = nullity + 1
    values = (1.0,) * size
    feature = [0.0, -2.0] + ([-1.0] if nullity > 1 else []) + [0.0] * max(0, nullity - 2)
    rows = [[1.0] + [0.0] * nullity] + [[0.0] * size for _ in range(5)] + [feature]
    residual = (0.0,) * 6 + (3.0 + sum(feature),)
    step = shortest_run_step(_Slots(size), values, rows, residual, lambda: None)
    evidence = straight_projection.RunwayEvidence()
    assert (
        shortest_run_step(_Slots(size), values, rows, residual, lambda: None, evidence=evidence)
        == step
    )
    if nullity == 2:
        assert evidence == straight_projection.RunwayEvidence()
    else:
        assert evidence.attempts == evidence.minima == 1 and evidence.retained_feasible == 0
        assert evidence.maximum_nullity == nullity and evidence.linear_saving_mm >= 0
    assert step is not None
    trial = tuple(a + b for a, b in zip(values, step))
    assert trial == pytest.approx((1.0, 1.5) + (0.0,) * (nullity - 1), abs=1e-14)
    assert trial[0] == 1.0 and all(value == 0.0 for value in trial[2:])
    assert residual[-1] + sum(a * b for a, b in zip(feature, step)) <= 1e-14


def test_redundant_faces_do_not_obstruct_the_minimum() -> None:
    """
    Reach the cheapest endpoint without giving duplicated inequalities extra influence.
    """
    rows = [[-1.0, 0.0], [0.0, -1.0], [1.0, 1.0], [-1.0, 0.0]]
    result = minimize([1.0, 2.0], rows, [0.0, 0.0, 3.0, 0.0], [1.0, 1.0], lambda: None)
    assert result is not None and result.point == pytest.approx((0.0, 0.0), abs=1e-14)
    assert all(
        sum(a * b for a, b in zip(row, result.point)) <= bound + 1e-14
        for row, bound in zip(rows, [0, 0, 3, 0])
    )


def test_pivot_limit_and_unbounded_or_inconsistent_systems_decline_without_search() -> None:
    """
    Do not label unfinished or unsupported algebra as a minimum or expand the finite pivot count.
    """
    size = 20
    rows = [[-float(i == j) for i in range(size)] for j in range(size)]
    checkpoint = Mock()
    assert (
        minimize([float(i + 1) for i in range(size)], rows, [0.0] * size, [1.0] * size, checkpoint)
        is None
    )
    assert checkpoint.call_count <= size + 16 * (size + 1)
    assert minimize([1.0], [], [], [0.0], lambda: None) is None
    assert minimize([1.0], [[1.0]], [-1.0], [0.0], lambda: None) is None
    assert minimize([math.nan], [[1.0]], [1.0], [0.0], lambda: None) is None


def test_zero_objective_and_hard_cancellation_have_distinct_dispositions() -> None:
    """
    Preserve an already stationary point while propagating the caller's resource stop.
    """
    result = minimize([0.0], [[1.0]], [1.0], [0.5], lambda: None)
    assert result is not None and result.point == (0.5,)
    with pytest.raises(RuntimeError, match="source drift"):
        minimize([1.0], [[-1.0]], [0.0], [1.0], Mock(side_effect=RuntimeError("source drift")))


@pytest.mark.parametrize("disposition", ("declined", "raw_gate", "interrupted"))
def test_declined_minimization_retains_one_original_feasible_projection(
    monkeypatch: pytest.MonkeyPatch,
    disposition: str,
) -> None:
    """
    Optimization exhaustion cannot create another feasibility solve or replace the original vector.
    """
    model = _Slots(4)
    values = (1.0,) * 4
    rows = [[1.0, 0.0, 0.0, 0.0]] + [[0.0] * 4 for _ in range(5)] + [[0.0, -2.0, -1.0, 0.0]]
    residual = (0.0,) * 6 + (1.0,)
    expected = active_step(model, values, rows, residual, lambda: None)
    project = Mock(wraps=active_step)
    minimum = Mock(
        return_value=LinearMinimum((0.0,) * 3, frozenset()) if disposition == "raw_gate" else None,
        side_effect=RuntimeError("clock stop") if disposition == "interrupted" else None,
    )
    monkeypatch.setitem(vars(straight_projection), "active_step", project)
    monkeypatch.setitem(vars(straight_projection), "minimize", minimum)
    evidence = straight_projection.RunwayEvidence()
    if disposition == "interrupted":
        with pytest.raises(RuntimeError, match="clock stop"):
            shortest_run_step(model, values, rows, residual, lambda: None, evidence=evidence)
    else:
        assert (
            shortest_run_step(model, values, rows, residual, lambda: None, evidence=evidence)
            == expected
        )
    assert evidence.attempts == 1 and evidence.minima == 0
    assert evidence.retained_feasible == int(disposition != "interrupted")
    assert evidence.linear_saving_mm == 0.0
    project.assert_called_once()
    minimum.assert_called_once()


@pytest.mark.parametrize(
    "rows,bounds,point", (([[1.0, 2.0]], [0.0], [0.0]), ([[1.0]], [], [0.0]), ([[1.0]], [0.0], []))
)
def test_malformed_linear_contract_is_rejected(
    rows: list[list[float]], bounds: list[float], point: list[float]
) -> None:
    """
    Reject mismatched coefficient, bound and point dimensions before optimization.
    """
    with pytest.raises(ValueError, match="Match"):
        minimize([1.0], rows, bounds, point, lambda: None)


def _determinant(matrix: list[list[float]]) -> float:
    """
    Evaluate tiny analytical determinants independently of the production affine solver.
    """
    if not matrix:
        return 1.0
    return sum(
        (-1) ** column
        * value
        * _determinant([row[:column] + row[column + 1 :] for row in matrix[1:]])
        for column, value in enumerate(matrix[0])
    )


@pytest.mark.parametrize("size", (1, 2, 3, 4))
def test_bounded_face_minimum_matches_independent_vertex_enumeration(size: int) -> None:
    """
    Compare twenty seeded analytical box-and-oblique polytopes with Cramer's-rule vertices.
    """
    rng = random.Random(1921 + size)
    for _ in range(5):
        rows = [
            [sign * float(i == j) for i in range(size)] for j in range(size) for sign in (-1.0, 1.0)
        ]
        bounds = [bound for _j in range(size) for bound in (0.0, 1.0)]
        for _cut in range(3):
            row = [rng.uniform(-1, 1) for _i in range(size)]
            rows.append(row)
            bounds.append(0.5 * sum(row) + rng.uniform(0.1, 0.5))
        objective = [rng.uniform(-1, 1) for _i in range(size)]
        costs: list[float] = []
        for selected in combinations(range(len(rows)), size):
            matrix = [rows[i] for i in selected]
            determinant = _determinant(matrix)
            if abs(determinant) < 1e-10:
                continue
            right = [bounds[i] for i in selected]
            point = [
                _determinant(
                    [
                        row[:column] + [value] + row[column + 1 :]
                        for row, value in zip(matrix, right)
                    ]
                )
                / determinant
                for column in range(size)
            ]
            if all(
                sum(a * b for a, b in zip(row, point)) <= bound + 1e-9
                for row, bound in zip(rows, bounds)
            ):
                costs.append(sum(a * b for a, b in zip(objective, point)))
        result = minimize(objective, rows, bounds, [0.5] * size, lambda: None)
        assert result is not None and costs
        assert sum(a * b for a, b in zip(objective, result.point)) == pytest.approx(
            min(costs), abs=1e-9
        )
