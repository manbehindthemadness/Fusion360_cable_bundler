"""
Replace stale hardware guidance only with a separating bound for the same complete material member.
"""

from __future__ import annotations

from dataclasses import replace
from math import pi
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot
from experiments.experiment_ribbon_feature_insertion.separation import Region, Side
from experiments.experiment_ribbon_fold_route.contact_inverse import occupied_coordinates
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import hardware_halfspaces
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route


def _plane(scale: float, bank: float, sign: float) -> FeaturePlane:
    """
    Place a complete fold beyond the start box, with a deliberately stale width-axis constraint.
    """
    source = _route(
        (Straight(5 * scale), fold(2 * scale, 1.2 * scale, sign, bank, scale), Straight(3 * scale))
    )
    source = replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)
    model = SignedJoints(source)
    box = Hardware.create(source.targets, Dimensions(10 * scale, 10 * scale, 10 * scale)).boxes[0]
    member = Region(0, False)
    return FeaturePlane(model, member, (member,), box, 1, Side.BEFORE)


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.4))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_full_separated_member_replaces_stale_axis_without_changing_material(
    scale: float, bank: float, sign: float
) -> None:
    """
    A positive whole-fold gap on another axis removes only the artificial guidance deficit.
    """
    old = _plane(scale, bank, sign)
    values = old.model.initial
    assert old.gap(values) < 0
    checks = Mock()
    original = [old]
    result = hardware_halfspaces.separated_alternatives(
        original, values, checks, minimum_gap_mm=1e-7
    )
    assert result.changed == (0,) and result.attempts == 1
    new = result.planes[0]
    assert new.gap(values) * old.model.scale >= 1e-7
    assert new.model is old.model and new.box is old.box
    assert new.members == old.members and new.reference == old.reference
    assert new.family != old.family or new.side != old.side
    assert result.planes is not original and original == [old]
    assert old.family == 1 and old.side is Side.BEFORE
    assert checks.call_count == 2


def test_touching_member_never_receives_an_invented_positive_gap() -> None:
    """
    A full member reaching the mating plane cannot pass the positive hardware margin by changing axes.
    """
    old = _plane(1.0, 0.2, 1.0)
    member = Region(0, True)
    old = replace(old, reference=member, members=(member,))
    result = hardware_halfspaces.separated_alternatives(
        [old], old.model.initial, lambda: None, minimum_gap_mm=1e-7
    )
    assert result.changed == () and result.attempts == 1 and result.planes[0] is old


def test_actual_occupied_member_cannot_change_away_its_intrusion() -> None:
    """
    A point inside both full material and the end proxy precludes a separating halfspace.
    """
    source = _route((Straight(5), fold(2, 1.2, pi, 0, 1), Straight(3)))
    model = SignedJoints(source)
    box = Hardware.create(source.targets, Dimensions(10, 10, 10)).boxes[1]
    point = Vector3(1, 0, 0)
    assert occupied_coordinates(source.pieces[0], point, 1, 1) is not None
    offset = difference(point, box.pose.origin)
    assert all(
        bound.low < dot(offset, axis) < bound.high for axis, bound in zip(box.axes, box.bounds)
    )
    member = Region(0, True)
    old = FeaturePlane(model, member, (member,), box, 1, Side.BEFORE)
    result = hardware_halfspaces.separated_alternatives(
        [old], model.initial, lambda: None, minimum_gap_mm=1e-7
    )
    assert result.changed == () and result.attempts == 1 and result.planes[0] is old


def test_satisfied_members_keep_identity_order_and_do_not_trigger_reselection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Existing useful guidance is retained without another fifteen-axis preparation.
    """
    old = replace(_plane(1.0, -0.2, -1.0), family=0, side=Side.AFTER)
    assert old.gap(old.model.initial) * old.model.scale > 1e-7
    selection = Mock(side_effect=AssertionError("Existing gap already meets the goal"))
    monkeypatch.setitem(vars(hardware_halfspaces), "member_planes", selection)
    result = hardware_halfspaces.separated_alternatives(
        [old, old], old.model.initial, lambda: None, minimum_gap_mm=1e-7
    )
    assert result.planes == [old, old] and all(p is old for p in result.planes)
    assert result.changed == () and result.attempts == 0
    selection.assert_not_called()


@pytest.mark.parametrize("stop_at", (1, 2))
def test_caller_cancellation_never_returns_partial_rebinding(stop_at: int) -> None:
    """
    A caller failure before or after axis preparation propagates without a retained result.
    """
    old = _plane(1.0, 0.3, 1.0)
    checks = 0

    def cancel() -> None:
        """
        Stop at a selected checkpoint without replacing the caller's error.
        """
        nonlocal checks
        checks += 1
        if checks == stop_at:
            raise RuntimeError("caller cancelled")

    with pytest.raises(RuntimeError, match="caller cancelled"):
        hardware_halfspaces.separated_alternatives(
            [old], old.model.initial, cancel, minimum_gap_mm=1e-7
        )


@pytest.mark.parametrize("minimum", (0.0, -1.0, float("inf"), float("nan")))
def test_invalid_gap_cannot_loosen_the_existing_positive_goal(minimum: float) -> None:
    """
    Invalid caller dimensions fail before evaluating geometry or selecting another side.
    """
    with pytest.raises(ValueError, match="positive hardware gap"):
        hardware_halfspaces.separated_alternatives([], (), lambda: None, minimum_gap_mm=minimum)


def test_grouped_material_is_never_silently_reduced_to_one_reference() -> None:
    """
    The refresh contract accepts only the independent-member representation its caller already uses.
    """
    old = _plane(1.0, 0.0, 1.0)
    old = replace(old, members=(old.reference, Region(0, True)))
    with pytest.raises(ValueError, match="independent complete-member"):
        hardware_halfspaces.separated_alternatives(
            [old], old.model.initial, lambda: None, minimum_gap_mm=1e-7
        )
