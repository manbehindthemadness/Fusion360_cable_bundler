"""
Verify compatible fitting stays bounded and keeps fixed planar pose controls.
"""

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_shooting import solve
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _case(z: float) -> EndpointCase:
    """
    Author endpoint poses independently of any generated strip.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("anonymous", Vector3(-40, 0, 0), Vector3(40, 0, z), x, x, y, y)


@pytest.mark.parametrize("z", [0.0, 12.0, -18.0])
def test_fixed_planar_controls_close_within_registered_work(z: float) -> None:
    """
    Require actual closure,monotone objectives and separately counted seed work.
    """
    case = _case(z)
    path, metrics = solve(case, lambda: None)
    assert metrics["endpoint_gate_passed"]
    assert magnitude(difference(path.lane(1, 0)[0], case.end)) < 1e-8
    assert metrics["evaluations"] <= 254 and metrics["seed_screenings"] == 46
    for stage in metrics["stages"]:
        assert all(b <= a for a, b in zip(stage["history"], stage["history"][1:]))


def test_identity_does_not_select_solver_geometry() -> None:
    """
    Preserve identical states and coordinates when only the fixture label changes.
    """
    case = _case(12)
    original, before = solve(case, lambda: None)
    renamed, after = solve(replace(case, name="another-label"), lambda: None)
    assert original.states == renamed.states
    assert before["coordinates"] == after["coordinates"]
