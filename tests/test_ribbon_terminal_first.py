"""
Verify reverse shooting preserves material identity and reveals original-start misses.
"""

from __future__ import annotations

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase
from experiments.experiment_ribbon_route_discovery.solver import integrate
from experiments.experiment_ribbon_route_discovery.terminal_first import (
    both_end_errors,
    restore_order,
    reverse_case,
    reverse_coordinates,
)


def test_reversal_preserves_dense_paths_offsets_and_actual_derivatives() -> None:
    """
    Require every material lane to retrace the same cubic geometry in reverse.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    case = EndpointCase("independent-target", Vector3(0, 0, 0), Vector3(80, 0, 10), x, x, y, y)
    values = (1.0, -0.2, 0.3, -0.1, 0.2, 0.1, 0.2, -0.1, 0.1, 2.0)
    original = integrate(reverse_case(case), values, 128, lambda: None)
    restored = restore_order(case, original, values)
    assert reverse_case(reverse_case(case)) == case
    assert reverse_coordinates(reverse_coordinates(values)) == values
    for u in (0.0, 0.173, 0.6, 1.0):
        for q in (-10, 0, 10):
            a, da = original.lane(1 - u, q)
            b, db = restored.lane(u, q)
            assert magnitude(difference(a, b)) < 1e-10
            assert (da.x + db.x, da.y + db.y, da.z + db.z) == pytest.approx((0, 0, 0), abs=1e-10)
    errors = both_end_errors(case, restored)
    assert errors["maximum_gap_mm"] > 1
    assert magnitude(difference(restored.lane(1, 0)[0], case.end)) < 1e-12
