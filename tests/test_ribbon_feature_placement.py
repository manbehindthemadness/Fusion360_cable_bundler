"""
Keep guide-derived feature placement scale invariant and bounded by the existing construction contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver.placement import guide_parameters
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_locked_solver.solver_v2 import solve


def _scene(diameter: float = 0.75) -> Scene:
    """
    Recreate the fixed gym input whose midpoint rotation demands nonlocal fold runways.
    """
    return Scene(
        Config(3871626163, 5, diameter, 300, 300),
        Goal.from_degrees(11, 1, 12),
        Goal.from_degrees(0, 1, 55),
    )


@pytest.mark.parametrize("diameter", (0.375, 0.75, 1.5))
def test_conditioned_reference_uses_turn_progress_independently_of_scale(diameter: float) -> None:
    """
    Replace only the existing station and preserve its deterministic cumulative-turn parameter.
    """
    scene = _scene(diameter)
    frames = Frames.create(scene.targets)
    radius = diameter / 2 / PinchLimit().fraction * (1 + 1e-9)
    events: list[dict[str, Any]] = []
    parameters = guide_parameters(
        Boundary(scene.targets, radius), frames, lambda: None, events.append
    )
    assert parameters == pytest.approx((0.8599760376305021,), abs=1e-12)
    assert parameters[0] == frames.turn_parameter(frames.turns[-1] / 2)
    assert events[0]["status"] == "cumulative_turn_midpoint"
    assert events[0]["minimum_midpoint_runway_mm"] > events[0]["guide_length_mm"]


def test_ordinary_midpoint_and_turn_interval_validation() -> None:
    """
    Preserve an ordinary guide and reject requests outside its ordered cumulative-turn range.
    """
    scene = Scene(
        Config(1607811975, 4, 0.75, 300, 300),
        Goal.from_degrees(21, 10, 5),
        Goal.from_degrees(3, 1, 32),
    )
    frames = Frames.create(scene.targets)
    radius = 0.75 / 2 / PinchLimit().fraction * (1 + 1e-9)
    assert guide_parameters(
        Boundary(scene.targets, radius), frames, lambda: None, lambda e: None
    ) == (0.5,)
    assert frames.turn_parameter(0.0) == 0.0
    assert frames.turn_parameter(frames.turns[-1]) == 1.0
    for wanted, begin, end in ((-1.0, 0, 256), (float("nan"), 0, 256), (0.0, 1, 1)):
        with pytest.raises(ValueError, match="cumulative turn"):
            frames.turn_parameter(wanted, begin, end)


def test_compact_feature_contact_stays_on_one_branch_with_original_work_limits() -> None:
    """
    Clear the fold and attached-straight contacts without abandoning the same material feature.
    """
    scene = _scene()
    events: list[dict[str, Any]] = []
    result = solve(scene.targets, Settings(1, False, True), lambda: None, events.append)
    assert result.route is not None and result.route.material_length_mm < 40
    assert result.detail["contact"] == "separated"
    construction = result.detail["construction"]
    recovery = construction["recovery"]
    assert construction["contact_pairs"] <= 2048 and construction["closed_branches"] <= 4
    assert recovery["iterations"] == recovery["contacts"] == 2
    assert len(recovery["attempts"]) == 1 and recovery["attempts"][0]["roots"] == (1, 0)
    assert any(event.get("stage") == "contact_feature_continuation" for event in events)
    assert result.route.targets == scene.targets
    assert result.detail["cap_error_mm"] < 1e-7 and result.detail["material_metric_error"] < 1e-10
    disabled = solve(scene.targets, Settings(0, False, False), lambda: None, lambda e: None)
    assert disabled.detail["construction"]["guide_parameters"] == (0.5,)


def test_short_control_keeps_midpoint_when_only_curved_material_exceeds_guide() -> None:
    """
    Preserve the accepted short layout rather than treating necessary bend arcs as runaway demand.
    """
    scene = Scene(
        Config(3875417403, 1, 0.75, 300, 300),
        Goal.from_degrees(8, 2, 75),
        Goal.from_degrees(21, 0, 22),
    )
    result = solve(scene.targets, Settings(1, False, True), lambda: None, lambda e: None)
    assert result.route is not None and result.detail["contact"] == "separated"
    assert result.detail["construction"]["guide_parameters"] == (0.5,)
    assert result.route.material_length_mm < 6.18
