"""
Exercise contact-interval selection independently of saved layouts and terminal labels.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import Penetration
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact, material_return
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    MaterialGuidance,
    ReturnLength,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.material_constraint import MaterialConstraint
from tests.test_ribbon_aesthetic import _route


def _witness(first: int, last: int, start: float = 0.0, end: float = 1.0) -> Penetration:
    """
    Supply material identities at a mocked strict-contact boundary.
    """
    return Penetration((first, last), (start, 0, 0), (end, 0, 0), Vector3(0, 0, 0))


@pytest.mark.parametrize("scale", (0.1, 1.0, 20.0))
@pytest.mark.parametrize("bank", (0.0, 0.3, -0.4))
def test_internal_straights_and_nonadjacent_folds_select_same_dominant_return(
    scale: float,
    bank: float,
) -> None:
    """
    Contact labels, straight length and scale do not exclude the intervening dominant turn.
    """
    source = _route(
        (
            Straight(2 * scale),
            fold(scale, 1.2, 0.5, bank, scale),
            Straight(8 * scale),
            fold(2 * scale, 1.2, -1.4, bank, scale),
            Straight(3 * scale),
            fold(scale, 1.2, 0.4, bank, scale),
            Straight(scale),
        )
    )
    for witness in (_witness(1, 5), _witness(2, 4), _witness(0, 6)):
        assert material_return.select_fold(source, witness) == 1


def test_partial_curved_endpoint_excludes_turn_outside_actual_collision_interval() -> None:
    """
    A large fold almost completed before the first witness must not outrank a smaller full fold.
    """
    source = _route((fold(2, 1.2, 2.5, 0, 0), Straight(3), fold(2, 1.2, 0.7, 0, 0), Straight(2)))
    assert material_return.select_fold(source, _witness(0, 3, 0.99)) == 1
    assert material_return.select_fold(source, _witness(0, 3)) == 0
    assert material_return.select_fold(source, _witness(1, 2, end=0.0)) is None


@pytest.mark.parametrize("pieces", ((-1, 2), (2, 1), (0, 9), (False, 2)))
def test_malformed_material_identity_is_not_silently_repaired(pieces: tuple[int, int]) -> None:
    """
    Reject invalid evidence before choosing any correction.
    """
    source = _route((Straight(2), fold(2, 1.2, 1, 0, 0), Straight(2)))
    with pytest.raises(ValueError, match="ordered"):
        material_return.select_fold(source, replace(_witness(0, 2), pieces=pieces))


@pytest.mark.parametrize("coordinate", (-0.1, 1.1, math.nan, True))
def test_invalid_contact_coordinate_does_not_select_a_fold(coordinate: float) -> None:
    """
    Incomplete or nonphysical material parameters never become reversal permission.
    """
    source = _route((Straight(2), fold(2, 1.2, 1, 0, 0), Straight(2)))
    with pytest.raises(ValueError, match="coordinates"):
        material_return.select_fold(source, _witness(0, 2, coordinate))


@pytest.mark.parametrize("length", tuple(ReturnLength))
def test_reflection_keeps_self_contact_under_explicit_length_policy(
    monkeypatch: pytest.MonkeyPatch,
    length: ReturnLength,
) -> None:
    """
    The real joint entry retains full material guidance alongside cap equations from its first step.
    """
    source = _route(
        (Straight(3), fold(2, 1.2, 1, 0, 1), Straight(4), fold(2, 1.2, -0.8, 0, 1), Straight(3))
    )
    captured: list[tuple[float, ...]] = []
    bind = Mock(wraps=MaterialConstraint.from_witness)
    monkeypatch.setattr(MaterialConstraint, "from_witness", bind)

    def projection(*args: Any, **_kwargs: Any) -> None:
        """
        Inspect actual initial equations, then stop without claiming physical coverage.
        """
        captured.append(args[3])

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projection)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        _witness(0, 4),
        Mock(spec=Gate),
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=2,
        mode=MaterialGuidance(0, length=length),
    )
    assert result is not None and result.contact is None and result.route is source
    bind.assert_called_once()
    assert bind.call_args.kwargs["axis_values"] == bind.call_args.args[0].initial
    assert captured and len(captured[0]) == (8 if length is ReturnLength.PARENT_CEILING else 7)
    if length is ReturnLength.PARENT_CEILING:
        assert abs(captured[0][6]) < 1e-13  # Equal parent length remains allowed.
    assert result.detail["flat_constraints"] == 1
    assert result.detail["method"] == "complete_material_return"
    assert result.detail["motion_regularization"] == "maximum_merit_squared"
    assert result.detail["newton_steps"] == 0 and result.detail["contact_pairs"] == 0


def test_curved_return_guidance_keeps_complete_material_bounds_and_spent_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A strict curved crossing initializes complete-piece guidance without guessing flat phases.
    """
    source = _route((fold(2, 1.2, 1, 0, 0), Straight(2), fold(2, 1.2, -1, 0, 0)))
    events: list[dict[str, Any]] = []
    projection = Mock(return_value=None)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projection)
    result = material_return.recover(
        source,
        _witness(0, 2, 0.5, 0.5),
        Mock(spec=Gate),
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=2,
    )
    assert result is not None and result.route is None and result.contact is None
    assert result.detail["flat_constraints"] == 1 and result.pairs == 0
    projection.assert_called_once()
    assert len(projection.call_args.args[3]) == 8
