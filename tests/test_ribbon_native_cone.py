"""
Keep native-size admissibility consistent across endpoint projection and optional guide allocation.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion import allocation
from experiments.experiment_ribbon_feature_insertion.angular_allocation import bounded_correction
from experiments.experiment_ribbon_feature_insertion.features import chains
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.native_cone import project
from experiments.experiment_ribbon_feature_insertion.repair import nearest
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_fold_route.native_length import minimum_coordinate
from experiments.experiment_ribbon_joint_route.allocation import Model
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
def test_native_projection_preserves_a_real_endpoint_deficit_until_orientation_can_close(
    scale: float,
) -> None:
    """
    A one-ray authored map must not call a sub-native positive closure buildable at any physical scale.
    """
    epsilon, threshold = 2e-6, 1e-5
    target = replace(_targets(), diameter_mm=scale, end=Vector3(epsilon * scale, 0, 0))
    model = Mock(
        spec=Model,
        size=1,
        topology=SimpleNamespace(folds=()),
        source=SimpleNamespace(targets=target),
    )
    model.equations.return_value = (((1.0, 0.0, 0.0),), (epsilon, 0.0, 0.0))

    def endpoint(values: tuple[float, ...]) -> Pose:
        """
        Measure the same actual affine displacement as the supplied ray equation.
        """
        return Pose(Vector3(values[0] * scale, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))

    model.endpoint.side_effect = endpoint
    assert nearest(model, lambda: None).error < 1e-12
    native = nearest(model, lambda: None, minimum_straight_mm=threshold * scale)
    assert native.values == (0.0,) and native.error == pytest.approx(epsilon)
    floor = minimum_coordinate(threshold * scale, scale)
    assert floor is not None and floor * scale > threshold * scale
    # An independently specified angular displacement can close with the valid floor.
    result = project([[1.0]], [floor], 1, floor, None, lambda: None)
    assert result == [floor]


@pytest.mark.parametrize(
    "rows,right,minimum,budget,expected",
    (
        ([[1.0, 0.0], [0.0, 1.0]], [-0.1, 1.0], 0.2, None, [0.2, 1.0]),
        ([[1.0, -1.0], [0.0, 1.0]], [0.0, 1.0], 0.2, 1.0, [0.4, 0.6]),
        ([[1.0, 0.0], [0.0, 1.0]], [0.4, 0.6], 0.2, 1.2, [0.4, 0.6]),
        ([[1.0, 0.0], [0.0, 1.0]], [0.4, 0.6], 0.7, 1.0, None),
    ),
)
def test_original_support_respects_lower_and_total_faces(
    rows: list[list[float]],
    right: list[float],
    minimum: float,
    budget: float | None,
    expected: list[float] | None,
) -> None:
    """
    Check exact independent QP optima without ribbon geometry or historical fixture inputs.
    """
    result = project(rows, right, 2, minimum, budget, lambda: None)
    assert result is None if expected is None else result == pytest.approx(expected)


@pytest.mark.parametrize("budget", (None, 2e-5))
def test_angular_elimination_retains_the_same_native_lower_face(budget: float | None) -> None:
    """
    Exact endpoint residual alone cannot hide an angular correction required by native material size.
    """
    result = bounded_correction(
        [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
        (0.0, 0.0, 0.0),
        ((1.0, 0.0, 0.0),),
        (2e-6,),
        budget,
        lambda: None,
        minimum_length=1e-5,
    )
    assert result == pytest.approx([-8e-6, 0.0, 0.0], abs=1e-14)


def _fitted() -> allocation.Allocation:
    """
    Supply one independently authored cap/material allocation, without a saved gym input.
    """
    frames = Frames.create(_targets())
    boundary = Boundary(frames.targets, 0.101)
    for chain in chains(boundary, frames, (0.5,), lambda: None, lambda event: None):
        result = allocation.fit(boundary, chain, 1e-5, lambda: None, lambda event: None)
        if result is not None:
            return result
    raise AssertionError("Analytical control must supply a cap-closed allocation")


def test_optional_guide_fit_cannot_erase_a_measured_admissible_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reuse the same coordinates only after all original allocation checks, without extra mask attempts.
    """
    source = _fitted()
    project_fit = Mock(return_value=None)
    monkeypatch.setitem(vars(allocation), "least_squares", project_fit)
    events: list[dict[str, Any]] = []
    result = allocation.fit(
        Boundary(source.route.targets, source.route.radius_mm),
        source.chain,
        1e-5,
        lambda: None,
        events.append,
        feasible_values=source.values,
    )
    assert result is not None and result.values == source.values and result.score == source.score
    assert project_fit.call_count == source.masks
    assert events[-1]["status"] == "native_cone_verified"


@pytest.mark.parametrize("broken", ("cap_error", "material_error"))
def test_measured_closure_never_bypasses_the_full_material_contract(
    monkeypatch: pytest.MonkeyPatch,
    broken: str,
) -> None:
    """
    Native-sized algebraic coordinates remain rejected when an independent full-route check fails.
    """
    source = _fitted()
    monkeypatch.setattr(allocation, broken, Mock(return_value=1.0))
    result = allocation.closure_allocation(
        Boundary(source.route.targets, source.route.radius_mm),
        source.chain,
        source.values,
        1e-5,
        lambda: None,
        lambda event: None,
    )
    assert result is None


@pytest.mark.parametrize("invalid", ("sliver", "negative", "radius", "budget"))
def test_measured_closure_preserves_native_radius_and_original_travel_rules(invalid: str) -> None:
    """
    A measured coordinate vector receives no exemption from the original allocation domain.
    """
    source = _fitted()
    values = list(source.values)
    index = next(i for i in range(0, len(values), 2) if values[i] > 0)
    if invalid == "sliver":
        values[index] = 5e-6 / source.route.targets.diameter_mm
    elif invalid == "negative":
        values[index] = -1.0
    elif invalid == "radius":
        values[1] = 1e-6
    result = allocation.closure_allocation(
        Boundary(source.route.targets, source.route.radius_mm),
        source.chain,
        tuple(values),
        1e-5,
        lambda: None,
        lambda event: None,
        maximum_straight_mm=0.0 if invalid == "budget" else None,
    )
    assert result is None


def test_three_ray_projection_keeps_eight_lower_faces_and_the_original_stop() -> None:
    """
    Bound algebra on one original support and propagate cancellation without another attempt.
    """
    rows = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    checkpoint = Mock()
    assert project(rows, [-1.0, -2.0, -3.0], 3, 0.2, 2.0, checkpoint) == [0.2] * 3
    assert checkpoint.call_count == 8
    with pytest.raises(TimeoutError, match="unchanged stop"):
        project(rows, [0.0] * 3, 3, 0.2, None, Mock(side_effect=TimeoutError("unchanged stop")))
