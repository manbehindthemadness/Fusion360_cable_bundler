"""
Check endpoint-first director routing contracts without touching reserved witnesses.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.director_fields import rejection_controls
from experiments.experiment_ribbon_cap_transition.director_rotation_transport import (
    integrate_rotation,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import (
    free_penalties,
    regular_penalties,
)
from experiments.experiment_ribbon_cap_transition.director_shooting import (
    BANK,
    BASELINE,
    CORKSCREW,
    FREE,
    REGULAR,
    ROTATION,
    ShootingPolicy,
    bounded,
    field_for,
    seed,
    solve,
)
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


def _checkpoint() -> None:
    """
    Leave live resource sampling to the registered experiment runner.
    """


def _case(z: float = 0.0) -> EndpointCase:
    """
    Freeze a planar control whose endpoints are independent of a generated path.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase(
        "synthetic_endpoint", Vector3(-40, 0, -z / 2), Vector3(40, 0, z / 2), x, x, y, y
    )


@pytest.mark.parametrize("z", [0.0, 12.0, -18.0])
@pytest.mark.parametrize("policy", [BASELINE, ROTATION, REGULAR, CORKSCREW, FREE, BANK])
def test_cold_start_reaches_fixed_planar_targets_without_snapping(
    z: float, policy: ShootingPolicy
) -> None:
    """
    Require strict actual A-edge closure and monotone stages on unrelated offsets.
    """
    case = _case(z)
    path, metrics = solve(case, _checkpoint, policy=policy)
    assert metrics["endpoint_gate_passed"]
    assert metrics["evaluations"] <= 2 + 12 * (policy.coarse_rounds + policy.final_rounds)
    assert magnitude(difference(path.lane(1, 0)[0], case.end)) < 1e-8
    for stage in metrics["stages"]:
        assert all(b <= a for a, b in zip(stage["history"], stage["history"][1:]))


def test_seed_depends_on_geometry_not_case_identity() -> None:
    """
    Prevent hidden per-fixture lookup paths from supplying a routing solution.
    """
    original = _case(12)
    renamed = replace(original, name="unseen_label")
    assert seed(original) == seed(renamed)


def test_extra_harmonic_preserves_caps_and_analytic_ruling_derivative() -> None:
    """
    Verify the new independent coefficient before any solver outcome is examined.
    """
    field = field_for(_case(), (1.0, -0.3, 0.4, 0.2, -0.2, 0.4, -0.3, 0.2, 0.5, 1.3))
    assert abs(field.sample(0)[1]) < 1e-12 and abs(field.sample(1)[1]) < 1e-12
    u, step = 0.371, 1e-6
    numerical = (field.sample(u + step)[1] - field.sample(u - step)[1]) / (
        2 * step * field.length_mm
    )
    assert field.sample(u)[2] == pytest.approx(numerical, rel=1e-8)


def test_search_bounds_reject_nonfinite_and_do_not_move_endpoint_inputs() -> None:
    """
    Keep bounds on solver freedom,not on user geometry or acceptance tolerances.
    """
    values = bounded((100.0,) * 10)
    assert values[:5] == (4 * math.pi,) * 5
    assert values[5:9] == (3.0,) * 4 and values[9] == 5
    with pytest.raises(ValueError):
        bounded((float("nan"),) * 10)


def test_regular_chart_bounds_full_width_jacobian_before_integration() -> None:
    """
    Check extreme raw ruling coordinates without accepting a clipped bad shape.
    """
    for scale in (1.0, 2.0, 5.0):
        field = field_for(
            _case(), (2.0, 1.0, -1.0, 0.5, 0.0, 3.0, -3.0, 3.0, -3.0, scale), policy=REGULAR
        )
        for i in range(1025):
            assert 1 - field.half_width_mm * abs(field.sample(i / 1024)[2]) > 0.1


def test_free_surrogate_penalizes_folding_while_regular_chart_rejects_it() -> None:
    """
    Separate optimizer freedom from the final geometry rejection contract.
    """
    path = integrate_rotation(rejection_controls()[0], 64, _checkpoint)
    penalties = free_penalties(_case(), path)
    assert all(math.isfinite(value) for value in penalties)
    assert max(penalties) > 0
    with pytest.raises(ValueError, match="Jacobian bound"):
        regular_penalties(_case(), path)
