"""
Challenge the compatible-edge chart independently of endpoint fitting.
"""

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.compatible_strip import (
    BendMapping,
    CompatibleField,
    integrate_compatible,
    map_turn,
)
from experiments.experiment_ribbon_cap_transition.director_routing_field import RoutingField


def _field() -> CompatibleField:
    """
    Author a mixed bend/ruling field without using an endpoint solver or witness.
    """
    return CompatibleField(
        RoutingField("mixed", 150, (2.0, -0.4, 1.2, 0.6), (0.4, -0.4, 0.7, -0.2), 19, 1.5, 0.2, 0.1)
    )


@pytest.mark.parametrize("dimensions", [(7, 0.6), (19, 1.5), (40, 0.7)])
@pytest.mark.parametrize("length", [0.5, 150.0, 1000.0])
@pytest.mark.parametrize("mapping", tuple(BendMapping))
def test_extreme_coordinates_preserve_full_width_local_bounds(
    dimensions: tuple[int, float], length: float, mapping: BendMapping
) -> None:
    """
    Exclude folding and curvature violations without a sampled optimizer guard.
    """
    raw = RoutingField(
        "extreme", length, (4 * math.pi,) * 4, (3, -3, -3, 3), *dimensions, -4 * math.pi, -3
    )
    field = CompatibleField(raw, mapping)
    reach = math.hypot(field.half_width_mm, field.diameter_mm / 2)
    for i in range(513):
        value = field.carrier(i / 512)
        k, _, gradient = field.sample(i / 512)
        minimum_j = 1 - field.half_width_mm * abs(gradient)
        assert minimum_j > 0.1
        assert abs(k) * reach < 0.78
        assert 3.1 * field.diameter_mm * abs(k) / minimum_j < 1
        a = value.progress_mm + field.half_width_mm * value.eta_u
        b = value.progress_mm - field.half_width_mm * value.eta_u
        assert min(a, b) > 0
        assert max(a, b) == pytest.approx(length)


@pytest.mark.parametrize("mapping", tuple(BendMapping))
def test_zero_bend_cannot_rotate_material_width(mapping: BendMapping) -> None:
    """
    Prevent a straight centerline from acquiring a longitudinal material twist.
    """
    field = CompatibleField(replace(_field().raw, bending=(0, 0, 0, 0), extra_bending=0), mapping)
    path = integrate_compatible(field, 512, lambda: None)
    for state in path.states:
        assert Vector3(*state[6:9]) == Vector3(0, 1, 0)
        assert state[1] == 0 and state[2] == 0


@pytest.mark.parametrize("mapping", tuple(BendMapping))
def test_actual_lane_derivative_matches_dense_positions_and_model_at_nodes(
    mapping: BendMapping,
) -> None:
    """
    Differentiate the real interpolant instead of assuming unit parameter speed.
    """
    field = replace(_field(), bend_mapping=mapping)
    path = integrate_compatible(field, 512, lambda: None)
    for u in (0.173, 0.321, 0.704):
        step = 1e-6
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            _, derivative = path.lane(u, q)
            before, after = path.lane(u - step, q)[0], path.lane(u + step, q)[0]
            numerical = Vector3(
                *(
                    a / (2 * step)
                    for a in (after.x - before.x, after.y - before.y, after.z - before.z)
                )
            )
            assert magnitude(difference(derivative, numerical)) < 1e-6
    for i in range(0, 513, 31):
        u = i / 512
        sample = field.carrier(u)
        state, _ = path.pose(u)
        tangent = Vector3(*state[3:6])
        for q in (-field.half_width_mm, field.half_width_mm):
            _, derivative = path.lane(u, q)
            expected = sample.progress_mm + q * sample.eta_u
            assert dot(derivative, tangent) == pytest.approx(expected, abs=1e-10)


@pytest.mark.parametrize("mapping", tuple(BendMapping))
def test_independent_grids_converge_without_moving_the_endpoints(mapping: BendMapping) -> None:
    """
    Bound finite transport/interpolation error separately from analytic field bounds.
    """
    field = replace(_field(), bend_mapping=mapping)
    coarse = integrate_compatible(field, 256, lambda: None)
    fine = integrate_compatible(field, 512, lambda: None)
    for i in range(41):
        u = (i + 0.5) / 41
        for q in (-field.half_width_mm, 0, field.half_width_mm):
            assert magnitude(difference(coarse.lane(u, q)[0], fine.lane(u, q)[0])) < 0.005
    assert not hasattr(field, "length_mm")
    assert fine.field is field


def test_near_limit_mapping_preserves_requested_bends_and_stays_bounded() -> None:
    """
    Keep signs, scale covariance and exact sublimit requests without a hard corner.
    """
    for limit in (0.01, 1.0, 1000.0):
        for fraction in (-0.9, -0.874272343, -0.5, 0, 0.5, 0.874272343, 0.9):
            requested = fraction * limit
            assert map_turn(requested, limit, BendMapping.NEAR_LIMIT) == requested
        values = [map_turn(i * limit / 100, limit, BendMapping.NEAR_LIMIT) for i in range(501)]
        assert all(a <= b for a, b in zip(values, values[1:]))
        assert max(values) < limit
        assert map_turn(1.5 * limit, limit, BendMapping.NEAR_LIMIT) > 0.99 * limit
        for requested in (0.91, 1.0, 1.5, 100.0):
            positive = map_turn(requested * limit, limit, BendMapping.NEAR_LIMIT)
            assert map_turn(-requested * limit, limit, BendMapping.NEAR_LIMIT) == -positive
            assert positive / limit == pytest.approx(map_turn(requested, 1, BendMapping.NEAR_LIMIT))
        step = limit * 1e-5
        knee = 0.9 * limit
        slope = (map_turn(knee + step, limit, BendMapping.NEAR_LIMIT) - knee) / step
        assert slope == pytest.approx(1, abs=1e-6)
