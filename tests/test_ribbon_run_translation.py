"""
Verify fixed-bend runway translation and its nonrenewing recovery budget.
"""

from __future__ import annotations

from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error, restore
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from experiments.experiment_ribbon_terminal_hardware.straight_projection import shortest_run_step
from tests.test_ribbon_aesthetic import _route


def test_linear_runway_minimum_keeps_caps_and_solves_absent_slot_as_exact_zero() -> None:
    """
    Keep the fixed first slot, grow the constrained second slot and remove unnecessary third travel.
    """
    source = _route((Straight(3), fold(2, 1.2, 1, 0.2, 0), fold(2, 1.2, -1, 0, 0)))
    model = StraightSlots(source)
    assert model.indices == (0, 4, 8)
    values = (1.0, 1.0, 1.0)
    rows = [[1.0, 0.0, 0.0]] + [[0.0] * 3 for _ in range(5)] + [[0.0, -1.0, 0.0]]
    delta = shortest_run_step(model, values, rows, (0.0,) * 6 + (0.5,), lambda: None)
    assert delta is not None
    trial = tuple(a + b for a, b in zip(values, delta))
    assert trial == pytest.approx((1.0, 1.5, 0.0))
    assert trial[-1] == 0.0


@pytest.mark.skip(
    reason="Historical layout retired; geometry qualification uses fresh unique inputs"
)
def test_failed_reflection_uses_only_idle_updates_to_translate_original_fixed_bends() -> None:
    """
    Clear the saved nine-conductor return by lengthening runways without altering bend shapes.
    """
    scene = Scene(
        Config(284829440, 9, 0.75, 300, 300),
        Goal.from_degrees(2, 7, 73),
        Goal.from_degrees(24, 1, 0),
    )
    events: list[dict[str, Any]] = []
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, events.append
    )
    assert result.route is not None and result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    detail = result.detail["contraction"]
    assert detail["status"] == "restored" and detail["length_goal_excess_mm"] > 0
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["contact_pairs"] <= 1024 and detail["cpu_seconds"] < 0.35
    assert detail["before_translation"]["iterations"] + 1 == detail["iterations"]
    start = next(e for e in events if e.get("stage") == "terminal_fold_reversal")
    translated = next(e for e in events if e.get("status") == "straight_translation_contact")
    source, proposal = restore(start["source"]), restore(translated["route"])
    source_folds = [p.geometry for p in source.pieces if isinstance(p.geometry, CylindricalFold)]
    assert [
        p.geometry for p in proposal.pieces if isinstance(p.geometry, CylindricalFold)
    ] == source_folds
    assert proposal.targets == source.targets
    assert cap_error(proposal) < 1e-7 and material_error(proposal) < 1e-10
