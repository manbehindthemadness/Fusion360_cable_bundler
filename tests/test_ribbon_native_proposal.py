"""
Keep predicted positive straight material native-valid before it can reopen completed caps.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.active_projection import CoordinateBounds
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    MaterialGuidance,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.native_slots import NativeSlots, bind_proposal
from experiments.experiment_ribbon_terminal_hardware.redistributed_projection import GuidancePolicy
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_hardware_motion import _adaptive_case
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
        assert _kwargs["linear_policy"] is joint_contact.LinearPolicy.DUAL
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


def test_expanded_hardware_native_replacement_retains_selected_linear_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The existing native-floor replacement must not silently revert an expanded action's optimizer.
    """
    source, terminal, evidence, mode = _adaptive_case()
    calls: list[CoordinateBounds] = []

    def no_straight(*_args: Any, **_kwargs: Any) -> None:
        """
        Decline the original straight-domain proposal before any geometry motion.
        """
        return None

    def project(
        model: CoordinateBounds, values: tuple[float, ...], *_args: Any, **kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Observe the selected policy before and after the real positive native-floor binding.
        """
        calls.append(model)
        assert kwargs["linear_policy"] is joint_contact.LinearPolicy.COUPLED_RESTORATION
        if len(calls) == 1:
            assert isinstance(model, SignedJoints) and values[0] > 0
            return tuple(
                (5e-6 / model.scale - values[0]) if i == 0 else 0.0 for i in range(len(values))
            )
        assert len(calls) == 2 and isinstance(model, NativeSlots)
        initial = calls[0]
        assert isinstance(initial, SignedJoints)
        assert 0 in model.positive and model.minimum * initial.scale > 1e-5
        return None

    monkeypatch.setitem(vars(joint_contact), "shortest_run_step", no_straight)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    result = joint_contact.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        lambda _event: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=mode,
    )
    assert result is not None and result.route is source and result.contact is None
    assert len(calls) == 2 and result.detail["hardware_domain_expanded"]
    assert result.detail["native_positive_slot_projections"] == 1
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0


@pytest.mark.parametrize("slot_change", (0.0, 1e-20, -1e-20))
@pytest.mark.parametrize("coupled", (False, True))
@pytest.mark.parametrize("descent", (False, True))
def test_only_unchanged_absent_faces_reuse_the_original_angular_step(
    monkeypatch: pytest.MonkeyPatch, slot_change: float, coupled: bool, descent: bool
) -> None:
    """
    A declined replacement retains only exact absent faces and a separately rechecked linear gate.
    """
    source = _route((fold(2, 1.2, 1, 0, 1), Straight(2), fold(2, 1.2, -1, 0, 1)))
    source = replace(
        source,
        targets=replace(source.targets, end=source.targets.end.translated(Vector3(1, 0, 0), 0.1)),
    )
    terminal = _gate(source)
    calls = 0
    events: list[dict[str, Any]] = []

    class TrialReached(RuntimeError):
        """
        Stop at the first ordinary nonlinear trial without granting acceptance.
        """

    def project(
        model: CoordinateBounds, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Supply an angular step and observe whether its exact absent-slot domain changes.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            return None
        assert isinstance(model, SignedJoints) and values[0] == 0.0
        return tuple(slot_change if i == 0 else 0.01 if i == 1 else 0.0 for i in range(len(values)))

    def no_trial(*_args: Any, **_kwargs: Any) -> None:
        """
        Verify the already-native step reaches the original nonlinear gate exactly once.
        """
        raise TrialReached()

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    monkeypatch.setitem(vars(joint_contact), "zero_step", lambda *_args: None)
    monkeypatch.setitem(vars(joint_contact), "advance", no_trial)
    gate = Mock(return_value=descent)
    monkeypatch.setitem(vars(joint_contact), "strict_descent", gate)
    arguments: dict[str, Any] = {
        "maximum_length_mm": source.material_length_mm,
        "minimum_straight_mm": 1e-5,
        "remaining_pairs": 123,
        "maximum_cpu_seconds": 0.35,
        "maximum_seconds": 2,
        "maximum_updates": 4,
        "mode": ContactGuidance() if coupled else MaterialGuidance(0),
    }
    crossing = _witness(0, 2, 0.5, 0.5)
    evidence = ContactResult("penetration", 1, crossing) if coupled else crossing
    if slot_change == 0.0 and descent:
        with pytest.raises(TrialReached):
            joint_contact.recover(
                source, evidence, terminal, lambda: None, events.append, **arguments
            )
        assert calls == 2
        reused = next(event for event in events if event["status"] == "native_zero_faces_reused")
        assert 0 in reused["slots"]
    else:
        result = joint_contact.recover(
            source, evidence, terminal, lambda: None, events.append, **arguments
        )
        assert result is not None and result.detail["stop_reason"] == "native_projection_infeasible"
        assert calls == 2 and result.detail["native_zero_face_reuses"] == 0
    assert gate.call_count == int(slot_change == 0.0)
    terminal.certify.assert_not_called()


def test_successful_native_replacement_keeps_its_original_preference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An already-native first proposal cannot displace a successfully optimized replacement.
    """
    source = _route((fold(2, 1.2, 1, 0, 1), Straight(2), fold(2, 1.2, -1, 0, 1)))
    calls = 0
    retained_gate = Mock(side_effect=AssertionError("Replacement succeeded"))

    class TrialReached(RuntimeError):
        """
        Stop after observing the ordinary replacement vector at the nonlinear boundary.
        """

    def project(
        _model: CoordinateBounds, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...]:
        """
        Give the first and replacement action distinct native-valid angular vectors.
        """
        nonlocal calls
        calls += 1
        assert calls <= 2
        return tuple(0.01 * calls if i == 1 else 0.0 for i in range(len(values)))

    def observe(
        _model: SignedJoints,
        _values: tuple[float, ...],
        delta: tuple[float, ...],
        _fraction: float,
    ) -> None:
        """
        Require the existing second action's vector rather than a changed preference.
        """
        assert delta[1] == 0.02
        raise TrialReached()

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    monkeypatch.setitem(vars(joint_contact), "advance", observe)
    monkeypatch.setitem(vars(joint_contact), "strict_descent", retained_gate)
    with pytest.raises(TrialReached):
        joint_contact.recover(
            source,
            _witness(0, 2, 0.5, 0.5),
            _gate(source),
            lambda: None,
            lambda _event: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=123,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
            maximum_updates=4,
            mode=MaterialGuidance(0),
        )
    assert calls == 2
    retained_gate.assert_not_called()
