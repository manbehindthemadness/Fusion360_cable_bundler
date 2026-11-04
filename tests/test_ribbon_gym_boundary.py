"""
Keep the extra cubicle layer invisible, scale-dependent and separate from numerical/native acceptance.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.boundary import assess
from devtools.ribbon_analysis.gym.scene import Config
from tests.test_ribbon_range_tester import make_tester, start


@pytest.mark.parametrize(
    "lines,diameter,void,zones,half", ((8, 0.75, 300, 300, 45), (3, 1.5, 600, 200, 31.5))
)
def test_boundary_adds_one_actual_zone_depth_to_every_visible_outer_face(
    lines: int, diameter: float, void: float, zones: float, half: float
) -> None:
    """
    Include complete native extents and permit touching the closed box without a fixed-size allowance.
    """
    config = Config(1, lines, diameter, void, zones)
    result = assess(config, Vector3(-half, -half, -half), Vector3(half, half, half))
    assert result.half_extent_mm == half and result.problem is None
    assert result.payload()["status"] == "passed" and result.excess_mm == 0


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("positive", (False, True))
def test_crossing_any_face_is_a_failure(axis: int, positive: bool) -> None:
    """
    Reject even when the rest of the entire body remains inside the extra layer.
    """
    low, high = [-1.0] * 3, [1.0] * 3
    (high if positive else low)[axis] = 45.25 if positive else -45.25
    report = assess(Config(1, 8, 0.75, 300, 300), Vector3(*low), Vector3(*high))
    assert report.excess_mm == 0.25 and report.problem is not None
    assert report.payload()["status"] == "failed"


@pytest.mark.parametrize("bad", (math.inf, math.nan, 2.0))
def test_unusable_native_bounds_never_pass(bad: float) -> None:
    """
    Fail closed on nonfinite or reversed extents instead of trusting an incomplete measurement.
    """
    with pytest.raises(ValueError, match="finite ordered bounds"):
        assess(Config(), Vector3(bad, 0, 0), Vector3(1, 1, 1))


def test_tester_halts_after_successful_native_work_when_boundary_fails(tmp_path: Path) -> None:
    """
    Keep the offending body/case for presentation and omit the pass increment or next launch.
    """
    tester, runner, present = make_tester(tmp_path, ["completed"])
    tester.measure_boundary = lambda scene: assess(
        scene.config, Vector3(0, 0, 0), Vector3(1e6, 0, 0)
    )
    start(tester)
    tester.poll()
    tester.poll()
    assert not tester.active and tester.phase == "problem"
    assert tester.attempted == 1 and tester.passed == 0
    assert "Gym boundary failed" in tester.reason
    present.assert_called_once()
    assert len(runner.jobs) == 1
    measurement = json.loads((runner.jobs[0] / "gym-boundary.json").read_text())
    assert measurement["status"] == "failed"
    assert tester.state()["gym_boundary"] == measurement
    assert tester.journal is not None
    plan = json.loads((tester.journal.directory / "plan.json").read_text())
    assert plan["gym_boundary"]["extra_layers"] == 1
    assert plan["gym_boundary"]["graphics"] is False
    assert plan["gym_boundary"]["solver_feedback"] is False
    tester.poll()
    assert len(runner.jobs) == 1
