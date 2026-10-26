"""
Verify harness-sphere removal preserves every physical search-penalty component.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    CompatibleField,
    CompatiblePath,
    integrate_compatible,
)
from experiments.experiment_ribbon_cap_transition.director_route_objective import (
    ObjectiveScope,
    free_penalties,
    routing_penalties,
)
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_cap_transition.shooting_telemetry import components


def test_stress_sphere_does_not_enter_routing_penalties_or_request_a_pose() -> None:
    """
    Preserve all99local residuals while independently detecting an outside route.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("independent", Vector3(0, 0, 0), Vector3(20, 0, 0), x, x, y, y, 3, 1)
    field = CompatibleField(
        RoutingField("independent", 20, (1, 0.4, 0.2, 0), (0.1, -0.1, 0.2, 0), 3, 1)
    )
    path = integrate_compatible(field, 64, lambda: None)
    legacy = free_penalties(case, path)
    assert any(legacy[3::4])
    with patch.object(CompatiblePath, "pose", side_effect=AssertionError("No envelope query")):
        current = routing_penalties(case, path)
        relocated = routing_penalties(replace(case, end=Vector3(200, 300, 400)), path)
    assert current == tuple(v for i, v in enumerate(legacy) if i % 4 != 3)
    assert relocated == current
    errors = (0.0,) * 9 + current
    parts = components(errors, ObjectiveScope.ROUTING)
    assert "sphere" not in parts and sum(parts.values()) == sum(v * v for v in errors)
