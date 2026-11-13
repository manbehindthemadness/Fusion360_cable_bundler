"""
Keep endpoint closure on the signed material branch without extra nonlinear work.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_feature_insertion import material_allocation, repair
from experiments.experiment_ribbon_feature_insertion.continuation import (
    BranchPolicy,
    closest,
    material_continuous,
)
from experiments.experiment_ribbon_feature_insertion.features import Chain
from experiments.experiment_ribbon_feature_insertion.material_allocation import (
    bounded_material_correction,
)
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_joint_route.frames import Topology
from tests.test_ribbon_feature_insertion import _targets

IDENTITY = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]


@pytest.mark.parametrize("sign", (-1, 1))
def test_rotational_half_turn_alias_is_not_continuous_material(sign: int) -> None:
    """
    Small endpoint rotation across pi cannot reverse the signed material bend silently.
    """
    before = (fold(0.4, 1.2, sign * math.radians(179), 0.3, 0),)
    wrapped = (fold(0.4, 1.2, -sign * math.radians(179), 0.3, 0),)
    assert closest(before, (wrapped,)) is wrapped
    assert not material_continuous(before, wrapped)
    nearby = (replace(before[0], angle_radians=sign * math.radians(178)),)
    assert material_continuous(before, nearby)
    through_zero = (replace(before[0], angle_radians=-0.01),)
    assert material_continuous((replace(before[0], angle_radians=0.01),), through_zero)


@pytest.mark.parametrize("angle_sign", (-1, 1))
def test_coupled_linear_turn_bound_uses_legal_straight_transfer(angle_sign: int) -> None:
    """
    Analytically known coupling requires extra angle in x to preserve the bend while y closes.
    """
    # Endpoint equations: ax+t=.25*sign, ay=.25*sign, az=0; signed bend change<=.01.
    # The constrained optimum is ax=-.24*sign, ay=.25*sign, t=.49*sign.
    sign = float(angle_sign)
    length = 0.5 if sign > 0 else 3.0
    result = bounded_material_correction(
        IDENTITY,
        (-0.25 * sign, -0.25 * sign, 0),
        ((1, 0, 0),),
        (length,),
        3.0,
        (sign * (math.pi - 0.01),),
        ((1, 1, 0),),
        lambda: None,
        minimum_length=0.2,
    )
    assert result == pytest.approx((-0.24 * sign, 0.25 * sign, 0), abs=1e-9)
    assert result is not None
    transfer = 0.25 * sign - result[0]
    assert 0.2 <= length + transfer <= 3.0
    assert abs(sign * (math.pi - 0.01) + result[0] + result[1]) <= math.pi + 1e-9


def test_insufficient_straight_budget_cannot_bypass_signed_bend_domain() -> None:
    """
    An inconsistent turn/endpoint system is unresolved rather than an aliased correction.
    """
    assert (
        bounded_material_correction(
            IDENTITY,
            (-0.25, -0.25, 0),
            ((1, 0, 0),),
            (0.5,),
            0.7,
            (math.pi - 0.01,),
            ((1, 1, 0),),
            lambda: None,
        )
        is None
    )


def test_unconstrained_turns_keep_known_endpoint_and_native_floor_solution() -> None:
    """
    Removing angular restrictions recovers the exact interval-projection answer.
    """
    result = bounded_material_correction(
        IDENTITY,
        (2, 0, 0),
        ((1, 0, 0),),
        (0.5,),
        None,
        (),
        (),
        lambda: None,
        minimum_length=0.2,
    )
    assert result == pytest.approx((-1.7, 0, 0), abs=1e-10)


def test_full_newton_turn_miss_does_not_reject_a_legal_original_capped_step() -> None:
    """
    The solver must judge the actual partial motion rather than demand full endpoint closure first.
    """
    angle = -math.pi + 0.2
    result = bounded_material_correction(
        IDENTITY,
        (-1, 0, 0),
        (),
        (),
        None,
        (angle,),
        ((-0.24, 0, 0),),
        lambda: None,
    )
    assert result == pytest.approx((1, 0, 0))
    assert angle - 0.24 < -math.pi
    assert angle - 0.24 * math.pi / 4 > -math.pi


def test_material_projection_closes_only_cap_scaled_residual_when_needed() -> None:
    """
    An obstructed capped direction can redistribute the partial endpoint correction within legal travel.
    """
    result = bounded_material_correction(
        IDENTITY,
        (-1, -1, 0),
        ((1, 0, 0),),
        (0.5,),
        3,
        (math.pi - 0.1,),
        ((1, 1, 0),),
        lambda: None,
    )
    assert result == pytest.approx((0.1 - math.pi / 4, math.pi / 4, 0), abs=1e-9)
    assert result is not None
    factor = min(1.0, math.pi / (4 * math.sqrt(sum(value * value for value in result))))
    assert abs(math.pi - 0.1 + factor * (result[0] + result[1])) <= math.pi


def test_linear_material_system_is_covariant_under_world_rotation() -> None:
    """
    Material-angle rows stay intrinsic while endpoint columns and rays rotate together.
    """

    def rotate(vector: tuple[float, float, float]) -> tuple[float, float, float]:
        """
        Apply one authored rigid rotation to the complete endpoint equation.
        """
        x, y, z = vector
        return x * math.cos(0.7) - y * math.sin(0.7), x * math.sin(0.7) + y * math.cos(0.7), z

    result = bounded_material_correction(
        [rotate(column) for column in IDENTITY],
        rotate((-0.25, -0.25, 0)),
        (rotate((1, 0, 0)),),
        (0.5,),
        3,
        (math.pi - 0.01,),
        ((1, 1, 0),),
        lambda: None,
    )
    assert result == pytest.approx((-0.24, 0.25, 0), abs=1e-9)


def test_original_stop_and_sixteen_face_limit_cannot_renew_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Repeated violations never create an unbounded affine-face search or swallow cancellation.
    """
    project = Mock(return_value=[10.0, 10.0, 10.0])
    monkeypatch.setitem(vars(material_allocation), "_face", project)
    assert (
        bounded_material_correction(
            IDENTITY,
            (0, 0, 0),
            (),
            (),
            None,
            (math.pi - 0.1,) * 3,
            tuple(IDENTITY),
            lambda: None,
        )
        is None
    )
    assert project.call_count <= 16
    project.reset_mock()
    with pytest.raises(TimeoutError, match="original clock"):
        bounded_material_correction(
            IDENTITY,
            (0, 0, 0),
            (),
            (),
            None,
            (),
            (),
            Mock(side_effect=TimeoutError("original clock")),
        )
    project.assert_not_called()


def test_material_reframing_declines_alias_without_trying_another_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The opt-in finite-step guard does not change default rotational matching or root count.
    """
    previous = (fold(0.4, 1.2, math.radians(179), 0.3, 0),)
    following = (replace(previous[0], angle_radians=math.radians(-179)),)
    chain = Chain(Topology("authored", previous, None), (), (), 1, (0,))
    choices = Mock(return_value=(following,))
    monkeypatch.setitem(vars(repair), "rotation_choices", choices)
    boundary = Boundary(_targets(), 0.4)
    assert repair.reframed(boundary, chain, (), branch_policy=BranchPolicy.CONTINUOUS) is not None
    assert repair.reframed(boundary, chain, (), branch_policy=BranchPolicy.MATERIAL) is None
    assert choices.call_count == 2


def test_boundary_derivatives_use_only_original_six_perturbations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    One-sided derivatives at pi reuse the known current pose instead of differentiating a side jump.
    """
    geometries = tuple(
        fold(0.4, 1.04, angle, bank, 0)
        for angle, bank in (
            (0.4, 0.3),
            (-0.2, -0.3),
            (math.pi, -0.4),
            (-1.5, 0.4),
        )
    )
    pose = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    middle = pose
    for i, geometry in enumerate(geometries):
        pose = PlacedPiece(pose, geometry, "authored branch boundary").end_pose()
        if i == 1:
            middle = pose
    targets = replace(
        _targets(),
        lines=5,
        diameter_mm=0.2,
        end=pose.origin,
        end_tangent=pose.tangent,
        end_width=pose.width,
    )
    chain = Chain(Topology("boundary", geometries, None), (2,), (middle,), 2, (0, 0))
    boundary = Boundary(targets, 0.4)
    original = repair.reframed
    probes: list[Chain] = []

    def traced(*args: Any, **kwargs: Any) -> Chain | None:
        """
        Retain actual algebraic factor results without replacing geometry calculations.
        """
        result = original(*args, **kwargs)
        if result is not None:
            probes.append(result)
        return result

    monkeypatch.setitem(vars(repair), "reframed", traced)
    allocate = Mock(return_value=[0.01, 0, 0])
    monkeypatch.setitem(vars(repair), "bounded_material_correction", allocate)
    closure = repair.Closure((0.0,) * 9, (0, 0, 0), 0)
    assert repair.correction(
        boundary,
        chain,
        closure,
        lambda: None,
        branch_policy=BranchPolicy.MATERIAL,
        straight_motion=repair.StraightMotion.REALLOCATABLE,
    ) == [0.01, 0, 0]
    assert len(probes) == 6
    assert any(not material_continuous(geometries, probe.topology.folds) for probe in probes)
    allocate.assert_called_once()
    assert all(
        math.isfinite(value) and abs(value) < 100
        for column in allocate.call_args.args[0]
        for value in column
    )
    assert all(
        math.isfinite(value) and abs(value) < 100
        for column in allocate.call_args.args[6]
        for value in column
    )
