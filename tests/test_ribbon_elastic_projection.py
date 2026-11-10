"""
Check bounded partial restoration without treating an unfinished linear correction as physical acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import elastic_projection
from experiments.experiment_ribbon_terminal_hardware.active_projection import (
    CoordinateBounds,
    active_step,
)


@dataclass(frozen=True)
class _Domain(CoordinateBounds):
    """
    Supply a typed analytical coordinate domain independently of ribbon geometry.
    """

    fixed: bool = False

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep two coordinates in the unit interval, or freeze every coordinate for impossible-motion checks.
        """
        if self.fixed:
            return 0.0, 0.0
        return (0.0, 1.0) if index in (0, 6) else (-math.inf, math.inf)


def _domain() -> CoordinateBounds:
    """
    Keep two synthetic coordinates in [0,1] with all other coordinates unbounded.
    """
    return _Domain()


def _caps() -> list[list[float]]:
    """
    Supply six independent analytical cap rows and two free material coordinates.
    """
    return [[float(i == j) for j in range(8)] for i in range(6)]


@pytest.mark.parametrize("initial", (0.3, 0.4, 0.5, 0.6))
def test_partial_restoration_reaches_nonlinear_root_when_full_newton_step_is_outside_bounds(
    initial: float,
) -> None:
    """
    x squared equals one is feasible at the exact upper bound despite an initially infeasible tangent step.
    """
    model = _domain()
    values = (initial,) + (0.0,) * 7
    rows = _caps() + [[0.0] * 8]
    rows[0][0] = 2 * initial
    residual = (initial**2 - 1,) + (0.0,) * 5 + (-1.0,)
    assert active_step(model, values, rows, residual, lambda: None) is None
    for _ in range(24):
        rows[0][0] = 2 * values[0]
        residual = (values[0] ** 2 - 1,) + (0.0,) * 5 + (-1.0,)
        if abs(residual[0]) < 1e-13:
            break
        step = elastic_projection.restoration_step(model, values, rows, residual, lambda: None)
        assert step is not None
        updated = tuple(a + b for a, b in zip(values, step))
        assert 0 <= updated[0] <= 1
        assert abs(updated[0] ** 2 - 1) < abs(residual[0])
        values = updated
    assert abs(values[0] ** 2 - 1) < 1e-13


def test_satisfied_inequality_stays_strict_while_a_violation_is_only_partially_reduced() -> None:
    """
    Incomplete clearance progress remains visibly incomplete and cannot cross a previously satisfied bound.
    """
    rows = _caps() + [[0.0] * 6 + [-1.0, 0.0], [0.0] * 6 + [1.0, 0.0]]
    residual = (0.0,) * 6 + (2.0, -0.25)
    step = elastic_projection.restoration_step(_domain(), (0.0,) * 8, rows, residual, lambda: None)
    assert step is not None
    assert 0 < step[6] <= 0.25
    assert 0 < residual[6] - step[6] < residual[6]
    assert residual[7] + step[6] <= 0


def test_no_available_bounded_motion_grants_no_correction() -> None:
    """
    A fixed coordinate cannot satisfy an impossible cap row through hidden slack acceptance.
    """
    model = _Domain(fixed=True)
    assert (
        elastic_projection.restoration_step(
            model, (0.0,) * 8, _caps() + [[0.0] * 8], (-1.0,) + (0.0,) * 5 + (-1.0,), lambda: None
        )
        is None
    )


def test_one_augmented_projection_reuses_the_original_rows_and_coordinate_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Add one slack without a second working-set solve, candidate enumeration or renewed caller allowance.
    """
    project = Mock(return_value=None)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.elastic_projection.active_step", project
    )
    model = _domain()
    rows = _caps() + [[0.0] * 8, [0.0] * 8]
    residual = (1.0, -2.0) + (0.0,) * 4 + (3.0, -0.25)
    values = (0.0,) * 8
    result = elastic_projection.restoration_step(model, values, rows, residual, lambda: None)
    assert result is None
    project.assert_called_once()
    domain, coordinates, matrix, terms, _ = project.call_args.args
    assert terms is residual and coordinates == values + (0.0,)
    assert [row[-1] for row in matrix] == [-r for r in residual[:6]] + [-3.0, 0.0]
    assert [row[:-1] for row in matrix] == rows
    assert domain.bounds(0) == model.bounds(0) and domain.bounds(8) == (0.0, 1.0)


def test_hard_cancellation_is_not_relabelled_as_no_progress() -> None:
    """
    Propagate the original source/resource stop through the unchanged projection checkpoint.
    """
    check = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        elastic_projection.restoration_step(
            _domain(), (0.0,) * 8, _caps() + [[0.0] * 8], (0.0,) * 7, check
        )


@pytest.mark.parametrize("count", (1, 5, 13))
def test_all_original_inequality_capacities_use_the_same_partial_projection(count: int) -> None:
    """
    Complete retained feature sets can reduce violations without changing the projection's row limit.
    """
    rows = _caps() + [[0.0] * 6 + [-1.0, 0.0] for _ in range(count)]
    residual = (0.0,) * 6 + (1.0,) * count
    step = elastic_projection.restoration_step(_domain(), (0.0,) * 8, rows, residual, lambda: None)
    assert step is not None and len(step) == 8
    assert 0 < step[6] <= 1
    assert 0 <= 1 - step[6] < 1


@pytest.mark.parametrize("count", (6, 20))
def test_physical_inequality_capacity_is_not_enlarged(count: int) -> None:
    """
    Preserve six caps and at most thirteen physical inequalities.
    """
    with pytest.raises(ValueError, match="thirteen"):
        elastic_projection.restoration_step(
            _domain(), (0.0,) * 8, [[0.0] * 8] * count, (0.0,) * count, lambda: None
        )
