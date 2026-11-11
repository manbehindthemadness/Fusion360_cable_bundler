"""
Reuse exact material measurements without transferring acceptance to changed geometry.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterator

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from tests.test_ribbon_aesthetic import _route


@pytest.fixture(autouse=True)
def empty_metric_cache() -> Iterator[None]:
    """
    Model a cold worker and prevent instrumented measurements from leaking between controls.
    """
    material_error.cache_clear()
    yield
    material_error.cache_clear()


def test_nested_checks_reuse_one_complete_raw_measurement() -> None:
    """
    Preserve every first measurement sample while avoiding two repeated complete evaluations.
    """
    route = _route((Straight(7.1234), fold(3.7, 1.2, 0.91, 0.17, 1.3), Straight(4.2345)))
    calls: list[tuple[float, float]] = []

    class CountedPiece(PlacedPiece):
        """
        Count the inherited material map without changing its returned measurements.
        """

        def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
            """
            Observe a world-space sample through the unchanged parent implementation.
            """
            calls.append((u, q))
            return super().surface(u, q)

    route = replace(
        route, pieces=tuple(CountedPiece(p.pose, p.geometry, p.label) for p in route.pieces)
    )
    values = [material_error(route), material_error(route), material_error(replace(route))]
    assert values[0] == values[1] == values[2] and values[0] < 1e-12
    assert len(calls) == 15 * len(route.pieces)


def test_changed_pose_geometry_profile_or_order_cannot_inherit_a_raw_measurement() -> None:
    """
    Keep full immutable keys, including actual world frames and target profile width.
    """
    route = _route((Straight(2.125), Straight(3.25)))
    first = route.pieces[0]
    changed_pose = replace(first, pose=replace(first.pose, width=Vector3(0, 1.02, 0)))
    variants = (
        replace(route, pieces=(changed_pose, route.pieces[1])),
        replace(route, pieces=(replace(first, geometry=Straight(2.25)), route.pieces[1])),
        replace(route, targets=replace(route.targets, lines=2)),
        replace(route, pieces=tuple(reversed(route.pieces))),
    )
    assert material_error(route) < 1e-12
    assert material_error(variants[0]) > 0.01
    assert material_error(variants[0]) > 0.01
    for variant in variants[1:]:
        assert material_error(variant) < 1e-12
    info = material_error.cache_info()
    assert info.misses == 5 and info.hits == 1


def test_raw_measurement_retention_is_bounded_and_evicted_routes_are_measured_again() -> None:
    """
    A worker cannot retain more than64complete routes regardless of its finite proposal history.
    """
    first = _route((Straight(2.125),))
    assert material_error(first) == 0.0
    for index in range(64):
        assert material_error(_route((Straight(3.125 + index),))) == 0.0
    info = material_error.cache_info()
    assert info.maxsize == info.currsize == 64 and info.misses == 65
    assert material_error(first) == 0.0
    assert material_error.cache_info().misses == 66


def test_invalid_wider_profile_cannot_borrow_a_previous_valid_fold_measurement() -> None:
    """
    A changed profile still reaches the original material-coordinate domain validation.
    """
    route = _route((fold(3.7, 1.2, 0.91, 0.17, 1.3),))
    assert material_error(route) < 1e-12
    wider = replace(route, targets=replace(route.targets, lines=2))
    for _ in range(2):
        with pytest.raises(ValueError, match="within the material strip"):
            material_error(wider)
    assert material_error.cache_info().currsize == 1
