"""
Check cached spatial diagnostics against independent straight-strip measurements.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.api import Candidate, analyze
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    CompatibleField,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.constraint_interaction import inspect
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase


@pytest.mark.parametrize("length", (10.0, 20.0))
def test_cached_straight_strip_preserves_clearance_and_objective(length: float) -> None:
    """
    Detect sphere excess without inventing bending, folding or a missing endpoint.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("straight", Vector3(0, 0, 0), Vector3(length, 0, 0), x, x, y, y, 3, 1)
    field = CompatibleField(RoutingField("straight", length, (0, 0, 0, 0), (0, 0, 0, 0), 3, 1))
    path = integrate_compatible(field, 64, lambda: None, initial=(0, 0, 0, 1, 0, 0, 0, 1, 0))
    evidence = analyze(Candidate("straight", path, case, "independent fixture"), intervals=16)
    sphere_score = sum(
        (0.2 * math.log1p(max(0, (math.hypot(length * (i / 32 - 0.5), 1.6) + 0.5) / 7.275 - 1)))
        ** 2
        for i in range(33)
    )
    metrics = {"stages": [{"history": [sphere_score, sphere_score]}]}
    result = inspect(path, case, evidence, metrics, lambda: None)
    assert result.evidence_fingerprint == evidence.fingerprint
    assert len(result.stations) == 257
    assert all(s.center_use == 0 and s.minimum_j == 1 for s in result.stations)
    assert all(s.surface_curvature_per_mm == 0 for s in result.stations)
    assert result.stations[-1].target_distance_mm == pytest.approx(0, abs=1e-12)
    assert result.stations[0].sphere_use == pytest.approx((math.hypot(length / 2, 1.6) + 0.5) / 7.5)
    assert dict(result.objective)["sphere"] == pytest.approx(sphere_score)
    assert sum(v for k, v in result.objective if k != "sphere") < 1e-25
    assert result.fine_unchanged_rounds == 1
    with pytest.raises(ValueError, match="retained fit score"):
        inspect(path, case, evidence, {"stages": [{"history": [42]}]}, lambda: None)
