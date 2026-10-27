"""
Verify backward initialization preserves the ribbon chart and conductor identity.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery import broad_chart, reverse_initialization


def test_reversal_preserves_every_material_lane_and_local_bounds() -> None:
    """
    Reverse a spatial, nonconstant field from its actual end and compare full lanes.
    """
    case = EndpointCase(
        "spatial",
        Vector3(0, 0, 0),
        Vector3(100, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
    )
    values = (2.0, -0.2, 0.4, -0.3, 0.1, 0.2, -0.1, 0.3, -0.2, 2.0)
    path = broad_chart.integrate(case, values, 512, lambda: None)
    end = path.states[-1]
    authored = replace(
        case,
        end=Vector3(*end[:3]),
        end_tangent=Vector3(*end[3:6]),
        end_width=Vector3(*end[6:9]),
    )
    backward = reverse_initialization.reverse_case(authored)
    assert reverse_initialization.reverse_case(backward) == authored
    reversed_values = reverse_initialization.reverse_coordinates(values)
    assert reverse_initialization.reverse_coordinates(reversed_values) == values
    # The authored end changes chord length; preserve the carrier in this fixture.
    chord = sum(value * value for value in end[:3]) ** 0.5
    reversed_values = reversed_values[:9] + (200 / chord,)
    reverse = broad_chart.integrate(backward, reversed_values, 512, lambda: None)
    for index in range(33):
        u = index / 32
        f, r = path.field.carrier(u), reverse.field.carrier(1 - u)
        assert r.progress_mm == pytest.approx(f.progress_mm)
        assert r.turn == pytest.approx(-f.turn)
        assert r.eta == pytest.approx(-f.eta)
        assert r.eta_u == pytest.approx(f.eta_u)
        for offset in (-path.field.half_width_mm, 0, path.field.half_width_mm):
            position, tangent = path.lane(u, offset)
            other, direction = reverse.lane(1 - u, offset)
            assert (other.x, other.y, other.z) == pytest.approx(
                (position.x, position.y, position.z), abs=1e-7
            )
            assert (direction.x, direction.y, direction.z) == pytest.approx(
                (-tangent.x, -tangent.y, -tangent.z), abs=1e-7
            )
