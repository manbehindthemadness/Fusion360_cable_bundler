"""
Check paired diagnostics against an exact parabola and a deliberate cubic error.
"""

import pytest

from cable_bundler.routing.geometry import CubicBezier, Vector3, unit
from experiments.experiment_ribbon_cap_transition.clamped_diagnostic import compare_paths
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.endpoint_trace_paths import TracePath
from experiments.experiment_ribbon_cap_transition.native_budget import NativeBudget


@pytest.mark.parametrize("perturb", (False, True))
def test_paired_curvature_distinguishes_interpolation_error(perturb: bool) -> None:
    """
    Exact cubic interpolation matches analytic curvature and scaling; damage differs.
    """
    case = EndpointCase(
        "parabola",
        Vector3(0, 0, 0),
        Vector3(1, 1, 0),
        Vector3(1, 0, 0),
        unit(Vector3(1, 2, 0)),
        Vector3(0, 0, 1),
        Vector3(0, 0, 1),
        lines=1,
        diameter_mm=0.01,
    )
    points = tuple(Vector3(i / 7, i * (i - 1) / 42, 0) for i in range(8))
    curves = []
    for segment in range(32):
        a, b = segment / 32, (segment + 1) / 32
        start, end = Vector3(a, a * a, 0), Vector3(b, b * b, 0)
        control_a = start.translated(Vector3(1, 2 * a, 0), 1 / 96)
        if perturb and segment == 16:
            control_a = control_a.translated(Vector3(0, 0, 1), 0.02)
        curves.append(
            CubicBezier(start, control_a, end.translated(Vector3(1, 2 * b, 0), -1 / 96), end)
        )
    path = TracePath(1, tuple(curves), (), ())
    budget = NativeBudget(memory=lambda: 1000)
    result = compare_paths(case, points, (path,), budget)
    assert result["observations_per_field"] == 288
    assert result["analytic_smallest_observed"]["radius_mm"] == pytest.approx(0.5)
    if perturb:
        assert result["max_position_error_mm"] > 0.005
        assert result["max_heading_error_degrees"] > 1
        assert result["max_global_acceleration_error_mm"] > 1
        assert result["cubic_smallest_observed"]["radius_mm"] < 0.5
    else:
        assert result["max_position_error_mm"] < 1e-12
        assert result["max_heading_error_degrees"] < 2e-6
        assert result["max_global_acceleration_error_mm"] < 1e-10
        assert result["cubic_smallest_observed"]["radius_mm"] == pytest.approx(0.5)
