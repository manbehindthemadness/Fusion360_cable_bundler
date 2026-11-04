"""
Verify deterministic range coverage, replay and validation independently of solver outcomes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_locked_solver.tester.ranges import NumericRange
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults


def specification() -> dict[str, Any]:
    """
    Use fixed selected faces and small dimensions without supplying a route.
    """
    payload = defaults(Scene(Config(19, 3, 0.75, 300, 300), Goal(10, 0), Goal(7, 8, 1)))
    payload["avoid_adjacent_zones"] = False
    return payload


def test_decimal_steps_are_exact_and_stop_at_the_declared_maximum() -> None:
    """
    Avoid cumulative floating drift and explicitly include only reachable values.
    """
    span = NumericRange.parse({"min": "0.1", "max": "0.35", "step": "0.1"})
    assert span.count == 3
    assert [span.value(i) for i in range(span.count)] == [0.1, 0.2, 0.3]
    assert NumericRange.parse(span.payload()) == span


@pytest.mark.parametrize("mode", ("systematic", "random"))
def test_replay_depends_only_on_specification_and_case_index(mode: str) -> None:
    """
    Generate the same inputs after reconnect without consuming mutable random state.
    """
    payload = specification()
    payload["mode"] = mode
    payload["ranges"]["a_zone"] = {"min": 1, "max": 3, "step": 1}
    payload["ranges"]["b_zone"] = {"min": 1, "max": 3, "step": 1}
    first = Specification.parse(payload)
    second = Specification.parse(first.payload())
    scenes = [first.scene(i) for i in range(12)]
    assert scenes == [second.scene(i) for i in range(12)]
    assert all(scene.a.zone != scene.b.zone and 1 <= scene.config.lines <= 6 for scene in scenes)
    assert first.scene(11) == first.scene(11)


def test_systematic_sweep_visits_combinations_then_repeats_with_new_gym_seeds() -> None:
    """
    Visit every selected dimension/face combination with conductor count advancing fastest.
    """
    payload = specification()
    payload["ranges"]["lines"] = {"min": 2, "max": 3, "step": 1}
    payload["ranges"]["a_face"] = {"min": 1, "max": 2, "step": 1}
    spec = Specification.parse(payload)
    scenes = [spec.scene(i) for i in range(5)]
    assert spec.combinations == 4
    assert [(s.config.lines, s.a.face) for s in scenes] == [(2, 0), (3, 0), (2, 1), (3, 1), (2, 0)]
    assert scenes[4].config.seed != scenes[0].config.seed
    assert scenes[4].a == scenes[0].a and scenes[4].b == scenes[0].b


@pytest.mark.parametrize(
    "field,change",
    (
        ("lines", {"min": 0}),
        ("lines", {"step": ".5"}),
        ("diameter_mm", {"min": 0}),
        ("void_percent", {"min": 299}),
        ("a_roll", {"step": ".5"}),
        ("a_roll", {"max": 360}),
        ("b_face", {"max": 13}),
        ("zone_percent", {"step": 0}),
        ("diameter_mm", {"max": "NaN"}),
        ("diameter_mm", {"max": "1.75", "step": "1e-20"}),
    ),
)
def test_invalid_ranges_reject_before_scheduling(field: str, change: dict[str, Any]) -> None:
    """
    Refuse malformed values rather than silently clamping or attempting invalid gym inputs.
    """
    payload = deepcopy(specification())
    payload["ranges"][field].update(change)
    with pytest.raises(ValueError):
        Specification.parse(payload)


def test_equal_only_endpoint_zone_ranges_reject_before_launch() -> None:
    """
    Do not enter an endless skip loop when no distinct zone pair exists.
    """
    payload = specification()
    payload["ranges"]["b_zone"] = payload["ranges"]["a_zone"].copy()
    with pytest.raises(ValueError, match="different zones"):
        Specification.parse(payload)
