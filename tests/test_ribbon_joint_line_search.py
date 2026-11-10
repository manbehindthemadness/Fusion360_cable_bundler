"""
Check bounded curvature contraction without saved layouts or additional trials.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import ContactGuidance
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.line_search import contracted_fraction
from tests.test_ribbon_contact_refinement import _depth, _gate, _source


@pytest.mark.parametrize("curvature", (0.2, 1.0, 5.0))
@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
def test_curved_weak_descent_is_reached_within_original_four_trials(
    curvature: float, scale: float
) -> None:
    """
    Reach strict descent on a quadratic that rejects all four fixed halvings.
    """
    before = scale
    slope = -0.01 * scale

    def merit(step: float) -> float:
        """
        Supply a positive physical residual with weak linear sensitivity and curvature.
        """
        return scale * (1.0 - 0.01 * step + curvature * step * step)

    assert all(merit(0.5**i) >= before for i in range(4))
    fraction = 1.0
    observations = []
    for _ in range(4):
        observed = merit(fraction)
        observations.append(observed)
        if observed < before:
            break
        next_fraction = contracted_fraction(fraction, before, observed, slope)
        assert 0.1 * fraction <= next_fraction <= 0.5 * fraction
        fraction = next_fraction
    assert observations[-1] < before
    assert 2 <= len(observations) <= 4


@pytest.mark.parametrize(
    ("observed", "slope"),
    ((None, -1.0), (math.inf, -1.0), (math.nan, -1.0), (2.0, 0.0), (2.0, 1.0)),
)
def test_unusable_observation_or_non_descent_prediction_retains_halving(
    observed: float | None, slope: float
) -> None:
    """
    Do not infer curvature from invalid material or a non-descent linear model.
    """
    assert contracted_fraction(0.8, 1.0, observed, slope) == 0.4


def test_interpolation_uses_fraction_in_physical_direction_units() -> None:
    """
    Recover a quadratic minimizer after an earlier bound-limited rejected trial.
    """
    fraction = 0.25
    before, slope, curvature = 2.0, -0.1, 1.0
    observed = before + slope * fraction + curvature * fraction**2
    assert contracted_fraction(fraction, before, observed, slope) == pytest.approx(0.05)


@pytest.mark.parametrize("curvature", (0.0, 1.0))
def test_joint_correction_uses_one_direction_and_original_trial_limit(
    monkeypatch: pytest.MonkeyPatch, curvature: float
) -> None:
    """
    Exercise orchestration with an analytical equation boundary, preserving first-trial success.

    Model placement is real, while residuals and the projector are analytical
    controls. Decline the next projection so no mocked residual earns clearance.
    """
    source = _source()
    model = SignedJoints(source)
    initial = model.initial
    fractions: list[float] = []

    def equations(values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Measure the controlled physical inequality along the one offered coordinate.
        """
        step = values[0] - initial[0]
        fractions.append(step)
        return (0.0,) * 6 + (1.0 - 0.01 * step + curvature * step * step,)

    evaluation = SimpleNamespace(
        equations=equations, admissible=model.admissible, constraints_changed=lambda: None
    )
    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", Mock(return_value=evaluation))
    rows = [[0.0] * len(initial) for _ in range(7)]
    rows[-1][0] = -0.01
    derivative = Mock(return_value=rows)
    monkeypatch.setitem(vars(joint_contact), "joint_jacobian", derivative)
    delta = (1.0,) + (0.0,) * (len(initial) - 1)
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
        mode=ContactGuidance(),
    )
    assert result is not None and result.route is source and result.contact is None
    assert result.detail["newton_steps"] == 1
    assert result.detail["stop_reason"] == "linear_projection_infeasible"
    assert projector.call_count == derivative.call_count == 2
    update = next(event for event in events if event["status"] == "update")
    accepted_step = update["values"][0] - initial[0]
    assert accepted_step == pytest.approx(1.0 if curvature == 0.0 else 0.005)
    # Base equations are also evaluated for merit and retained update reporting.
    attempted = list(dict.fromkeys(step for step in fractions if step > 0))
    assert len(attempted) == (1 if curvature == 0.0 else 4)
