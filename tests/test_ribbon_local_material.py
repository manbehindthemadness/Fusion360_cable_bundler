"""
Share validated local material without aliasing parameters, world poses or custom dispatch.
"""

from __future__ import annotations

import gc
import math
from dataclasses import asdict, replace
from typing import Callable, cast
from unittest.mock import Mock
from weakref import ref

import pytest

from cable_bundler.routing.geometry import Vector3, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_relaxation import flexible, local_material
from experiments.experiment_ribbon_fold_relaxation.flexible import FlexibleModel
from experiments.experiment_ribbon_fold_relaxation.local_material import LocalFolds
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_derivatives import Difference, jacobian
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("index", range(6))
def test_every_local_parameter_and_signed_zero_remain_authoritative(index: int) -> None:
    """
    Reuse exact floats only; no changed parameter or zero sign can return another shape.
    """
    cache = LocalFolds()
    values = [1.0, 1.2, 0.0, 2.0, 1.0, 1.0]
    first = cache(*values)
    assert cache(*values) is first
    changed = list(values)
    changed[index] += 0.1
    actual = cache(*changed)
    assert actual is not first and asdict(actual) == asdict(CylindricalFold(*changed))
    positive = cache(1.0, 1.2, 0.0, 2.0, 0.0, 0.0)
    negative = cache(1.0, 1.2, -0.0, 2.0, -0.0, -0.0)
    assert positive is not negative
    assert float(positive.bank_radians).hex() != float(negative.bank_radians).hex()
    assert float(positive.before_mm).hex() != float(negative.before_mm).hex()
    assert float(positive.after_mm).hex() != float(negative.after_mm).hex()


def test_nonfloat_validation_and_failed_construction_are_never_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A warm float entry grants neither integer representation conversion nor boolean acceptance.
    """
    constructor = Mock(wraps=CylindricalFold)
    monkeypatch.setitem(vars(local_material), "CylindricalFold", constructor)
    cache = LocalFolds()
    first = cache(1.0, 1.2, 0.0, 2.0, 1.0, 1.0)
    assert cache(1.0, 1.2, 0.0, 2.0, 1.0, 1.0) is first
    assert constructor.call_count == 1
    for _ in range(2):
        integer = cache(1, 1.2, 0.0, 2.0, 1.0, 1.0)
        assert type(integer.radius_mm) is int and integer is not first
        for invalid in (True, math.nan, math.inf, -1.0):
            with pytest.raises(ValueError):
                cache(invalid, 1.2, 0.0, 2.0, 1.0, 1.0)
    assert constructor.call_count == 11


def test_local_store_is_bounded_private_and_does_not_retain_its_material_model() -> None:
    """
    Eviction and model release cannot leak routes through a globally retained preparation cache.
    """
    cache = LocalFolds()
    first = cache(1.0, 1.2, 0.0, 2.0, 1.0, 1.0)
    for index in range(64):
        cache(float(index + 2), 1.2, 0.0, 2.0, 1.0, 1.0)
    assert cache(1.0, 1.2, 0.0, 2.0, 1.0, 1.0) is not first
    other = LocalFolds()(1.0, 1.2, 0.0, 2.0, 1.0, 1.0)
    assert other == first and other is not first
    route = _route((Straight(3), fold(1, 1.2, 1.1, 0.3, 0), Straight(4)))
    model = FlexibleModel(route)
    model.pieces(model.initial)
    retained_cache = model._local_folds
    model_reference, route_reference = ref(model), ref(route)
    del model, route
    gc.collect()
    assert model_reference() is None and route_reference() is None
    assert retained_cache(1.0, 1.2, 0.0, 2.0, 1.0, 1.0) == first


def test_terminal_sample_is_local_immutable_and_absent_from_serialized_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Distinct world placements share one local sample while retaining all original frame bits.
    """
    geometry = CylindricalFold(1.0, -1.2, 0.3, 2.0, 1.0, 1.0)
    expected_fields = asdict(geometry)
    original = cast(
        Callable[[CylindricalFold, float, float], tuple[Vector3, Vector3, Vector3, Vector3]],
        vars(CylindricalFold)["surface"],
    )
    calls = []

    def surface(
        self: CylindricalFold, u: float, q: float
    ) -> tuple[Vector3, Vector3, Vector3, Vector3]:
        """
        Observe local evaluation without substituting its material arithmetic.
        """
        calls.append((u, q))
        return original(self, u, q)

    monkeypatch.setattr(CylindricalFold, "surface", surface)
    for pose in (
        Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)),
        Pose(Vector3(10, -3, 4), Vector3(0, 1, 0), Vector3(0, 0, 1)),
    ):
        local_point, local_forward, local_width, _ = original(geometry, 1, 0)
        forward = unit(pose.direction(local_forward))
        width = pose.direction(local_width)
        expected = Pose(
            pose.point(local_point), forward, unit(width.translated(forward, -dot(width, forward)))
        )
        assert PlacedPiece(pose, geometry, "authored placement").end_pose() == expected
    assert calls == [(1, 0)]
    assert asdict(geometry) == expected_fields
    changed = replace(geometry, angle_radians=1.1)
    assert "terminal_surface" not in changed.__dict__
    assert changed.terminal_surface == original(changed, 1, 0)
    assert calls == [(1, 0), (1, 0)]


def test_custom_fold_surface_keeps_its_original_dispatch() -> None:
    """
    A specialized fold never inherits the base-fold terminal shortcut implicitly.
    """
    calls = []

    class CustomFold(CylindricalFold):
        """
        Expose an observable specialized material surface.
        """

        def surface(self, u: float, q: float) -> tuple[Vector3, Vector3, Vector3, Vector3]:
            """
            Retain the actual material values while observing every original call.
            """
            calls.append((u, q))
            return super().surface(u, q)

    geometry = CustomFold(1.0, 1.2, 0.0, 2.0, 0.0, 0.0)
    for x in (0, 10):
        piece = PlacedPiece(
            Pose(Vector3(x, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), geometry, "custom fold"
        )
        piece.end_pose()
    assert calls == [(1, 0), (1, 0)] and "terminal_surface" not in geometry.__dict__


@pytest.mark.parametrize("count", (1, 4, 8, 12))
def test_prepared_material_retains_complete_joint_derivative_bits(
    count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Compare full ordered-frame derivatives with original uncached local construction.
    """
    material: list[Straight | CylindricalFold] = [Straight(3)]
    for index in range(count):
        material.extend(
            (
                fold(1 + index * 0.03, 1.2, (-1) ** index * 1.1, (-1) ** index * 0.3, 0.1),
                Straight(4),
            )
        )
    route = _route(tuple(material))
    results = []
    for prepared in (False, True):
        with monkeypatch.context() as context:
            if not prepared:
                context.setattr(flexible, "LocalFolds", Mock(return_value=CylindricalFold))
            model = SignedJoints(route)
            evaluation = JointEvaluation(model.residual, model.admissible)
            results.append(
                jacobian(
                    model,
                    model.initial,
                    evaluation.equations,
                    6,
                    frozenset(),
                    lambda: None,
                    admissible=evaluation.admissible,
                    difference=Difference.ONE_SIDED,
                )
            )
    assert [[value.hex() for value in row] for row in results[0]] == [
        [value.hex() for value in row] for row in results[1]
    ]
