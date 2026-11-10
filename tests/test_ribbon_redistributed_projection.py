"""
Test independent cap-error restoration with analytical bounds and strict physical rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import redistributed_projection
from experiments.experiment_ribbon_terminal_hardware.active_projection import CoordinateBounds
from experiments.experiment_ribbon_terminal_hardware.elastic_projection import restoration_step


@dataclass(frozen=True)
class _Domain(CoordinateBounds):
    """
    Bound each analytical geometry coordinate to a closed unit interval.
    """

    high: float = 1.0

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Supply identical finite bounds for independently indexed coordinates.
        """
        return 0.0, self.high


@dataclass(frozen=True)
class _CrowdedDomain(CoordinateBounds):
    """
    Keep many analytical coordinates fixed while leaving the last coordinate free for restoration.
    """

    free_index: int

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Expose original geometric bounds independently of the projector's numerical residual variables.
        """
        return (0.0, 1.0) if index == self.free_index else (0.0, 0.0)


class _RunwayDomain(CoordinateBounds):
    """
    Keep one nonnegative geometric slot while leaving analytical cap-compensation coordinates free.
    """

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Preserve the zero runway bound independently of the numerical projection metric.
        """
        return (0.0, 1.0) if index == 0 else (-float("inf"), float("inf"))


@pytest.mark.parametrize("error", (1e-8, 2e-8, 5e-8))
def test_small_projection_metric_cannot_leave_an_outward_zero_runway_step(error: float) -> None:
    """
    Project amplified bound roundoff before a tiny outward coordinate can freeze all useful cap compensation.
    """
    values = (1e-20, 0.0, 0.0)
    rows = [[1.0, -1.0, 0.0], [0.0, 1.0, 1.0]] + [[0.0] * 3 for _ in range(5)]
    residual = (error, -0.1 * error) + (0.0,) * 4 + (-1.0,)
    feasible = (0.0, error, -0.9 * error)
    assert all(
        abs(r + sum(a * b for a, b in zip(row, feasible))) < error * 1e-14
        for row, r in zip(rows[:6], residual[:6])
    )
    evidence = redistributed_projection.ProjectionEvidence()
    step = redistributed_projection.redistributed_step(
        _RunwayDomain(), values, rows, residual, lambda: None, evidence=evidence
    )
    assert step is not None and values[0] + step[0] == 0.0
    predicted = [r + sum(a * b for a, b in zip(row, step)) for row, r in zip(rows, residual)]
    assert max(map(abs, predicted[:6])) < error
    assert predicted[6] <= 0.0
    assert evidence.bound_clipped_proposals == 1 and evidence.exhaustions == 0


@pytest.mark.parametrize("fixed_count", (18, 22))
def test_exhausted_working_set_can_retain_useful_bounded_restoration(fixed_count: int) -> None:
    """
    A finite projection must not discard usable motion merely because many fixed coordinates need pivots.
    """
    size = fixed_count + 1
    rows = [[-1.0] * size] + [[0.0] * size for _ in range(6)]
    residual = (1.0,) + (0.0,) * 5 + (-1.0,)
    evidence = redistributed_projection.ProjectionEvidence()
    step = redistributed_projection.redistributed_step(
        _CrowdedDomain(fixed_count),
        (0.0,) * size,
        rows,
        residual,
        lambda: None,
        evidence=evidence,
    )
    assert step is not None and step[:-1] == (0.0,) * fixed_count
    assert 0 < step[-1] <= 1.0 and 0 <= 1.0 - step[-1] < 1.0
    assert evidence.exhaustions == evidence.bounded_proposals == 1


@pytest.mark.parametrize("physical_residual", (-0.1, 0.1))
@pytest.mark.parametrize("reason", ("working_set_limit", "raw_inequality"))
def test_unfinished_box_projection_preserves_a_physical_row(
    monkeypatch: pytest.MonkeyPatch,
    physical_residual: float,
    reason: str,
) -> None:
    """
    A useful cap correction cannot cross satisfied clearance or enlarge an existing violation.
    """

    def declined(*args: object, **kwargs: object) -> tuple[float, ...] | None:
        """
        Supply an unfinished algebraic vector without declaring feasibility.
        """
        receipt = kwargs["unfinished"]
        assert isinstance(receipt, redistributed_projection.UnfinishedProjection)
        if reason == "raw_inequality":
            from experiments.experiment_ribbon_terminal_hardware.active_projection import (
                _checked_step,
            )

            matrix, terms = args[2], args[3]
            assert isinstance(matrix, list) and isinstance(terms, tuple)
            return _checked_step([0.5] + [0.0] * 7, [0.0] * 8, matrix, terms, unfinished=receipt)
        receipt.step = (0.5,) + (0.0,) * 7
        receipt.stop_reason = "working_set_limit"
        return None

    project = Mock(side_effect=declined)
    monkeypatch.setitem(vars(redistributed_projection), "active_step", project)
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]]
    evidence = redistributed_projection.ProjectionEvidence()
    result = redistributed_projection.redistributed_step(
        _Domain(),
        (0.0,),
        rows,
        (1.0,) + (0.0,) * 5 + (physical_residual,),
        lambda: None,
        evidence=evidence,
    )
    assert evidence.exhaustions == int(reason == "working_set_limit")
    assert evidence.raw_gate_rejections == int(reason == "raw_inequality")
    if physical_residual > 0:
        assert result is None and evidence.bounded_proposals == 0
    else:
        assert result is not None and 0 < result[0] <= -physical_residual + 1e-14
        assert evidence.bounded_proposals == evidence.halfspace_contracted_proposals == 1
    project.assert_called_once()


@pytest.mark.parametrize("offered", (0.1 + 2e-13, 0.5))
def test_one_ray_contraction_retains_all_original_halfspaces_without_another_projection(
    monkeypatch: pytest.MonkeyPatch, offered: float
) -> None:
    """
    Preserve simultaneous satisfied/violated rows using the same vector and original projector count.
    """
    project = Mock(return_value=(offered,) + (0.0,) * 7)
    monkeypatch.setitem(vars(redistributed_projection), "active_step", project)
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0], [1.0], [-1.0]]
    residual = (1.0,) + (0.0,) * 5 + (-0.4, -0.1, 0.2)
    evidence = redistributed_projection.ProjectionEvidence()
    result = redistributed_projection.redistributed_step(
        _Domain(), (0.0,), rows, residual, lambda: None, evidence=evidence
    )
    assert result is not None and 0 < result[0] <= 0.1 + 1e-14
    assert 1.0 - result[0] < 1.0 and 0.2 - result[0] < 0.2
    assert all(
        r + row[0] * result[0] - max(0.0, r) <= 1e-14 for row, r in zip(rows[6:], residual[6:])
    )
    assert evidence.halfspace_contracted_proposals == 1
    project.assert_called_once()


def test_already_feasible_vector_is_unchanged_and_touching_outward_motion_is_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Do not perturb an existing valid proposal or grant motion outward from an active halfspace.
    """
    project = Mock(return_value=(0.05,) + (0.0,) * 7)
    monkeypatch.setitem(vars(redistributed_projection), "active_step", project)
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]]
    for physical in (-0.1, 0.0):
        evidence = redistributed_projection.ProjectionEvidence()
        result = redistributed_projection.redistributed_step(
            _Domain(),
            (0.0,),
            rows,
            (1.0,) + (0.0,) * 5 + (physical,),
            lambda: None,
            evidence=evidence,
        )
        assert result == ((0.05,) if physical < 0 else None)
        assert evidence.halfspace_contracted_proposals == 0


def test_ray_contraction_keeps_nonzero_box_coordinates_and_one_common_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scale positive and negative increments together while retaining their original convex coordinate box.
    """
    project = Mock(return_value=(0.5, -0.5) + (0.0,) * 7)
    monkeypatch.setitem(vars(redistributed_projection), "active_step", project)
    rows = [[-1.0, 0.0]] + [[0.0, 0.0] for _ in range(5)] + [[1.0, -1.0]]
    residual = (1.0,) + (0.0,) * 5 + (-0.2,)
    values = (0.3, 0.7)
    step = redistributed_projection.redistributed_step(
        _Domain(), values, rows, residual, lambda: None
    )
    assert step is not None and step[0] == -step[1]
    assert 0 < step[0] <= 0.1 and -0.2 + step[0] - step[1] <= 1e-14
    assert all(0.0 <= value + change <= 1.0 for value, change in zip(values, step))
    project.assert_called_once()


def test_independent_cap_errors_escape_a_proportional_restoration_obstruction() -> None:
    """
    Reduce the largest cap error even when a smaller component must initially grow.
    """
    rows = [[-1.0], [1.0]] + [[0.0] for _ in range(5)]
    residual = (1.0, 0.5, 0.0, 0.0, 0.0, 0.0, -1.0)
    common = restoration_step(_Domain(), (0.0,), rows, residual, lambda: None)
    assert common is None or abs(common[0]) < 1e-12
    step = redistributed_projection.redistributed_step(
        _Domain(), (0.0,), rows, residual, lambda: None
    )
    assert step is not None and 0 < step[0] < 0.5
    assert max(1.0 - step[0], 0.5 + step[0]) < 1.0


@pytest.mark.parametrize("count", (1, 5, 13))
def test_violated_physical_rows_can_progress_without_caps_or_crossing_satisfied_rows(
    count: int,
) -> None:
    """
    Retain every supplied physical row and bound the correction by real geometry coordinates.
    """
    rows = [[0.0] for _ in range(6)] + [[-1.0] for _ in range(count)]
    residual = (0.0,) * 6 + (2.0,) * count
    step = redistributed_projection.redistributed_step(
        _Domain(high=0.25), (0.0,), rows, residual, lambda: None
    )
    assert step is not None and 0 < step[0] <= 0.25 + 1e-14
    assert 0 < 2.0 - step[0] < 2.0


def test_satisfied_physical_row_remains_a_strict_gate() -> None:
    """
    A clearance row limits cap progress despite the numerical residual coordinates.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(5)] + [[1.0]]
    residual = (1.0,) + (0.0,) * 5 + (-0.1,)
    step = redistributed_projection.redistributed_step(
        _Domain(), (0.0,), rows, residual, lambda: None
    )
    assert step is not None and 0 < step[0] <= 0.1 + 1e-14


def test_no_geometric_descent_is_not_hidden_by_numerical_slacks() -> None:
    """
    Fixed geometry and an already solved system grant no correction.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(6)]
    for residual in ((1.0,) + (0.0,) * 5 + (-1.0,), (0.0,) * 7):
        assert (
            redistributed_projection.redistributed_step(
                _Domain(high=0.0), (0.0,), rows, residual, lambda: None
            )
            is None
        )


def test_one_projection_retains_original_rows_bounds_and_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Add only bounded numerical residuals in the original single working-set call.
    """
    project = Mock(return_value=None)
    monkeypatch.setitem(vars(redistributed_projection), "active_step", project)
    model, check = _Domain(), Mock()
    rows = [[1.0] for _ in range(8)]
    residual = (1.0, -2.0, 0.0, 0.0, 0.0, 0.0, 3.0, -0.25)
    assert redistributed_projection.redistributed_step(model, (0.0,), rows, residual, check) is None
    project.assert_called_once()
    domain, values, matrix, terms, checkpoint = project.call_args.args
    assert terms is residual and checkpoint is check and values == (0.0,) * 8
    assert domain.bounds(0) == (0.0, 3.0)
    assert all(domain.bounds(i) == (-1.0, 1.0) for i in range(1, 7))
    assert domain.bounds(7) == (0.0, 1.0)
    assert [row[:1] for row in matrix] == [[1 / 3]] * 8
    assert [row[-1] for row in matrix] == [0.0] * 6 + [-3.0, 0.0]
    assert [matrix[i][i + 1] for i in range(6)] == [-3.0] * 6


@pytest.mark.parametrize("error", (0.03, 0.01, 0.001))
def test_vanishing_motion_penalty_restores_weak_but_feasible_physical_sensitivity(
    error: float,
) -> None:
    """
    A small derivative must not make leaving a real violation cheaper than available bounded motion.
    """
    gradient = error / 10
    rows = [[0.0] for _ in range(6)] + [[-gradient]]
    residual = (0.0,) * 6 + (error,)
    fixed_penalty_step = gradient * error / (gradient**2 + error**2)
    assert error - gradient * fixed_penalty_step > 0.99 * error
    step = redistributed_projection.redistributed_step(
        _Domain(high=12.0), (0.0,), rows, residual, lambda: None
    )
    assert step is not None and 9 < step[0] <= 10.0
    assert 0 <= error - gradient * step[0] < 0.1 * error


def test_transformed_nonzero_coordinates_preserve_real_bound_and_increment() -> None:
    """
    Translate a bounded nonzero base in the scaled domain and return only the original geometry increment.
    """
    rows = [[-1.0]] + [[0.0] for _ in range(6)]
    residual = (0.01,) + (0.0,) * 5 + (-1.0,)
    step = redistributed_projection.redistributed_step(
        _Domain(high=0.505), (0.5,), rows, residual, lambda: None
    )
    assert step is not None and 0 < step[0] <= 0.005 + 1e-14
    assert 0 < 0.01 - step[0] < 0.01


def test_hard_cancellation_propagates() -> None:
    """
    Preserve source/resource cancellation from the original projector.
    """
    check = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        redistributed_projection.redistributed_step(
            _Domain(), (0.0,), [[1.0]] * 7, (1.0,) * 7, check
        )


@pytest.mark.parametrize("count", (6, 20))
def test_physical_row_capacity_is_unchanged(count: int) -> None:
    """
    Reject row counts outside the existing six-cap thirteen-inequality contract.
    """
    with pytest.raises(ValueError, match="thirteen"):
        redistributed_projection.redistributed_step(
            _Domain(), (0.0,), [[1.0]] * count, (1.0,) * count, lambda: None
        )
