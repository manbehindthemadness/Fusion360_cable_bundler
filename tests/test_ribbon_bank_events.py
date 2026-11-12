"""
Verify bounded change-point trials and consistent derivative domains at exact bank zeros.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.bank_events import BankEvent, ZeroBanks
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import ContactGuidance
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from experiments.experiment_ribbon_terminal_hardware.line_search import contracted_fraction
from tests.test_ribbon_contact_refinement import _depth, _gate, _source


@pytest.mark.parametrize("sign", (-1.0, 1.0))
@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
def test_change_point_can_use_an_unspent_correction_after_four_ordinary_failures(
    sign: float, scale: float
) -> None:
    """
    Preserve four failed ordinary trials, then measure a known cusp using the next correction slot.
    """
    bank, delta = sign * 1e-4, -sign
    event = BankEvent.first((bank,), (delta,), (0,), 0.2)
    assert event is not None

    def merit(fraction: float) -> float:
        """
        Couple a cap correction to absolute bank-dependent lead length.
        """
        point = event.coordinates((bank + fraction * delta,), fraction)
        return scale * (1.0 - 0.1 * fraction + abs(point[0]) - abs(bank))

    before, slope, ordinary = merit(0.0), -1.1 * scale, 0.2
    for _ in range(4):
        assert merit(ordinary) >= before
        ordinary = contracted_fraction(ordinary, before, merit(ordinary), slope)
    assert merit(event.fraction) < before
    assert event.coordinates((1e-18,), event.fraction) == (0.0,)
    assert event.coordinates((1e-18,), event.fraction / 2) == (1e-18,)


def test_first_event_respects_actual_bank_identity_and_original_trial_limit() -> None:
    """
    Ignore nonbanks and departing zeros; preserve bounds and simultaneous first crossings.
    """
    event = BankEvent.first((0.1, -0.02, 0.02, 0.0), (-1.0, 1.0, -1.0, 1.0), (1, 2, 3), 0.5)
    assert event == BankEvent(0.02, frozenset({1, 2}))
    assert BankEvent.first((0.1,), (-1.0,), (0,), 0.01) is None
    assert BankEvent.first((0.0,), (-1.0,), (0,), 1.0) is None


@pytest.mark.parametrize("side", (-1.0, 1.0))
def test_zero_bank_uses_measured_side_for_both_derivative_and_projection_bounds(
    side: float,
) -> None:
    """
    Choose either outgoing side while leaving every nonzero bank and other coordinate unchanged.
    """
    model = Mock(spec=MovableBends)
    model.indices = (0, 2, 6)
    model.bounds.return_value = (-1.0, 1.0)
    values = (0.4, 0.0, -0.2)
    score = Mock(side_effect=lambda p: 1.0 - side * p[1] + 0.5 * abs(p[1]))
    domain = ZeroBanks.at(model, values, score, lambda p: True, Mock())
    assert domain is not None
    assert score.call_count == 2
    assert domain.bounds(0) == domain.bounds(2) == (-1.0, 1.0)
    assert domain.bounds(1) == ((-1.0, 0.0) if side < 0 else (0.0, 1.0))
    rows = jacobian(
        domain, values, lambda p: (score(p),), 1, {0, 2}, Mock(), difference=Difference.ONE_SIDED
    )
    assert rows[0] == pytest.approx((0.0, -0.5 * side, 0.0))
    assert score.call_args.args[0][1] == side * 1e-5


def test_nonzero_banks_do_not_select_a_branch_or_spend_endpoint_measurements() -> None:
    """
    Preserve the original model identity and derivative behavior away from exact zeros.
    """
    model, score = Mock(spec=MovableBends), Mock()
    model.indices = (0, 2)
    assert ZeroBanks.at(model, (0.4, -1e-18), score, Mock(), Mock()) is None
    score.assert_not_called()


def test_zero_bank_material_rejection_and_cancellation_remain_authoritative() -> None:
    """
    Never score inadmissible endpoints or proceed after the caller's resource stop.
    """
    model, score = Mock(spec=MovableBends), Mock(return_value=1.0)
    model.indices = (2,)
    model.bounds.return_value = (-1.0, 1.0)
    domain = ZeroBanks.at(model, (0.0,), score, lambda p: p[0] < 0.0, Mock())
    assert domain is not None and domain.negative == frozenset({0})
    score.assert_called_once_with((-1e-5,))
    with pytest.raises(ArithmeticError, match="no admissible"):
        ZeroBanks.at(model, (0.0,), score, lambda p: False, Mock())
    with pytest.raises(TimeoutError, match="cancel"):
        ZeroBanks.at(model, (0.0,), score, Mock(), Mock(side_effect=TimeoutError("cancel")))


@pytest.mark.parametrize(
    ("crossing_succeeds", "remaining_newton"), ((False, 1), (False, 6), (True, 6))
)
def test_joint_solver_keeps_successful_crossing_and_measures_rejected_ray_event(
    monkeypatch: pytest.MonkeyPatch, crossing_succeeds: bool, remaining_newton: int
) -> None:
    """
    Exercise the actual four-trial orchestration; neither analytical residual earns clearance.
    """
    source = _source(1e-4)
    model = SignedJoints(source)
    initial = model.initial

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Supply a smooth successful crossing or a bank-lead cusp requiring an intermediate trial.
        """
        fraction = (initial[2] - values[2]) / 0.2
        term = (
            1.0 - 0.5 * fraction
            if crossing_succeeds
            else 1.0 - 0.01 * fraction + abs(values[2]) - abs(initial[2])
        )
        return (0.0,) * 6 + (term,)

    evaluation = SimpleNamespace(
        equations=equations, admissible=model.admissible, constraints_changed=lambda: None
    )
    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", Mock(return_value=evaluation))
    rows = [[0.0] * len(initial) for _ in range(7)]
    rows[-1][2] = 2.5 if crossing_succeeds else 1.05
    derivative = Mock(return_value=rows)
    monkeypatch.setitem(vars(joint_contact), "joint_jacobian", derivative)
    delta = tuple(-0.2 if i == 2 else 0.0 for i in range(len(initial)))
    projector = Mock(side_effect=(delta, None))
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projector)
    monkeypatch.setitem(vars(joint_contact), "step_limit", Mock(return_value=1.0))
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        _depth(),
        _gate(source),
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        maximum_newton_steps=remaining_newton,
        mode=ContactGuidance(),
    )
    assert result is not None and result.route is source and result.contact is None
    if not crossing_succeeds and remaining_newton == 1:
        assert projector.call_count == derivative.call_count == 1
        assert result.detail["newton_steps"] == 0
        assert result.detail["stop_reason"] == "joint_no_descent"
        assert not any(e["status"] == "bank_event_restoration_debit" for e in events)
        return
    assert projector.call_count == derivative.call_count == 2
    update = next(e for e in events if e["status"] == "update")
    event_trials = [e for e in events if e["status"] == "bank_event_restoration_debit"]
    if crossing_succeeds:
        assert update["values"][2] == initial[2] - 0.2
        assert not event_trials
    else:
        assert update["values"][2] == 0.0
        assert len(event_trials) == 1
        assert event_trials[0]["failed_correction_slots"] == 1
        assert event_trials[0]["event_correction_slots"] == 1
        assert update["newton"] == 2
