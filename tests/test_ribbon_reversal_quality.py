"""
Check initial length handoff eligibility and preservation of the original shared recovery allowance.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import reversal_quality


@pytest.mark.parametrize(
    "motions,declined", (([None], False), ([(0.0,), None], True), ([(0.0,), (0.0,)], False))
)
def test_length_handoff_requires_bounded_cap_motion_and_declined_length(
    monkeypatch: pytest.MonkeyPatch, motions: list[Any], declined: bool
) -> None:
    """
    Keep unknown cap closure on its old path and never apply a projection to geometry.
    """
    model = Mock()
    model.initial = (0.0,)
    model.scale = 2.0
    model.indices = (0,)
    model.residual.return_value = (0.0,) * 6
    model.jacobian.return_value = [[0.0]] * 6
    model.full.length_gradient.return_value = [1.0]
    model.route.return_value.material_length_mm = 10.0
    projector = Mock(side_effect=motions)
    monkeypatch.setitem(vars(reversal_quality), "active_step", projector)
    checkpoint = Mock()
    assert reversal_quality.decline_initial_length(model, 9.0, checkpoint) is declined
    assert projector.call_count == len(motions)
    assert all(call.args[-1] is checkpoint for call in projector.call_args_list)
    if len(motions) == 1:
        model.route.assert_not_called()
    else:
        model.route.assert_called_once_with(model.initial)
    if len(motions) == 2:
        assert projector.call_args.args[3][-1] == 0.5


def test_early_handoff_keeps_work_for_actual_feature_clearance() -> None:
    """
    Close the saved five-conductor length conflict without spending its final updates on reflection.
    """
    scene = Scene(
        Config(3871626163, 5, 0.75, 300, 300),
        Goal.from_degrees(11, 1, 12),
        Goal.from_degrees(0, 1, 55),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    declined = next(e for e in events if e.get("status") == "initial_linear_length_declined")
    assert declined["detail"]["iterations"] == declined["detail"]["newton_steps"] == 0
    detail = result.detail["construction"]["recovery"]
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["cpu_seconds"] < 0.35 and detail["contact_pairs"] <= 2048
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
