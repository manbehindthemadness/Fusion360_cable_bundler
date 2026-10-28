"""
Verify local basis continuity, preserved material bounds and unchanged controls.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart, local_chart, local_clearance


def _case() -> EndpointCase:
    """
    Supply a fixed straight boundary configuration without external data.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("local-control", Vector3(0, 0, 0), Vector3(100, 0, 0), x, x, y, y)


def test_local_basis_has_smooth_joins_and_exact_derivative_bound() -> None:
    """
    Compact supports must not introduce ruling or derivative jumps at joins.
    """
    for join in (0, 0.25, 0.5, 0.75, 1):
        _, value, derivative = local_chart.bump(join)
        assert value == derivative == 0
    for u in (0.03, 0.14, 0.35, 0.69, 0.93):
        step = 1e-6
        _, value, derivative = local_chart.bump(u)
        numeric = (local_chart.bump(u + step)[1] - local_chart.bump(u - step)[1]) / (2 * step)
        assert 0 <= value <= 1
        assert derivative == pytest.approx(numeric, abs=1e-7)
    u = (1 - 1 / math.sqrt(5)) / 8
    assert local_chart.bump(u)[2] == pytest.approx(local_chart.DERIVATIVE_BOUND)


def test_zero_overlay_replays_nontrivial_original_exactly() -> None:
    """
    Basis adoption alone must not change a retained route or its integration order.
    """
    case = _case()
    base = (2.0, -1.0, 0.2, 0.3, 0.4, 0.3, -0.1, 0.1, 0.1, 2.0)
    old = broad_chart.integrate(case, base, 64, lambda: None)
    new = local_chart.integrate(case, base, (0.0,) * 8 + (2.0,), 64, lambda: None)
    assert new == old


@pytest.mark.parametrize("sign", [-1, 1])
def test_large_local_coordinates_keep_material_and_turn_contracts(sign: int) -> None:
    """
    Both extrema retain positive lanes and the unchanged center/conductor bounds.
    """
    case = _case()
    base = (2.0, -1.0, 0.2, 0.3, 0.4, 0.3, -0.1, 0.1, 0.1, 2.0)
    values = tuple(sign * (-1) ** i * 4 * math.pi for i in range(4)) + (3.0 * sign,) * 4 + (2.0,)
    path = local_chart.integrate(case, base, values, 512, lambda: None)
    half, diameter = path.field.half_width_mm, path.field.diameter_mm
    for i in range(1025):
        k, _, gradient = path.field.sample(i / 1024)
        minimum_j = 1 - half * abs(gradient)
        assert minimum_j > 0.1
        assert abs(k) * math.hypot(half, diameter / 2) < 0.78
        assert abs(k) * 3.1 * diameter < minimum_j


def test_clear_control_avoids_adjustment_work() -> None:
    """
    A clear straight path needs only coarse/fine replay and retains exact endpoints.
    """
    case = _case()
    path, metrics = local_clearance.refine(case, (0.0,) * 9 + (1.0,), lambda: None)
    assert metrics["evaluations"] == 2
    assert metrics["trials"] == []
    assert path.states[-1][:3] == pytest.approx((100, 0, 0))


@pytest.mark.parametrize("bad", [(0.0,) * 8, (float("nan"),) + (0.0,) * 7 + (1.0,)])
def test_invalid_coordinates_are_rejected(bad: tuple[float, ...]) -> None:
    """
    Invalid dimensions or nonfinite values cannot reach the integrator.
    """
    with pytest.raises(ValueError):
        local_chart.integrate(_case(), (0.0,) * 9 + (1.0,), bad, 64, lambda: None)
