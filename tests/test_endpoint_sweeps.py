"""
Check trace interpolation, cap discrimination and sweep timing contracts.
"""

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_cap_transition.endpoint_caps import cap_matches
from experiments.experiment_ribbon_cap_transition.endpoint_first import endpoint_cases
from experiments.experiment_ribbon_cap_transition.endpoint_timing import timing_values
from experiments.experiment_ribbon_cap_transition.endpoint_trace_paths import (
    interpolate_trace,
    plan_trace_sweeps,
)


def test_coplanar_caps_match_their_own_endpoint_only() -> None:
    """
    Return-loop caps sharing a plane do not count each other as endpoint matches.
    """
    left, right = Vector3(-45, 0, 0), Vector3(45, 0, 0)
    normal = Vector3(0, 0, 1)
    assert cap_matches(left, normal, left, normal, left)
    assert cap_matches(right, Vector3(0, 0, -1), right, normal, right)
    assert not cap_matches(left, normal, right, normal, right)
    assert not cap_matches(left, normal, left, Vector3(1, 0, 0), left)
    assert not cap_matches(left, normal, left, normal, left.translated(Vector3(1, 0, 0), 0.001))


def test_interpolation_retains_caps_and_shared_interior_jets() -> None:
    """
    One exact cubic chain retains prescribed endpoint tangents and C1 joins.
    """
    points = (Vector3(0, 0, 0), Vector3(1, 1, 0), Vector3(2, 1, 1))
    x, z = Vector3(1, 0, 0), Vector3(0, 0, 1)
    path = interpolate_trace(1, points, x, z)
    assert path.controls[0] == points[0]
    assert path.controls[-1] == points[-1]
    assert magnitude(difference(unit(path.curves[0].derivative(0)), x)) < 1e-10
    assert magnitude(difference(unit(path.curves[-1].derivative(1)), z)) < 1e-10
    assert magnitude(difference(path.curves[0].derivative(1), path.curves[1].derivative(0))) < 1e-10
    assert len(path.knots) == len(path.controls) + 4
    assert path.knots[:4] == (0,) * 4
    assert path.knots[-4:] == (1,) * 4


def test_straight_trace_plan_retains_order_and_radius_certificate() -> None:
    """
    An independent small control produces three translated straight trace paths.
    """
    case = replace(
        endpoint_cases()[0], start=Vector3(-4, 0, 0), end=Vector3(4, 0, 0), lines=3, diameter_mm=1
    )
    paths, numerical = plan_trace_sweeps(case)
    assert [p.number for p in paths] == [1, 2, 3]
    assert [p.controls[0].y for p in paths] == [-1, 0, 1]
    assert all(p.controls[0].x == -4 and p.controls[-1].x == 4 for p in paths)
    assert numerical["trace_interpolation"]["maximum_curvature_bound_per_mm"] == pytest.approx(0)


def test_sweep_timing_excludes_audits_and_rejects_ambiguous_methods() -> None:
    """
    Sweep work is attributed once and is not reported as loft construction.
    """
    row = {
        "numerical_seconds": 0.003,
        "section_seconds": 1,
        "sweep_seconds": 2,
        "audit_seconds": 20,
    }
    assert timing_values(row) == {
        "solver_seconds": 0.003,
        "geometry_seconds": 3,
        "audit_seconds": 20,
    }
    row["loft_seconds"] = 2
    with pytest.raises(ValueError, match="mix loft and sweep"):
        timing_values(row)
