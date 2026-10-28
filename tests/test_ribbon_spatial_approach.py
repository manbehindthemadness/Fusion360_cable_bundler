"""
Verify finite approach geometry and observable spatial motion without physical relaxation.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import spatial_approach


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ((-1, -3, 0), (-1, 3, 0), 0),
        ((-1, -3, 2), (-1, 3, 2), 2),
        ((2, -3, 0), (2, 3, 0), 2),
        ((-4, 0, 0), (-3, 0, 0), 1),
    ],
)
def test_finite_rectangle_covers_full_segment(
    a: tuple[float, ...], b: tuple[float, ...], expected: float
) -> None:
    """
    Catch width crossings missed by endpoints while allowing passage outside the rectangle.
    """
    assert spatial_approach.segment_rectangle_distance(a, b, 2, 1) == pytest.approx(expected)


def _case() -> EndpointCase:
    """
    Supply a neutral boundary for deterministic routing guidance checks.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return EndpointCase("spatial", Vector3(0, 0, 0), Vector3(100, 0, 0), x, x, y, y)


def test_guidance_scales_with_geometry_and_keeps_approach_aligned() -> None:
    """
    Width-based waypoints scale with the fixture and both sides share the final approach.
    """
    case = _case()
    first = spatial_approach.Approach(case, 1)
    opposite = spatial_approach.Approach(case, -1)
    scaled = spatial_approach.Approach(
        replace(case, end=Vector3(200, 0, 0), diameter_mm=case.diameter_mm * 2), 1
    )
    assert first.targets[-1] == opposite.targets[-1]
    assert first.targets[0][1].z == -opposite.targets[0][1].z
    for (_, p), (_, q) in zip(first.targets, scaled.targets):
        assert (q.x, q.y, q.z) == pytest.approx((2 * p.x, 2 * p.y, 2 * p.z))


def test_fitting_reports_real_displacement_and_bounds_work() -> None:
    """
    Spatial guidance moves a neutral baseline rather than merely renaming its budget.
    """
    values = (0.0,) * 9 + (1.0,)
    _, metrics = spatial_approach.refine(_case(), values, 1, lambda: None)
    assert metrics["evaluations"] <= 520
    assert any(t["accepted"] for t in metrics["trials"])
    assert metrics["maximum_center_displacement_mm"] > 1e-3
    assert 0 < metrics["rms_center_displacement_mm"] <= metrics["maximum_center_displacement_mm"]
