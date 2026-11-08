"""
Exercise one-degree connector rolls while preserving historical quarter-turn replay.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import cross, dot, magnitude
from devtools.ribbon_analysis.gym.handoff import freeze, validate
from devtools.ribbon_analysis.gym.scene import Goal, generate
from devtools.ribbon_analysis.inspection.session import Session
from experiments.experiment_ribbon_locked_solver.tester.sequence import Specification, defaults
from tests.test_ribbon_range_sequence import specification


@pytest.mark.parametrize("face", range(12))
def test_roll_rotates_the_width_about_its_fixed_face_normal(face: int) -> None:
    """
    Measure every integer angle in the actual face plane, without moving its target or solid.
    """
    scene = generate()
    origin, normal, across, _ = scene.solid(scene.a.zone).face(face)
    up = cross(normal, across)
    for degrees in range(360):
        goal = Goal.from_degrees(scene.a.zone, face, degrees)
        point, tangent, width = scene.pose(goal)
        assert point == origin and tangent == normal
        assert magnitude(width) == pytest.approx(1)
        assert dot(width, normal) == pytest.approx(0, abs=1e-12)
        assert dot(width, across) == pytest.approx(math.cos(math.radians(degrees)), abs=1e-12)
        assert dot(width, up) == pytest.approx(math.sin(math.radians(degrees)), abs=1e-12)


def test_legacy_quarter_turns_keep_exact_goals_widths_and_payloads() -> None:
    """
    Never reinterpret old roll1 as1degree or add fields to historical serialized goals.
    """
    scene = generate()
    for index in range(4):
        legacy = Goal(scene.a.zone, scene.a.face, index)
        current = Goal.from_degrees(scene.a.zone, scene.a.face, index * 90)
        assert current == legacy
        assert current.payload() == {"zone": legacy.zone, "face": legacy.face, "roll": index}
        assert scene.pose(current) == scene.pose(legacy)


def test_mixed_degree_goals_freeze_and_validate_without_losing_units(tmp_path: Path) -> None:
    """
    Preserve non-cardinal start/end frames through the same diagnostic handoff used by workers.
    """
    original = generate()
    scene = original.choose("a", Goal.from_degrees(original.a.zone, original.a.face, 1))
    scene = scene.choose("b", Goal.from_degrees(original.b.zone, original.b.face, 359))
    session = Session(freeze(scene, tmp_path))
    assert session.targets == scene.targets
    assert session.gym is not None
    assert validate(session.gym, session.targets) == session.gym
    assert session.gym["a"]["roll_degrees"] == 1
    assert session.gym["b"]["roll_degrees"] == 359
    altered = json.loads(json.dumps(session.gym))
    altered["a"]["roll_degrees"] = 2
    with pytest.raises(ValueError):
        validate(altered, session.targets)


@pytest.mark.parametrize("angle", (-1, 360, 0.5, True))
def test_invalid_degree_inputs_reject_instead_of_rounding(angle: object) -> None:
    """
    Reject unsupported or malformed external angles without snapping them to legal values.
    """
    with pytest.raises(ValueError):
        Goal(0, 0, roll_degrees=angle)  # type: ignore[arg-type]


def test_ambiguous_legacy_and_degree_units_reject() -> None:
    """
    Do not silently choose between two conflicting orientation fields.
    """
    with pytest.raises(ValueError, match="either"):
        Goal(0, 0, 1, roll_degrees=10)


@pytest.mark.parametrize("step", (1, 10, 45))
def test_tester_uses_actual_degrees_without_quarter_turn_truncation(step: int) -> None:
    """
    Accept both the reported0..90/10range and one-degree sampling without changing old90steps.
    """
    payload = specification()
    payload["ranges"]["lines"] = {"min": 1, "max": 1, "step": 1}
    payload["ranges"]["a_roll"] = {"min": 0, "max": 90, "step": step}
    payload["ranges"]["b_roll"] = {"min": 359, "max": 359, "step": 1}
    spec = Specification.parse(payload)
    scenes = [spec.scene(i) for i in range(spec.combinations)]
    assert [scene.a.degrees for scene in scenes] == list(range(0, 91, step))
    assert all(scene.b.degrees == 359 for scene in scenes)
    assert defaults(scenes[-1])["ranges"]["b_roll"] == {"min": "-90", "max": "90", "step": "1"}
    assert Specification.parse(spec.payload()).scene(1) == scenes[1]
