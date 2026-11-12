"""
Verify fixed-slot joint mating restoration and original final-proof accounting without saved layouts.
"""

from __future__ import annotations

import math
from dataclasses import replace
from functools import partial
from typing import Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.mating import ordered_mating_caps
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_fold_route.straight_closure import correction
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from experiments.experiment_ribbon_terminal_hardware.joint_mating import restore
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_stalled_certification import _Control
from tests.test_ribbon_stalled_certification import control as control


@pytest.mark.parametrize("scale", (0.5, 1.0, 20.0, 1000.0))
@pytest.mark.parametrize("absent_start", (False, True))
def test_actual_joint_caps_close_with_fixed_folds_and_exact_absent_slots(
    scale: float, absent_start: bool
) -> None:
    """
    Independently authored spatial chains restore a measured defect without any bend change.
    """
    bends = (fold(2 * scale, 1.2, 1.1, 0.3, scale), fold(2 * scale, 1.2, -0.8, -0.4, scale))
    geometries = (bends[0], Straight(3 * scale), bends[1], Straight(4 * scale))
    source = _route(geometries if absent_start else (Straight(2 * scale), *geometries))
    model = SignedJoints(source)
    values = list(model.initial)
    values[model.straight_indices[-1]] += 5e-8 / model.scale
    coordinates = tuple(values)
    route = model.route(coordinates)
    assert route is not None and 1e-10 < cap_error(route) < 1e-7
    result = restore(
        route,
        model,
        coordinates,
        (0.0,) * 6,
        lambda: None,
        minimum_straight_mm=1e-5,
        length_ceiling_mm=None,
        fixed=frozenset(),
    )
    assert result is not None
    restored = result
    placed = model.route(restored)
    assert placed is not None and placed.targets is route.targets
    assert ordered_mating_caps(placed.pieces, route.targets)
    assert all(
        a == b
        for i, (a, b) in enumerate(zip(coordinates, restored))
        if i not in model.straight_indices
    )
    assert (restored[model.straight_indices[0]] == 0) is absent_start
    assert model.preserves(placed)


@pytest.mark.parametrize("failure", ("fixed", "native", "length", "nonfinite", "frame"))
def test_joint_polish_cannot_bypass_original_domains_or_guess_a_new_face(failure: str) -> None:
    """
    A real positive slot cannot cross its native floor, pin or inherited quality ceiling.
    """
    source = _route((Straight(10),))
    if failure == "frame":
        source = replace(source, targets=replace(source.targets, end_width=Vector3(0, 0, 1)))
    model = SignedJoints(source)
    values = (model.initial[0] + 5e-8 / model.scale,)
    route = model.route(values)
    assert route is not None
    result = restore(
        route,
        model,
        values,
        (math.nan,) * 6 if failure == "nonfinite" else (0.0,) * 6,
        lambda: None,
        minimum_straight_mm=10 if failure == "native" else 1e-5,
        length_ceiling_mm=9 if failure == "length" else None,
        fixed=frozenset({0}) if failure == "fixed" else frozenset(),
    )
    assert result is None


def test_joint_polish_requires_exact_source_coordinates_and_keeps_guard_errors() -> None:
    """
    A different route cannot inherit coordinate identity; original cancellation is never a decline.
    """
    source = _route((Straight(10),))
    model = SignedJoints(source)
    values = (model.initial[0] + 5e-8 / model.scale,)
    with pytest.raises(ValueError, match="exact current"):
        restore(
            source,
            model,
            values,
            (0.0,) * 6,
            lambda: None,
            minimum_straight_mm=1e-5,
            length_ceiling_mm=None,
            fixed=frozenset(),
        )
    with pytest.raises(InterruptedError, match="original guard"):
        restore(
            source,
            model,
            values,
            (0.0,) * 6,
            Mock(side_effect=InterruptedError("original guard")),
            minimum_straight_mm=1e-5,
            length_ceiling_mm=None,
            fixed=frozenset(),
        )


def test_shared_kernel_rejects_guessed_slot_identity_and_preserves_pins() -> None:
    """
    Exact measured material lengths determine the mapping; even a small mismatch is not retargeted.
    """
    source = _route((Straight(10),))
    with pytest.raises(ValueError, match="actual ordered"):
        correction(source.pieces, source.targets, (10 + 5e-8,), lambda: None)
    targets = replace(source.targets, end=source.targets.end.translated(Vector3(1, 0, 0), 5e-8))
    assert (
        correction(source.pieces, targets, (10.0,), lambda: None, fixed_slots=frozenset({0}))
        is None
    )


def test_omitted_subrepresentation_slot_is_not_guessed_as_occupied_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A positive coordinate below placement resolution declines before strict actual-slot binding.
    """
    source = _route((fold(2, 1.2, 0.8, 0.2, 1), Straight(3)))
    model = SignedJoints(source)
    values = list(model.initial)
    values[0] = 1e-14 / model.scale
    values[model.straight_indices[-1]] += 5e-9 / model.scale
    coordinates = tuple(values)
    route = model.route(coordinates)
    assert route is not None
    projection = Mock(side_effect=AssertionError("must not guess actual slot identity"))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_mating.correction", projection
    )
    assert (
        restore(
            route,
            model,
            coordinates,
            (0.0,) * 6,
            lambda: None,
            minimum_straight_mm=1e-5,
            length_ceiling_mm=None,
            fixed=frozenset(),
        )
        is None
    )
    projection.assert_not_called()


def _rounding_motion(control: _Control, *, native_decline: bool) -> Mock:
    """
    Add one authored positional defect to the protocol's real accepted hairpin translation.
    """
    model = StraightSlots(control.source)
    first = (0.1 / model.scale + 5e-9 / model.scale, 0.1 / model.scale)
    second = (
        (-model.initial[0] - first[0] + 0.5e-5 / model.scale, 0.0) if native_decline else (0.0, 0.0)
    )
    control.projector.side_effect = [first, second]
    return Mock(return_value=None)


@pytest.mark.parametrize("native_decline", (False, True))
def test_stall_polish_debits_one_original_step_before_one_actual_final_request(
    control: _Control, monkeypatch: pytest.MonkeyPatch, native_decline: bool
) -> None:
    """
    Real cap correction precedes the final request; no new projection, motion or constraint follows it.
    """
    native = _rounding_motion(control, native_decline=native_decline)
    monkeypatch.setitem(vars(joint_contact), "bind_native_slots", native)
    result = control.run()
    assert result is not None and result.contact is not None
    assert result.detail["newton_steps"] == 2 and result.detail["iterations"] == 1
    assert result.detail["mating_restoration_attempts"] == result.detail["mating_restorations"] == 1
    assert result.detail["stalled_certificate_requests"] == 1
    assert native.call_count == int(native_decline)
    assert control.projector.call_count == 2
    assert control.advance.call_count == (1 if native_decline else 5)
    control.terminal.certify.assert_called_once()
    route = control.terminal.certify.call_args.args[0]
    assert ordered_mating_caps(route.pieces, route.targets)
    assert route is control.checker.call_args.args[0]
    request = next(e for e in control.events if e["status"] == "stalled_certificate_requested")
    assert request["original_stop"] == (
        "native_projection_infeasible" if native_decline else "joint_no_descent"
    )
    index = control.events.index(request)
    assert not any(
        e["status"] in ("update", "mating_restoration", "constraint_added")
        for e in control.events[index + 1 :]
    )


@pytest.mark.parametrize("boundary", ("restore", "record"))
def test_late_restoration_is_charged_without_request_or_counter_renewal(
    control: _Control, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """
    Exhaustion during geometry or reporting retains the spent correction and prevents physical proof.
    """
    _rounding_motion(control, native_decline=False)
    if boundary == "restore":

        def late(*_args: object, **_kwargs: object) -> None:
            """
            Model time spent before any restored result is available.
            """
            control.clock[0] = 0.36

        monkeypatch.setitem(vars(joint_contact), "restore_mating", late)
    else:

        def record(event: dict[str, object]) -> None:
            """
            Model reporting time after retaining the original correction receipt.
            """
            control.events.append(event)
            if event["status"] == "mating_restoration":
                control.clock[0] = 0.36

        control.recorder.side_effect = record
    result = control.run()
    assert result is not None and result.detail["stop_reason"] == "phase_budget"
    assert result.detail["newton_steps"] == 2 and result.detail["mating_restoration_attempts"] == 1
    control.terminal.certify.assert_not_called()
    control.checker.assert_not_called()


@pytest.mark.parametrize("remaining_newton", (1, 2))
def test_ordinary_certificate_preparation_uses_only_remaining_original_correction(
    control: _Control, monkeypatch: pytest.MonkeyPatch, remaining_newton: int
) -> None:
    """
    Completion may polish once before proof, while an exhausted allocation keeps its original decision.
    """
    _rounding_motion(control, native_decline=False)
    model = StraightSlots(control.source)

    def completed(_self: JointEvaluation, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Isolate completed guidance after one real translated shape, independently of cap accuracy.
        """
        return (0.0,) * 6 + (1e-4 if values[0] < model.initial[0] + 0.05 / model.scale else -1e-6,)

    monkeypatch.setattr(JointEvaluation, "equations", completed)
    monkeypatch.setitem(
        vars(joint_contact),
        "recover",
        partial(joint_contact.recover, maximum_newton_steps=remaining_newton),
    )
    result = control.run()
    assert result is not None and result.contact is not None
    assert result.detail["newton_steps"] == remaining_newton
    assert result.detail["mating_restoration_attempts"] == remaining_newton - 1
    assert result.detail["mating_restorations"] == remaining_newton - 1
    assert result.detail["stalled_certificate_requests"] == 0
    assert control.projector.call_count == control.advance.call_count == 1
    control.terminal.certify.assert_called_once()
    route = control.terminal.certify.call_args.args[0]
    assert ordered_mating_caps(route.pieces, route.targets) is (remaining_newton == 2)


@pytest.mark.parametrize(
    "hardware,contact",
    (
        ("blocked", "separated"),
        ("unresolved", "separated"),
        ("clear", "penetration"),
        ("clear", "unresolved"),
    ),
)
def test_native_projection_decline_cannot_bypass_actual_nonpassing_physical_proof(
    control: _Control,
    monkeypatch: pytest.MonkeyPatch,
    hardware: Literal["clear", "blocked", "unresolved"],
    contact: str,
) -> None:
    """
    A rejected native linear direction grants one final measurement, never a physical pass or more repair.
    """
    native = _rounding_motion(control, native_decline=True)
    monkeypatch.setitem(vars(joint_contact), "bind_native_slots", native)
    control.terminal.certify.return_value = Report(hardware, 2)
    control.checker.return_value = ContactResult(contact, 7)
    result = control.run()
    assert result is not None and result.contact is None
    assert result.detail["stalled_certificate_requests"] == 1
    assert result.detail["newton_steps"] == 2
    control.terminal.certify.assert_called_once()
    assert control.checker.call_count == int(hardware == "clear")
    assert control.projector.call_count == 2 and control.advance.call_count == 1
    assert not any(
        e["status"]
        in ("constraint_added", "hardware_constraint_added", "straight_contact_retained")
        for e in control.events
    )


def test_unsuccessful_polish_keeps_original_pose_for_one_final_measurement(
    control: _Control,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Failed optional closure consumes its correction but neither fabricates geometry nor renews itself.
    """
    _rounding_motion(control, native_decline=False)
    polish = Mock(return_value=None)
    monkeypatch.setitem(vars(joint_contact), "restore_mating", polish)
    result = control.run()
    assert result is not None and result.contact is not None
    assert result.detail["newton_steps"] == 2 and result.detail["mating_restoration_attempts"] == 1
    assert result.detail["mating_restorations"] == 0 and polish.call_count == 1
    original_candidate = polish.call_args.args[0]
    assert control.terminal.certify.call_args.args[0] is original_candidate
    assert not ordered_mating_caps(original_candidate.pieces, original_candidate.targets)
