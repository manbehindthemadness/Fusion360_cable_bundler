"""
Verify projected angular equations against an independent analytical endpoint map.
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion import repair
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.repair import Closure, StraightMotion
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from tests.test_ribbon_feature_insertion import _targets


@pytest.mark.parametrize("domain", ("free", "sum_face", "zero_slot"))
def test_angular_projection_uses_only_legal_positive_straight_transfers(
    domain: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Solve a known endpoint map without spending angle motion on legal runway compensation.

    The map is (s0+a0+a2, s1+a0+10*a1, a0). With both straights positive,
    X/Y can move freely below the sum budget; at its boundary only their
    difference is free. A zero second slot cannot borrow negative travel.
    These are affine equations, not a saved or complete ribbon configuration.
    """
    epsilon = 0.01
    second = 0.0 if domain == "zero_slot" else 1.0
    targets = replace(_targets(), diameter_mm=1.0, end=Vector3(1, second, epsilon))
    boundary = Boundary(targets, 0.6)
    chain = Mock(spec=Chain, targets=((0.0, 0.0, 0.0),), topology=(0.0, 0.0, 0.0))
    probes: list[tuple[float, ...]] = []

    def changed(
        references: tuple[tuple[float, ...], ...], delta: list[float], scale: float
    ) -> tuple[tuple[float, ...], ...]:
        """
        Express a shared reference's three analytical angle coordinates without a geometry fixture.
        """
        return (tuple(value + scale * d for value, d in zip(references[0], delta)),)

    def reframed(
        source: Boundary, original: Any, references: tuple[tuple[float, ...], ...], **kwargs: Any
    ) -> Any:
        """
        Retain the perturbed reference as the analytical model's orientation coordinates.
        """
        del source, original, kwargs
        return SimpleNamespace(topology=references[0])

    def model(source: Boundary, angles: tuple[float, ...]) -> Any:
        """
        Provide exact straight rays and the independent endpoint map for finite differentiation.
        """
        del source

        def endpoint(values: tuple[float, ...]) -> Pose:
            """
            Evaluate actual cap displacement rather than substituting a derivative matrix result.
            """
            probes.append(angles)
            a0, a1, a2 = angles
            return Pose(
                Vector3(values[0] + a0 + a2, values[2] + a0 + 10 * a1, a0),
                Vector3(1, 0, 0),
                Vector3(0, 1, 0),
            )

        return SimpleNamespace(
            endpoint=endpoint,
            equations=lambda: (((1, 0, 0), (0, 0, 0), (0, 1, 0)), (1, second, epsilon)),
        )

    monkeypatch.setitem(vars(repair), "changed", changed)
    monkeypatch.setitem(vars(repair), "reframed", reframed)
    monkeypatch.setitem(vars(repair), "Model", model)
    closure = Closure((1.0, 0.0, second), (0.0, 0.0, -epsilon), epsilon)
    budget = 2.0 if domain == "sum_face" else None
    fixed = repair.correction(boundary, chain, closure, lambda: None, maximum_straight_mm=budget)
    coupled = repair.correction(
        boundary,
        chain,
        closure,
        lambda: None,
        straight_motion=StraightMotion.REALLOCATABLE,
        maximum_straight_mm=budget,
    )
    assert len(probes) == 12
    assert fixed is not None
    assert coupled is not None
    projected = tuple(coupled)
    expected = (
        (epsilon, -20 * epsilon / 101, -2 * epsilon / 101)
        if domain == "sum_face"
        else (epsilon, -epsilon / 10 if domain == "zero_slot" else 0.0, 0.0)
    )
    assert projected == pytest.approx(expected, abs=1e-11)
    assert math.fsum(d * d for d in projected) < math.fsum(d * d for d in fixed)
    # The fixed direction crosses a hypothetical material-angle boundary; legal transfers avoid it.
    assert fixed[2] < -epsilon / 2 < projected[2]
    s0, s1 = 1 - projected[0] - projected[2], second - projected[0] - 10 * projected[1]
    assert min(s0, s1) >= -1e-11
    if budget is not None:
        assert s0 + s1 == pytest.approx(budget, abs=1e-11)
    if domain == "zero_slot":
        assert abs(s1) < 1e-11
    end = model(boundary, projected).endpoint((s0, 0.0, s1)).origin
    assert (end.x, end.y, end.z) == pytest.approx((1, second, epsilon), abs=1e-11)
