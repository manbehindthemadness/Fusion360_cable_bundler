"""
Verify cap-restoration metric calibration with authored affine maps and unchanged physical gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import redistributed_projection as projection


@dataclass(frozen=True)
class _Box:
    """
    Bound an analytical geometric coordinate without supplying any ribbon layout.
    """

    high: float = 100.0

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Supply the original finite nonnegative coordinate domain.
        """
        del index
        return 0.0, self.high


@pytest.mark.parametrize("sensitivity", (0.001, 0.002))
def test_weak_cap_restoration_closes_within_original_updates_without_regularization_bias(
    sensitivity: float,
) -> None:
    """
    Compare the authored scalar quadratic's exact old recurrence with calibrated constrained steps.

    For one affine cap, the original M-squared geometry penalty leaves the
    residual r**5/(sensitivity**2+r**4). No historical solver replay is used.
    Calibration improves finite-step restoration while the same box and actual
    affine residual are checked after every returned geometric increment.
    """
    legacy = 0.05
    legacy_updates = 0
    for _ in range(6):
        if abs(legacy) < 1e-13:
            break
        legacy = legacy**5 / (sensitivity**2 + legacy**4)
        legacy_updates += 1
    values = (0.0,)
    rows = [[-sensitivity]] + [[0.0] for _ in range(6)]
    updates = 0
    for _ in range(4):
        residual = 0.05 - sensitivity * values[0]
        if abs(residual) < 1e-13:
            break
        step = projection.redistributed_step(
            _Box(), values, rows, (residual,) + (0.0,) * 5 + (-1.0,), lambda: None
        )
        assert step is not None
        values = (values[0] + step[0],)
        assert 0 <= values[0] <= 100.0
        updates += 1
    assert abs(0.05 - sensitivity * values[0]) < 1e-13 and updates <= 3
    assert updates < legacy_updates


def test_calibration_cannot_hide_a_bound_limited_or_physically_conflicting_cap() -> None:
    """
    Better numerical scaling grants neither a larger coordinate domain nor purported cap closure.
    """
    rows = [[-0.001]] + [[0.0] for _ in range(6)]
    terms = (0.05,) + (0.0,) * 5 + (-1.0,)
    step = projection.redistributed_step(_Box(1.0), (0.0,), rows, terms, lambda: None)
    assert step is not None and 0 <= step[0] <= 1.0
    assert 0.05 - 0.001 * step[0] >= 0.049
    conflict = rows[:6] + [[1.0]]
    refused = projection.redistributed_step(
        _Box(), (0.0,), conflict, terms[:6] + (0.0,), lambda: None
    )
    if refused is not None:
        assert refused[0] <= 1e-14
        assert 0.05 - 0.001 * refused[0] > 0.049


@pytest.mark.parametrize("sensitivity,residual", ((1.0, 0.05), (0.1, 0.05), (0.001, 0.0)))
def test_unit_scale_and_smaller_cap_steps_retain_original_metric_exactly(
    sensitivity: float, residual: float
) -> None:
    """
    Avoid perturbing ordinary corrections or pure physical restoration with already closed caps.
    """
    rows = [[sensitivity]] + [[0.0] for _ in range(6)]
    assert projection._motion_scale(rows, (residual,) + (0.0,) * 6, 0.05) == 0.05


def test_inconsistent_cap_calibration_retains_original_partial_restoration_metric() -> None:
    """
    Independent cap-error redistribution remains available when a nominal exact cap solve is inconsistent.
    """
    rows = [[-1.0], [1.0]] + [[0.0] for _ in range(5)]
    terms = (1.0, 0.5) + (0.0,) * 4 + (-1.0,)
    assert projection._motion_scale(rows, terms, 1.0) == 1.0
    step = projection.redistributed_step(_Box(), (0.0,), rows, terms, lambda: None)
    assert step is not None and 0 < step[0] < 0.5


@pytest.mark.parametrize("estimate,coefficient", ((math.inf, 1.0), (math.nan, 1.0), (1e308, 1e308)))
def test_unrepresentable_calibration_falls_back_before_the_working_set(
    monkeypatch: pytest.MonkeyPatch, estimate: float, coefficient: float
) -> None:
    """
    A diagnostic norm cannot introduce nonfinite transformed columns or a second constrained solve.
    """
    monkeypatch.setitem(vars(projection), "affine_projection", Mock(return_value=[estimate]))
    assert projection._motion_scale([[coefficient]] * 7, (0.05,) * 7, 0.05) == 0.05


def test_one_constrained_projection_and_original_checkpoint_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The nominal cap metric estimate is not another candidate or working-set budget.
    """
    projector = Mock(wraps=projection.active_step)
    monkeypatch.setitem(vars(projection), "active_step", projector)
    rows = [[-0.001]] + [[0.0] for _ in range(6)]
    terms = (0.05,) + (0.0,) * 5 + (-1.0,)
    evidence = projection.ProjectionEvidence()
    assert (
        projection.redistributed_step(_Box(), (0.0,), rows, terms, lambda: None, evidence=evidence)
        is not None
    )
    assert evidence.cap_metric_calibrations == 1
    projector.assert_called_once()
    with pytest.raises(TimeoutError, match="original clock"):
        projection.redistributed_step(
            _Box(), (0.0,), rows, terms, Mock(side_effect=TimeoutError("original clock"))
        )
    projector.assert_called_once()
