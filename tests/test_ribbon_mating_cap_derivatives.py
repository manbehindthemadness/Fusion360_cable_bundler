"""
Preserve final cap accuracy without centering nonsmooth physical inequalities or renewing correction work.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import (
    Difference,
    jacobian,
    mating_cap_jacobian,
)
from experiments.experiment_ribbon_terminal_hardware.projection_system import CoordinateBounds


@dataclass(frozen=True)
class _Bounds(CoordinateBounds):
    """
    Supply an actual finite coordinate contract for independent derivative tests.
    """

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep all authored coordinates inside the same closed unit interval.
        """
        return 0.0, 1.0


@pytest.mark.parametrize("offset", (-1e-7, 0.0, 1e-7))
def test_centered_caps_remove_first_order_truncation_without_changing_fixed_columns(
    offset: float,
) -> None:
    """
    A known smooth quadratic cap row retains second-order accuracy at the original probe size.
    """
    model = _Bounds()
    values = (0.4 + offset, 0.7)
    calls: list[tuple[float, ...]] = []

    def caps(v: tuple[float, ...]) -> tuple[float, ...]:
        """
        Supply only six cap equations; physical inequality callbacks are absent.
        """
        calls.append(v)
        x = v[0] - 0.4
        assert v[1] == values[1]
        return (x + x * x,) + (0.0,) * 5

    residual = caps(values)
    calls.clear()
    centered = mating_cap_jacobian(
        model, values, residual, caps, {1}, Mock(), admissible=lambda v: True
    )
    assert centered is not None and len(calls) == 2
    expected = 1 + 2 * offset
    assert centered[0] == pytest.approx((expected, 0), abs=1e-11)
    first_order = jacobian(model, values, caps, 6, {1}, Mock(), difference=Difference.ONE_SIDED)
    assert abs(first_order[0][0] - expected) > 9e-6
    assert all(row[1] == 0 for row in centered)


@pytest.mark.parametrize("error", (1e-5, -1e-5, 1e-3))
def test_far_caps_do_not_allocate_endpoint_evaluations(error: float) -> None:
    """
    Ordinary corrections keep exactly their original derivative work outside the existing probe-sized neighborhood.
    """
    evaluate = Mock(side_effect=AssertionError("No precision refinement needed"))
    assert (
        mating_cap_jacobian(
            _Bounds(),
            (0.4,),
            (error,) + (0.0,) * 5,
            evaluate,
            set(),
            Mock(),
            admissible=lambda v: True,
        )
        is None
    )
    evaluate.assert_not_called()


@pytest.mark.parametrize("residual", ((0.0,), (float("nan"),) + (0.0,) * 5))
def test_cap_contract_cannot_be_replaced_by_arbitrary_or_nonfinite_equations(
    residual: tuple[float, ...],
) -> None:
    """
    Bad numerical shape fails before probing geometry or claiming proof readiness.
    """
    with pytest.raises(ValueError, match="six finite"):
        mating_cap_jacobian(
            _Bounds(), (0.4,), residual, Mock(), set(), Mock(), admissible=lambda v: True
        )


def test_original_bounds_and_source_guards_stay_authoritative() -> None:
    """
    Near-bound centering keeps the original one-sided fallback and propagates caller cancellation.
    """
    model = _Bounds()
    evaluate = Mock(side_effect=lambda v: (v[0],) + (0.0,) * 5)
    result = mating_cap_jacobian(
        model, (0.0,), (0.0,) * 6, evaluate, set(), Mock(), admissible=lambda v: v[0] >= 0
    )
    assert result is not None and result[0] == pytest.approx((1,))
    assert [c.args[0] for c in evaluate.call_args_list] == [(0.0,), (1e-5,)]
    with pytest.raises(InterruptedError, match="source drift"):
        mating_cap_jacobian(
            model,
            (0.0,),
            (0.0,) * 6,
            evaluate,
            set(),
            Mock(side_effect=InterruptedError("source drift")),
            admissible=lambda v: True,
        )
