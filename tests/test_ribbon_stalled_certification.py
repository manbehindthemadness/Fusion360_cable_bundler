"""
Verify one strict final-proof request after accepted motion stalls, without saved-layout replay.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Callable, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_completion, joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.flat_continuation import (
    ClosedFlatContinuation,
    ContactContinuation,
)
from experiments.experiment_ribbon_terminal_hardware.joint_evaluation import JointEvaluation
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate, _source
from tests.test_ribbon_material_return import _witness


@pytest.mark.parametrize("guidance", (-1.0, 1e-5, 100.0))
@pytest.mark.parametrize("scale", (0.5, 1.0, 20.0))
def test_readiness_keeps_actual_closed_material_separate_from_guidance(
    guidance: float, scale: float
) -> None:
    """
    Independently authored closed material may request proof, never inherit clearance from readiness.
    """
    source = _route((Straight(2 * scale), fold(2 * scale, 1.2, 0.8, 0.2, scale)))
    model = SignedJoints(source)
    residual = (0.0,) * 6 + (guidance,)
    assert joint_completion.stalled_certificate_ready(
        source, model, residual, length_ceiling_mm=None, minimum_straight_mm=1e-5
    )
    assert not joint_completion.stalled_certificate_ready(
        source,
        model,
        residual,
        length_ceiling_mm=source.material_length_mm - 0.1,
        minimum_straight_mm=1e-5,
    )
    shifted = replace(
        source,
        targets=replace(source.targets, end=source.targets.end.translated(Vector3(0, 0, 1), 1e-3)),
    )
    assert not joint_completion.stalled_certificate_ready(
        shifted, SignedJoints(shifted), residual, length_ceiling_mm=None, minimum_straight_mm=1e-5
    )


@pytest.mark.parametrize(
    "change", ("targets", "radius", "sign", "native", "residual", "metric", "caps")
)
def test_readiness_rejects_changed_contracts_and_nonfinite_measurements(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """
    Two legal half turns isolate radius/sign preservation from endpoint closure.
    """
    source = _route(
        (Straight(2), fold(2, 1.2, math.pi, 0, 0), fold(2, 1.2, math.pi, 0, 0), Straight(3))
    )
    model = SignedJoints(source)
    candidate = source
    terms = (0.0,) * 6 + (1.0,)
    if change == "targets":
        candidate = replace(source, targets=replace(source.targets, name="different identity"))
    elif change in ("radius", "sign"):
        geometry = fold(
            3 if change == "radius" else 2, 1.2, -math.pi if change == "sign" else math.pi, 0, 0
        )
        other = _route((Straight(2), geometry, geometry, Straight(3)))
        candidate = replace(other, targets=source.targets)
        assert cap_error(candidate) < 1e-7
    elif change == "native":
        candidate = _route((Straight(1e-6), fold(2, 1.2, 0.8, 0.2, 1)))
        model = SignedJoints(candidate)
    elif change == "residual":
        terms = (0.0,) * 6 + (math.nan,)
    else:
        monkeypatch.setattr(
            joint_completion,
            "material_error" if change == "metric" else "cap_error",
            lambda _: math.nan,
        )
    assert not joint_completion.stalled_certificate_ready(
        candidate, model, terms, length_ceiling_mm=None, minimum_straight_mm=1e-5
    )


@dataclass
class _Control:
    """
    Keep real authored placement with explicit optimizer and certificate-boundary doubles.
    """

    source: FoldRoute
    evidence: Report
    terminal: Mock
    clock: list[float]
    events: list[dict[str, Any]]
    projector: Mock
    checker: Mock
    recorder: Mock
    checkpoint: Mock
    advance: Mock

    def run(
        self,
        *,
        remaining_pairs: int = 123,
        on_blocked: Callable[[JointHandoff], None] | None = None,
    ) -> Result | None:
        """
        Use the original finite correction allocation and a quality goal with useful growth slack.
        """
        return joint_contact.recover(
            self.source,
            self.evidence,
            self.terminal,
            self.checkpoint,
            self.recorder,
            maximum_length_mm=self.source.material_length_mm + 0.25,
            minimum_straight_mm=1e-5,
            remaining_pairs=remaining_pairs,
            maximum_cpu_seconds=0.35,
            maximum_seconds=2,
            maximum_updates=2,
            mode=ContactGuidance(
                (FeatureEvidence(self.source, self.evidence),),
                ContactMotion.ADAPTIVE_HARDWARE,
                ContactContinuation.FIRST_FLAT,
            ),
            on_blocked=on_blocked,
        )


@pytest.fixture
def control(monkeypatch: pytest.MonkeyPatch) -> _Control:
    """
    Accept one real closed affine translation, then stall synthetic guidance without another shape.

    Progress/projector and physical results are explicit protocol doubles, not
    geometry coverage. Real model placement, cap/native contracts, derivative
    binding, line-search ordering and allowance accounting remain in use.
    """
    source = _source(0.0)
    model = StraightSlots(source)
    terminal = _gate(source)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    evidence = inspect(source, terminal.hardware)
    assert evidence.status == "blocked" and evidence.witness is not None
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])
    delta = (0.1 / model.scale,) * len(model.initial)
    moved = model.route(tuple(a + b for a, b in zip(model.initial, delta)))
    assert moved is not None and cap_error(moved) < 1e-7

    def equations(_self: JointEvaluation, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Model a completed translation and stationary guidance independently of actual cap measurement.
        """
        return (0.0,) * 6 + (model.initial[0] + 0.1 / model.scale - values[0], 1e-6)

    monkeypatch.setattr(JointEvaluation, "equations", equations)
    projector = Mock(side_effect=[delta, (0.0,) * len(delta)])
    monkeypatch.setitem(vars(joint_contact), "shortest_run_step", projector)
    checker = Mock(return_value=ContactResult("separated", 7))
    monkeypatch.setitem(vars(joint_contact), "inspect_contact", checker)
    # This fixture isolates stalled certification; discovery has its own protocol controls.
    monkeypatch.setitem(
        vars(joint_contact), "screen_restoration", Mock(return_value=ContactResult("unresolved", 0))
    )
    advance = Mock(wraps=joint_contact.advance)
    monkeypatch.setitem(vars(joint_contact), "advance", advance)
    events: list[dict[str, Any]] = []
    return _Control(
        source,
        evidence,
        terminal,
        clock,
        events,
        projector,
        checker,
        Mock(side_effect=events.append),
        Mock(),
        advance,
    )


@pytest.mark.parametrize("remaining,accepted", ((1024, False), (1523, True), (2048, True)))
def test_final_certificate_uses_only_the_unspent_shared_pool_without_retry(
    control: _Control,
    monkeypatch: pytest.MonkeyPatch,
    remaining: int,
    accepted: bool,
) -> None:
    """
    Preserve prior negative work while allowing a larger complete proof inside the original pool.

    This is a certificate protocol double requiring1500comparisons, not physical
    geometry coverage. The old1024suballocation strands otherwise available work.
    """
    spent = 23
    monkeypatch.setitem(
        vars(joint_contact),
        "screen_restoration",
        Mock(return_value=ContactResult("unresolved", spent)),
    )

    def certificate(*_args: Any, maximum_pairs: int, **_kwargs: Any) -> ContactResult:
        """
        Complete only when the owner grants enough genuinely unused comparisons.
        """
        return ContactResult(
            "separated" if maximum_pairs >= 1500 else "unresolved",
            min(1500, maximum_pairs),
            limit=None if maximum_pairs >= 1500 else "pairs",
        )

    control.checker.side_effect = certificate
    result = control.run(remaining_pairs=remaining)
    assert result is not None and result.detail["status"] == (
        "separated" if accepted else "unresolved"
    )
    assert control.checker.call_count == 1
    assert control.checker.call_args.kwargs["maximum_pairs"] == remaining - spent
    assert result.detail["restoration_screen_pairs"] == spent
    assert result.detail["contact_pairs"] == spent + min(1500, remaining - spent) <= remaining
    assert result.detail["contacts"] == 1 and result.detail["newton_steps"] == 1
    assert control.projector.call_count == 2


def test_interrupted_final_certificate_charges_only_the_remaining_pool_as_an_upper_bound(
    control: _Control,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve earlier measured work and conservatively debit pending work without another request.
    """
    monkeypatch.setitem(
        vars(joint_contact),
        "screen_restoration",
        Mock(return_value=ContactResult("unresolved", 23)),
    )
    control.checker.side_effect = vars(joint_contact)["_Exhausted"]()
    result = control.run(remaining_pairs=2048)
    assert result is not None and result.detail["stop_reason"] == "phase_budget"
    control.checker.assert_called_once()
    assert control.checker.call_args.kwargs["maximum_pairs"] == 2025
    assert result.detail["contact_pairs"] == 2048
    assert result.detail["restoration_screen_pairs"] == 23
    assert result.detail["newton_steps"] == 1


@pytest.mark.parametrize(
    "hardware,contact",
    (
        ("clear", "separated"),
        ("blocked", "separated"),
        ("unresolved", "separated"),
        ("clear", "penetration"),
        ("clear", "unresolved"),
    ),
)
def test_stalled_request_uses_both_original_certificates_once_without_more_motion(
    control: _Control, hardware: Literal["clear", "blocked", "unresolved"], contact: str
) -> None:
    """
    Actual certification alone may accept; nonpassing reports cannot add another constraint or trial.
    """
    control.terminal.certify.return_value = Report(hardware, 2)
    measured = ContactResult(contact, 7)
    control.checker.return_value = measured
    result = control.run()
    assert result is not None
    assert result.detail["stalled_certificate_requests"] == 1
    assert sum(e["status"] == "stalled_certificate_requested" for e in control.events) == 1
    assert control.projector.call_count == 2 and control.advance.call_count == 5
    assert result.detail["newton_steps"] == 1 and result.detail["iterations"] == 1
    control.terminal.certify.assert_called_once()
    assert control.checker.call_count == int(hardware == "clear")
    assert result.detail["contact_pairs"] == (7 if hardware == "clear" else 0)
    if hardware == "clear":
        assert control.terminal.certify.call_args.args[0] is control.checker.call_args.args[0]
        assert control.checker.call_args.kwargs["maximum_pairs"] == 123
    assert (result.contact is measured) is (hardware == "clear" and contact == "separated")
    assert not any(
        e["status"]
        in ("constraint_added", "hardware_constraint_added", "straight_contact_retained")
        for e in control.events
    )


@pytest.mark.parametrize("pose", ("unchanged", "open"))
def test_no_accepted_motion_or_open_caps_cannot_request_proof(control: _Control, pose: str) -> None:
    """
    Synthetic progress cannot turn the initial blocker or an open translated cap into readiness.
    """
    size = len(StraightSlots(control.source).initial)
    control.projector.side_effect = (
        [(0.0,) * size] if pose == "unchanged" else [(0.01, 0.0), (0.0,) * size]
    )
    result = control.run()
    assert result is not None and result.contact is None
    assert result.detail["stalled_certificate_requests"] == 0
    control.terminal.certify.assert_not_called()
    control.checker.assert_not_called()


@pytest.mark.parametrize("boundary", ("request", "hardware", "contact"))
def test_late_work_cannot_gain_a_certificate_or_renew_the_phase(
    control: _Control, boundary: str
) -> None:
    """
    Charge request logging and each physical result before any acceptance or further work.
    """

    def record(event: dict[str, Any]) -> None:
        """
        Simulate time spent in the actual request callback after retaining its receipt.
        """
        control.events.append(event)
        if boundary == "request" and event["status"] == "stalled_certificate_requested":
            control.clock[0] = 0.36

    def hardware(*_args: Any) -> Report:
        """
        Return a late actual-boundary disposition without granting more phase time.
        """
        if boundary == "hardware":
            control.clock[0] = 0.36
        return Report("clear", 2)

    def contact(*_args: Any, **_kwargs: Any) -> ContactResult:
        """
        Retain the check's spent comparisons even when its separated result arrives too late.
        """
        if boundary == "contact":
            control.clock[0] = 0.36
        return ContactResult("separated", 7)

    control.recorder.side_effect = record
    control.terminal.certify.side_effect = hardware
    control.checker.side_effect = contact
    result = control.run()
    assert (
        result is not None
        and result.contact is None
        and result.detail["stop_reason"] == "phase_budget"
    )
    assert result.detail["newton_steps"] == 1 and control.advance.call_count == 5
    assert control.terminal.certify.call_count == int(boundary != "request")
    assert control.checker.call_count == int(boundary == "contact")
    assert result.detail["contact_pairs"] == (7 if boundary == "contact" else 0)


def test_original_caller_failure_after_request_propagates(control: _Control) -> None:
    """
    Caller source/cancellation errors remain authoritative after a requested final check.
    """

    def record(event: dict[str, Any]) -> None:
        """
        Invalidate the original source guard before the next work boundary.
        """
        control.events.append(event)
        if event["status"] == "stalled_certificate_requested":
            control.checkpoint.side_effect = InterruptedError("original source guard")

    control.recorder.side_effect = record
    with pytest.raises(InterruptedError, match="original source guard"):
        control.run()
    control.terminal.certify.assert_not_called()


def test_stalled_hardware_blocker_preserves_actual_current_pose_handoff(control: _Control) -> None:
    """
    An actual newly measured occupied point may yield the same immutable rejected pose, never acceptance.
    """
    control.terminal.certify.side_effect = lambda route, _: inspect(
        route, control.terminal.hardware
    )
    yielded: list[JointHandoff] = []
    result = control.run(on_blocked=yielded.append)
    assert result is not None and result.contact is None and len(yielded) == 1
    assert yielded[0].route is control.terminal.certify.call_args.args[0]
    assert yielded[0].evidence.status == "blocked" and yielded[0].evidence.witness is not None
    assert result.detail["stop_reason"] == "hardware_handoff"
    assert control.advance.call_count == 5
    control.checker.assert_not_called()


def test_stalled_material_report_cannot_restart_opted_in_flat_motion(
    monkeypatch: pytest.MonkeyPatch, control: _Control
) -> None:
    """
    A mocked strict checker boundary yields its current pose without another FIRST_FLAT attempt.
    """
    crossing = ContactResult("penetration", 7, _witness(0, 2))
    control.checker.return_value = crossing
    prepare = Mock(side_effect=AssertionError("No more constraint insertion after final stop"))
    monkeypatch.setattr(ClosedFlatContinuation, "prepare", prepare)
    yielded: list[JointHandoff] = []
    result = control.run(on_blocked=yielded.append)
    assert result is not None and result.contact is None and len(yielded) == 1
    assert yielded[0].route is control.checker.call_args.args[0] and yielded[0].evidence is crossing
    assert result.detail["stop_reason"] == "material_handoff" and control.advance.call_count == 5
    prepare.assert_not_called()


@pytest.mark.parametrize("interrupted", (False, True))
def test_final_contact_keeps_the_remaining_pair_pool_and_interrupted_upper_bound(
    control: _Control, interrupted: bool
) -> None:
    """
    A partial or interrupted final proof cannot obtain another pair allowance or become acceptance.
    """

    def contact(*_args: Any, **kwargs: Any) -> ContactResult:
        """
        Exercise the actual remaining comparison ceiling and original checkpoint.
        """
        assert kwargs["maximum_pairs"] == 3
        if interrupted:
            control.clock[0] = 0.36
            kwargs["checkpoint"]()
        return ContactResult("unresolved", 3, limit="pairs")

    control.checker.side_effect = contact
    result = control.run(remaining_pairs=3)
    assert result is not None and result.contact is None
    assert result.detail["contact_pairs"] == 3 and result.detail["contacts"] == 1
    assert result.detail["stop_reason"] == ("phase_budget" if interrupted else "contact_unresolved")
    assert control.advance.call_count == 5
    if interrupted:
        assert result.detail["interrupted_pairs_charged_as_upper_bound"] == 3
