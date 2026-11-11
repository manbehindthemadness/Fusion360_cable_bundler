"""
Keep predicted positive straight material native-valid before it can reopen completed caps.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.active_projection import CoordinateBounds
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.native_slots import NativeSlots, bind_proposal
from experiments.experiment_ribbon_terminal_hardware.redistributed_projection import GuidancePolicy
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_material_return import _witness
from tests.test_ribbon_native_slots import _Bounds


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("before_mm", (2e-5, 5e-6))
def test_positive_target_selects_native_floor_even_for_negative_or_zero_increment(
    scale: float, before_mm: float
) -> None:
    """
    Sign the face from retained material, preserving original box limits and untouched coordinates.
    """
    values = (before_mm / scale, 1.0, 0.0)
    delta = ((5e-6 - before_mm) / scale, 0.0, 0.0)
    source = _Bounds(((0, 100), (-10, 10), (0, 100)))
    domain = bind_proposal(source, values, frozenset({0, 2}), delta, 1e-5, scale)
    assert domain is not None and domain.positive == frozenset({0})
    assert domain.frozen == frozenset({2}) and domain.minimum * scale > 1e-5
    assert domain.bounds(0) == (domain.minimum, source.bounds(0)[1])
    assert domain.bounds(1) == source.bounds(1) and domain.bounds(2)[1] == 0


def test_zero_target_and_original_upper_limit_retain_their_native_domain_meaning() -> None:
    """
    Removing a slot still selects zero, while an unrepresentable positive floor declines.
    """
    zero = bind_proposal(_Bounds(), (2e-5,), frozenset({0}), (-2e-5,), 1e-5, 1)
    assert zero is not None and not zero.positive and zero.frozen == frozenset({0})
    assert bind_proposal(_Bounds(((0, 9e-6),)), (5e-6,), frozenset({0}), (0,), 1e-5, 1) is None
    with pytest.raises(ValueError, match="complete finite"):
        bind_proposal(_Bounds(), (1.0,), frozenset({0}), (), 1e-5, 1)


def test_positive_existing_slot_uses_one_replacement_projection_before_motion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Use real derivative/model preparation; inspect a contracting slot's floor, then decline without proof.
    """
    source = _route((Straight(2e-5), fold(2, 1.2, 1, 0, 1), Straight(2), fold(2, 1.2, -1, 0, 1)))
    terminal = _gate(source)
    calls: list[CoordinateBounds] = []

    def project(
        model: CoordinateBounds,
        values: tuple[float, ...],
        rows: list[list[float]],
        _terms: tuple[float, ...],
        _check: Callable[[], None],
        **_kwargs: Any,
    ) -> tuple[float, ...] | None:
        """
        Supply a sub-native positive target, inspect the existing second pass, and forbid geometry.
        """
        calls.append(model)
        assert _kwargs["guidance_policy"] is GuidancePolicy.RESTORATION_MERIT
        if len(calls) == 1:
            assert isinstance(model, SignedJoints) and values[0] > 0
            return tuple(-1.5e-5 / model.scale if i == 0 else 0 for i in range(len(values)))
        assert len(calls) == 2 and isinstance(model, NativeSlots)
        assert 0 in model.positive and 0 not in model.frozen
        first = calls[0]
        assert isinstance(first, SignedJoints) and model.minimum * first.scale > 1e-5
        assert any(row[0] != 0 for row in rows[:6])
        return None

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        _witness(0, 2, 0.5, 0.5),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=MaterialGuidance(0),
    )
    assert result is not None and result.contact is None and result.route is source
    assert len(calls) == 2 and result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
    assert result.detail["stop_reason"] == "native_projection_infeasible"
    assert result.detail["native_positive_slot_projections"] == 1
    event = next(e for e in events if e["status"] == "native_positive_slot_projection")
    assert event["original_steps_mm"]["0"] < 0
    assert event["original_lengths_mm"]["0"] > event["proposed_lengths_mm"]["0"] > 0
    terminal.certify.assert_not_called()
