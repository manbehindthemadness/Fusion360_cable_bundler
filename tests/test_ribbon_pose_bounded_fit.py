"""
Verify relative endpoint corridors and actual constrained continuation steps.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.director_shooting import residual
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery.active_clearance import sample
from experiments.experiment_ribbon_route_discovery.families import Seed
from experiments.experiment_ribbon_route_discovery.pose_bounded_fit import (
    pose_limits,
    refine_bounded,
)
from experiments.experiment_ribbon_route_discovery.solver import (
    integrate,
    refine_full,
    screen_seeds,
)


def _case() -> EndpointCase:
    """
    Retain an examined clamped quarter-turn regression without stored coordinates.
    """
    x, y, minus_z = Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1)
    return EndpointCase("pose-corridor", Vector3(-40, 0, 0), Vector3(35, -16, 12), x, x, y, minus_z)


@pytest.mark.parametrize("scale", [0.1, 1, 100])
def test_pose_corridor_is_invariant_under_uniform_geometry_scaling(scale: float) -> None:
    """
    Scale search restrictions with dimensions instead of imposing a fixed distance.
    """
    case = _case()

    def scaled(p: Vector3) -> Vector3:
        """
        Scale only positions,leaving the dimensionless frame directions unchanged.
        """
        return Vector3(p.x * scale, p.y * scale, p.z * scale)

    other = replace(
        case, start=scaled(case.start), end=scaled(case.end), diameter_mm=case.diameter_mm * scale
    )
    assert pose_limits(other) == pytest.approx(pose_limits(case))


def test_actual_accepted_width_steps_stay_inside_pose_corridor() -> None:
    """
    Check actual transported endpoint errors,QP accounting and final density.

    This examined crossing need not be solved by the bounded continuation. The
    regression ensures accepted width steps cannot pay for clearance by losing pose.
    """
    case = _case()
    _, selected, _ = screen_seeds(case, lambda: None)
    initial, base = refine_full(case, selected[0], lambda: None)
    assert (
        base["strict_endpoint_gate"]
        and sample(case, initial, lambda: None).contacts["contact_detected"]
    )
    seed = Seed(selected[0].index, base["coordinates"], base["score"], selected[0].descriptor)
    path, result = refine_bounded(case, seed, lambda: None)
    assert len(path.states) == 513 and result["evaluations"] <= 194
    assert result["qp_steps"] and all(q["iterations"] <= 32 for q in result["qp_steps"])
    accepted = [t for t in result["stages"][0]["trials"] if t["accepted"]]
    assert accepted
    for trial in accepted:
        actual = integrate(case, trial["proposed"], 64, lambda: None)
        assert all(
            abs(v - origin) <= limit
            for v, origin, limit in zip(
                residual(case, actual), result["stages"][0]["pose_reference"], pose_limits(case)
            )
        )
    assert 2 <= result["contact_audits"] <= 34
