"""
Verify bounded reference derivatives independently of saved layouts and solver outcomes.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from tests.test_ribbon_aesthetic import _route


def test_reference_differences_preserve_affine_rows_bounds_and_fixed_columns() -> None:
    """
    Two free coordinates need one base and two endpoints, with backward sampling at an upper bound.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    calls: list[tuple[float, ...]] = []

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Supply independent affine and quadratic functions with known one-sided truncation.
        """
        calls.append(values)
        x, y, z = values
        assert z == 0.3 and 0 <= x <= 1 and 0 <= y <= 1
        return x + 3 * y, x * x + 2 * y * y

    values = (0.4, 1.0, 0.3)
    result = jacobian(model, values, equations, 2, {2}, Mock(), difference=Difference.ONE_SIDED)
    assert len(calls) == 3 and calls[0] == values
    assert calls[1] == (0.4 + 1e-5, 1.0, 0.3)
    assert calls[2] == (0.4, 1.0 - 1e-5, 0.3)
    assert result[0] == pytest.approx((1, 3, 0))
    assert result[1] == pytest.approx((0.8 + 1e-5, 4 - 2e-5, 0))


def test_material_domain_can_require_negative_endpoint() -> None:
    """
    A positive coordinate endpoint is never evaluated when the material predicate rejects it.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    values = (0.4,)
    evaluate = Mock(side_effect=lambda v: (2 * v[0],))
    result = jacobian(
        model,
        values,
        evaluate,
        1,
        set(),
        Mock(),
        admissible=lambda v: v[0] <= 0.4,
        difference=Difference.ONE_SIDED,
    )
    assert result[0] == pytest.approx((2,))
    assert [c.args[0] for c in evaluate.call_args_list] == [values, (0.4 - 1e-5,)]


def test_isolated_material_domain_declines_without_invalid_equation_probe() -> None:
    """
    No available endpoint is an explicit derivative failure, with no extra probe or geometry repair.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    values = (0.4,)
    evaluate = Mock(return_value=(1.0,))
    with pytest.raises(ArithmeticError, match="no admissible finite endpoint"):
        jacobian(
            model,
            values,
            evaluate,
            1,
            set(),
            Mock(),
            admissible=lambda v: v == values,
            difference=Difference.ONE_SIDED,
        )
    evaluate.assert_called_once_with(values)


@pytest.mark.parametrize("row_results", [((1.0, 2.0),), ((1.0,), (1.0, 2.0))])
def test_row_contract_changes_are_not_silently_accepted(
    row_results: tuple[tuple[float, ...], ...],
) -> None:
    """
    Both current and endpoint equation shape must match the declared matrix.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    with pytest.raises(ArithmeticError, match="finite equation contract"):
        jacobian(
            model,
            (0.4,),
            Mock(side_effect=row_results),
            1,
            set(),
            Mock(),
            difference=Difference.ONE_SIDED,
        )


def test_caller_failure_propagates_before_sampling() -> None:
    """
    One-sided guidance cannot convert source/cancellation failures into a usable matrix.
    """
    model = Mock(spec=MovableBends)
    evaluate = Mock()
    with pytest.raises(TimeoutError, match="outer"):
        jacobian(
            model,
            (0.4,),
            evaluate,
            1,
            set(),
            Mock(side_effect=TimeoutError("outer")),
            admissible=lambda v: True,
            difference=Difference.ONE_SIDED,
        )
    evaluate.assert_not_called()


def test_default_centered_scheme_keeps_original_two_probe_behavior() -> None:
    """
    Existing consumers retain centered accuracy and do not evaluate a new base row.
    """
    model = Mock(spec=MovableBends)
    model.bounds.return_value = (0.0, 1.0)
    evaluate = Mock(side_effect=lambda v: (v[0] * v[0],))
    result = jacobian(model, (0.4,), evaluate, 1, set(), Mock())
    assert result[0] == pytest.approx((0.8,))
    assert [c.args[0] for c in evaluate.call_args_list] == [(0.4 - 1e-5,), (0.4 + 1e-5,)]


def test_reference_derivative_tracks_real_material_cap_equations() -> None:
    """
    Authored nonplanar material kinematics retain a close raw derivative under the explicit approximation.
    """
    route = _route(
        (
            Straight(3),
            fold(2, 1.2, 1.1, 0.2, 0),
            Straight(4),
            fold(3, 1.2, -0.9, -0.3, 0),
            Straight(5),
        )
    )
    model = SignedJoints(route)
    values = model.initial
    centered = jacobian(
        model, values, model.residual, 6, set(), Mock(), admissible=model.admissible
    )
    reference = jacobian(
        model,
        values,
        model.residual,
        6,
        set(),
        Mock(),
        admissible=model.admissible,
        difference=Difference.ONE_SIDED,
    )
    assert max(abs(a - b) for old, new in zip(centered, reference) for a, b in zip(old, new)) < 1e-4
    assert model.route(values) is not None and model.initial == values
