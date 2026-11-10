"""
Verify bounded automatic handoffs on analytical material routes, without saved-layout geometry replay.
"""

from __future__ import annotations

from dataclasses import replace
from math import ceil
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_feature_insertion.contact_recovery import BaselinePolicy
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import mating_feasibility
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence, joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
    MaterialGuidance,
    ReturnLength,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_contact import JointMode
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _depth, _source


@pytest.fixture
def source() -> FoldRoute:
    """
    Author an asymmetric three-fold route with fixed caps measured from its actual analytical pieces.
    """
    return _route(
        (
            Straight(3),
            fold(2, 1.2, 0.6, 0.2, 1),
            Straight(4),
            fold(3, 1.2, -1.4, -0.1, 1),
            Straight(3),
            fold(2, 1.2, 0.8, 0.2, 1),
            Straight(3),
        )
    )


def _gate(route: FoldRoute) -> Mock:
    """
    Retain real hardware dimensions and mock only the measured certificate boundary.
    """
    gate = Mock(spec=Gate)
    gate.hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    gate.measure.return_value = Report("clear", 1)
    gate.certify.return_value = Report("clear", 1)
    return gate


def _pending() -> ContactResult:
    """
    Provide a depth-limited measurement boundary without inventing a strict penetration witness.
    """
    return ContactResult(
        "unresolved",
        4,
        unresolved_pieces=(0, 4),
        limit="depth",
        unresolved_regions=(
            Cell(0, Span(0.2, 0.4), Span(-0.1, 0.1), Span(-0.1, 0.1)),
            Cell(4, Span(0.2, 0.4), Span(-0.1, 0.1), Span(-0.1, 0.1)),
        ),
    )


def _crossing(route: FoldRoute, first: int, last: int) -> ContactResult:
    """
    Supply a mocked strict-checker outcome for sequence control, not physical clearance evidence.
    """
    witness = Penetration(
        (first, last), (0.5, 0, 0), (0.5, 0, 0), route.pieces[first].surface(0.5, 0)[0]
    )
    return ContactResult("penetration", 5, witness)


def _result(
    route: FoldRoute,
    contact: ContactResult | None = None,
    *,
    newton: int = 1,
    pairs: int = 5,
    iterations: int | None = None,
) -> Result:
    """
    Keep stage accounting explicit at a mocked joint-solver boundary.
    """
    return Result(
        route,
        contact,
        {
            "iterations": ceil(newton / 6) if iterations is None else iterations,
            "newton_steps": newton,
            "contacts": 1,
            "contact_pairs": pairs,
            "contact_seconds": 0.001,
            "stop_reason": "accepted" if contact is not None else "handoff",
        },
    )


def _run(
    source: FoldRoute,
    gate: Mock,
    *,
    work: Work | None = None,
    record: Callable[[dict[str, Any]], None] | None = None,
) -> Result | None:
    """
    Invoke only the sequence boundary on the analytical route with finite original work.
    """
    return deviation_sequence.recover(
        source,
        _pending(),
        gate,
        lambda: None,
        record or (lambda e: None),
        work=work or Work(4, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )


def test_actual_blockers_drive_distinct_returns_then_adaptive_hardware_under_one_budget(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Carry closed immutable proposals, prior connector evidence and decreasing original allocations.
    """
    gate = _gate(source)
    changed = restore(snapshot(source))
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setattr(
            "experiments.experiment_ribbon_terminal_hardware.deviation_sequence." + name,
            lambda: clock[0],
        )
    captured: list[dict[str, Any]] = []

    def stage(
        route: FoldRoute,
        evidence: Any,
        terminal: Gate,
        _checkpoint: Any,
        _record: Any,
        **options: Any,
    ) -> Result:
        """
        Simulate independently tested joint stages; no numerical solver or geometry qualification is claimed.
        """
        assert terminal is gate
        number = len(captured)
        captured.append(options)
        clock[0] += 0.01
        if number == 0:
            assert isinstance(options["mode"], ContactGuidance)
            assert options["mode"].motion is ContactMotion.BEND_JOINTS
            blocker: ContactResult | Report = _crossing(changed, 0, 4)
        elif number in (1, 2):
            mode = options["mode"]
            assert (
                isinstance(mode, MaterialGuidance) and mode.length is ReturnLength.RESTORATION_GOAL
            )
            assert mode.selected_fold == number
            if number == 1:
                blocker = _crossing(changed, 4, 6)
            else:
                blocker = Report(
                    "blocked",
                    1,
                    Witness(
                        "end", 5, (0.5, 0, 0), changed.pieces[5].surface(0.5, 0)[0], (-0.1, 0, 0)
                    ),
                )
        else:
            assert isinstance(evidence, Report)
            assert options["mode"].motion is ContactMotion.ADAPTIVE_HARDWARE
            assert options["mode"].evidence[0].route is changed
            return _result(changed, ContactResult("separated", 7))
        options["on_blocked"](JointHandoff(changed, blocker))
        return _result(route)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints", stage
    )
    result = _run(source, gate)
    assert result is not None and result.route is changed and result.contact is not None
    assert result.detail["iterations"] == 4 and result.detail["newton_steps"] == 4
    assert result.detail["contact_pairs"] == 20 and result.detail["reflected_folds"] == [1, 2]
    assert [c["maximum_updates"] for c in captured] == [4, 3, 2, 1]
    assert [c["remaining_pairs"] for c in captured] == [100, 95, 90, 85]
    assert [c["maximum_cpu_seconds"] for c in captured] == pytest.approx([0.35, 0.34, 0.33, 0.32])


@pytest.mark.parametrize("work", (Work(1, 100, 0.35, 2), Work(4, 5, 0.35, 2)))
def test_exhausted_work_cannot_start_another_stage(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    work: Work,
) -> None:
    """
    Either spent update or spent pair allowance prevents the next actual-blocker correction.
    """
    gate = _gate(source)
    calls = []

    def stage(*_args: Any, **options: Any) -> Result:
        """
        Consume one allocation and retain an actual strict outcome at the mocked boundary.
        """
        calls.append(options)
        options["on_blocked"](JointHandoff(source, _crossing(source, 0, 4)))
        return _result(source)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints", stage
    )
    result = _run(source, gate, work=work)
    assert result is not None and result.contact is None and result.route is source
    assert len(calls) == 1 and result.detail["stop_reason"] == "work_exhausted"


def test_a_return_is_never_reflected_twice_to_retry_an_unresolved_layout(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A recurring measured interval gets one sign-preserving continuation, then stops without flipping back.
    """
    calls = []

    def stage(*_args: Any, **options: Any) -> Result:
        """
        Return the same checker witness after one attempted material-return correction.
        """
        calls.append(options)
        options["on_blocked"](JointHandoff(source, _crossing(source, 0, 4)))
        return _result(source)

    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints", stage
    )
    result = _run(source, _gate(source))
    assert result is not None and result.contact is None and len(calls) == 3
    assert isinstance(calls[1]["mode"], MaterialGuidance)
    assert isinstance(calls[2]["mode"], ContactGuidance)
    assert calls[2]["mode"].motion is ContactMotion.BEND_JOINTS
    assert result.detail["material_continuation"] is True
    assert result.detail["stop_reason"] == "unsupported_or_repeated_return"


def test_repeated_return_continues_actual_candidate_and_evidence_with_remaining_work(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain the measured crossing and connector feature without repeating a reflection or renewing work.
    """
    gate = _gate(source)
    hardware = Report(
        "blocked", 1, Witness("end", 5, (0.5, 0, 0), source.pieces[5].pose.origin, (-0.1, 0, 0))
    )
    gate.measure.return_value = hardware
    changed = restore(snapshot(source))
    crossing = _crossing(changed, 0, 4)
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(deviation_sequence), name, lambda: clock[0])
    calls: list[dict[str, Any]] = []

    def stage(
        route: FoldRoute,
        evidence: Any,
        _terminal: Gate,
        _checkpoint: Any,
        _record: Any,
        **options: Any,
    ) -> Result:
        """
        Yield a closed material blocker after reflection, then certify the exact handed-off candidate.
        """
        calls.append(options)
        clock[0] += 0.01
        if len(calls) == 1:
            assert isinstance(options["mode"], MaterialGuidance)
            options["on_blocked"](JointHandoff(changed, crossing))
            return _result(source, newton=5, pairs=11)
        assert route is changed and evidence is crossing
        mode = options["mode"]
        assert isinstance(mode, ContactGuidance) and mode.motion is ContactMotion.BEND_JOINTS
        assert mode.evidence[-1].route is changed and mode.evidence[-1].report is hardware
        return _result(changed, ContactResult("separated", 17), newton=2, pairs=17)

    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    result = deviation_sequence.recover(
        source,
        _crossing(source, 0, 4),
        gate,
        lambda: None,
        lambda event: None,
        work=Work(4, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )
    assert result.route is changed and result.contact is not None
    assert len(calls) == 2 and result.detail["reflected_folds"] == [1]
    assert result.detail["material_continuation"] is True
    assert result.detail["newton_steps"] == 7 and result.detail["contact_pairs"] == 28
    assert calls[1]["maximum_updates"] == 3 and calls[1]["remaining_pairs"] == 89
    assert calls[1]["maximum_cpu_seconds"] == pytest.approx(0.34)
    assert calls[1]["maximum_seconds"] == pytest.approx(1.99)


def test_full_report_cost_can_discard_an_otherwise_certified_late_result(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reporting overhead cannot escape the original CPU ceiling or transfer acceptance afterward.
    """
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setattr(
            "experiments.experiment_ribbon_terminal_hardware.deviation_sequence." + name,
            lambda: clock[0],
        )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints",
        Mock(return_value=_result(source, ContactResult("separated", 5))),
    )

    def record(event: dict[str, Any]) -> None:
        """
        Consume the remaining time at the final serialized report boundary.
        """
        if event["status"] == "separated":
            clock[0] = 0.36

    result = _run(source, _gate(source), record=record)
    assert (
        result is not None
        and result.contact is None
        and result.detail["stop_reason"] == "phase_budget"
    )


def test_newton_work_cannot_be_hidden_in_a_smaller_reported_update_count(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Protect the original six-Newton-per-update bound even at a malformed stage boundary.
    """
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints",
        Mock(return_value=_result(source, newton=7, iterations=1)),
    )
    with pytest.raises(ArithmeticError, match="remaining allocation"):
        _run(source, _gate(source), work=Work(1, 100, 0.35, 2))


@pytest.mark.parametrize(
    "evidence", (ContactResult("unresolved", 1), Report("unresolved", 1), Report("blocked", 1))
)
def test_uncertainty_or_missing_witness_never_becomes_a_handoff(
    source: FoldRoute, evidence: Any
) -> None:
    """
    A missed or incomplete measurement is not a strict geometry blocker.
    """
    with pytest.raises(ValueError, match="demonstrated intrusion"):
        JointHandoff(source, evidence)


def test_open_caps_cannot_be_handed_to_a_fresh_recovery(source: FoldRoute) -> None:
    """
    Preserve exact stage lineage; no later strategy repairs an unclosed failed proposal as if closed.
    """
    target = replace(source.targets, end=source.targets.end.translated(Vector3(1, 0, 0), 1))
    opened = replace(source, targets=target)
    with pytest.raises(ValueError, match="closed ordered caps"):
        JointHandoff(opened, _crossing(source, 0, 4))


def test_child_contact_acceptance_cannot_bypass_route_bound_hardware(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reject a completed material certificate when final hardware remains incomplete.
    """
    gate = _gate(source)
    gate.certify.return_value = Report("unresolved", 12)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.deviation_sequence.recover_joints",
        Mock(return_value=_result(source, ContactResult("separated", 5))),
    )
    result = _run(source, gate)
    assert result is not None and result.contact is None
    assert result.detail["status"] == "unresolved"
    assert result.detail["stop_reason"] == "final_hardware_not_clear"


def test_source_and_cancellation_failures_remain_hard_stops(source: FoldRoute) -> None:
    """
    A failed caller guard cannot become optional recovery exhaustion or start any stage.
    """
    gate = _gate(source)
    checkpoint = Mock(side_effect=RuntimeError("source drift"))
    with pytest.raises(RuntimeError, match="source drift"):
        deviation_sequence.recover(
            source,
            _pending(),
            gate,
            checkpoint,
            lambda e: None,
            work=Work(4, 100, 0.35, 2),
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
        )
    gate.measure.assert_not_called()


def test_real_joint_entry_yields_the_measured_candidate_without_a_second_contact_constraint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise real cap/material equations and preserve the exact route passed to the mocked checker.
    """
    source = _source()
    gate = _gate(source)
    checker = Mock(return_value=_crossing(source, 0, 1))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact.inspect_contact", checker
    )
    yielded: list[JointHandoff] = []
    result = joint_contact.recover(
        source,
        _depth(0, 2),
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=ContactGuidance(),
        on_blocked=yielded.append,
    )
    assert result is not None and result.contact is None and len(yielded) == 1
    assert yielded[0].route is checker.call_args.args[0]
    assert yielded[0].evidence is checker.return_value
    assert result.detail["flat_constraints"] == 1 and result.detail["contact_pairs"] == 5
    assert result.detail["stop_reason"] == "material_handoff"


def test_hardware_report_can_initialize_straight_correction_without_fake_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Initialize the new hardware-only entry from actual finite-box measurement on an analytical control.
    """
    from experiments.experiment_ribbon_terminal_hardware.check import inspect

    source = _source()
    gate = _gate(source)
    gate.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, gate.hardware)
    assert report.status == "blocked" and report.witness is not None
    projection = Mock(return_value=None)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.joint_contact.shortest_run_step",
        projection,
    )
    result = joint_contact.recover(
        source,
        report,
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=1,
        mode=ContactGuidance((FeatureEvidence(source, report),), ContactMotion.STRAIGHT_SLOTS),
    )
    assert result is not None and result.contact is None and result.detail["flat_constraints"] == 0
    projection.assert_called_once()
    assert all(i % 4 == 0 for i in projection.call_args.args[0].indices)


@pytest.mark.parametrize("blocker_kind", ("hardware", "material"))
@pytest.mark.parametrize("initial_newton", (6, 7))
def test_blocked_mating_handoff_uses_only_remaining_original_work(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    blocker_kind: str,
    initial_newton: int,
) -> None:
    """
    Preserve the original mating first step, then follow a real closed blocker without renewing its allocation.
    """
    gate = _gate(source)
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(deviation_sequence), name, lambda: clock[0])
    calls: list[dict[str, Any]] = []
    crossing = _crossing(source, 0, 4)

    def stage(
        route: FoldRoute,
        evidence: Any,
        terminal: Gate,
        _checkpoint: Any,
        _record: Any,
        **options: Any,
    ) -> Result:
        """
        Mock the physical solver boundary while checking actual evidence identity and accounting.
        """
        assert route is source and terminal is gate
        calls.append(options)
        clock[0] += 0.01
        if len(calls) == 1:
            gate.measure.assert_not_called()
            assert options["mode"] is JointMode.BLOCKED_MATING and evidence is crossing.witness
            blocker = (
                Report(
                    "blocked",
                    1,
                    Witness("end", 5, (0.5, 0, 0), source.pieces[5].pose.origin, (-0.1, 0, 0)),
                )
                if blocker_kind == "hardware"
                else _crossing(source, 0, 4)
            )
            options["on_blocked"](JointHandoff(source, blocker))
            return _result(source, newton=initial_newton, pairs=11)
        if blocker_kind == "hardware":
            assert isinstance(evidence, Report)
            assert isinstance(options["mode"], ContactGuidance)
            assert options["mode"].motion is ContactMotion.ADAPTIVE_HARDWARE
            assert options["mode"].evidence[0].route is source
        else:
            assert isinstance(evidence, Penetration)
            assert isinstance(options["mode"], MaterialGuidance)
            assert options["mode"].length is ReturnLength.RESTORATION_GOAL
        return _result(source, ContactResult("separated", 17), newton=2, pairs=17)

    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    result = deviation_sequence.recover(
        source,
        crossing,
        gate,
        lambda: None,
        lambda event: None,
        work=Work(4, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        start=deviation_sequence.SequenceStart.BLOCKED_MATING,
    )
    assert result.contact is not None and result.contact.status == "separated"
    assert len(calls) == 2 and result.detail["stages"] == 2
    assert calls[1]["maximum_updates"] == 4 - ceil(initial_newton / 6)
    assert calls[1]["remaining_pairs"] == 89
    assert calls[1]["maximum_cpu_seconds"] == pytest.approx(0.34)
    assert calls[1]["maximum_seconds"] == pytest.approx(1.99)
    assert result.detail["iterations"] == ceil(initial_newton / 6) + 1
    assert result.detail["newton_steps"] == initial_newton + 2
    assert result.detail["contact_pairs"] == 28 and result.detail["contacts"] == 2
    assert result.detail["cpu_seconds"] == pytest.approx(0.02)
    assert result.detail["length_ceiling_released"] is True


def test_unsupported_initial_mating_preparation_declines_without_geometry_work(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A missing initial model remains a zero-motion decline rather than a new recovery attempt.
    """
    gate = _gate(source)
    action = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", action)
    result = deviation_sequence.recover(
        source,
        _crossing(source, 0, 4),
        gate,
        lambda: None,
        lambda event: None,
        work=Work(4, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        start=deviation_sequence.SequenceStart.BLOCKED_MATING,
    )
    assert result.contact is None and result.route is source
    assert result.detail["initial_mating_supported"] is False
    assert (
        result.detail["iterations"]
        == result.detail["newton_steps"]
        == result.detail["contacts"]
        == 0
    )
    action.assert_called_once()
    gate.measure.assert_not_called()
    monkeypatch.setitem(vars(mating_feasibility), "recover_sequence", Mock(return_value=result))
    assert (
        mating_feasibility.recover(
            source,
            source,
            _crossing(source, 0, 4),
            gate,
            1e-5,
            Work(4, 100, 0.35, 2),
            lambda: None,
            lambda event: None,
        )
        is None
    )


@pytest.mark.parametrize(
    "policy", (BaselinePolicy.GUIDE_IMPROVEMENT, BaselinePolicy.RESTORE_BLOCKED)
)
@pytest.mark.parametrize("released", (False, True))
def test_mating_entry_isolates_blocked_continuation_from_clear_quality_improvement(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    policy: BaselinePolicy,
    released: bool,
) -> None:
    """
    Only a blocked baseline can use the sequence or carry its released length-goal selection policy.
    """
    child = _result(source, ContactResult("separated", 5))
    child.detail["length_ceiling_released"] = released
    coupled, sequence = Mock(return_value=child), Mock(return_value=child)
    monkeypatch.setitem(vars(mating_feasibility), "recover_joints", coupled)
    monkeypatch.setitem(vars(mating_feasibility), "recover_sequence", sequence)
    result = mating_feasibility.recover(
        source,
        source,
        _crossing(source, 0, 4),
        _gate(source),
        1e-5,
        Work(4, 100, 0.35, 2),
        lambda: None,
        lambda event: None,
        baseline_policy=policy,
    )
    assert result is not None
    if policy is BaselinePolicy.RESTORE_BLOCKED:
        sequence.assert_called_once()
        coupled.assert_not_called()
        assert sequence.call_args.kwargs["start"] is deviation_sequence.SequenceStart.BLOCKED_MATING
    else:
        coupled.assert_called_once()
        sequence.assert_not_called()
        assert coupled.call_args.kwargs["mode"] is JointMode.MATING_CEILING
    expected = (
        BaselinePolicy.RESTORE_BLOCKED_GOAL
        if released and policy is BaselinePolicy.RESTORE_BLOCKED
        else policy
    )
    assert result.baseline_policy is expected


def test_blocked_mating_cannot_renew_an_exhausted_initial_stage(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A closed blocker transfers evidence but no work when the initial stage consumed the last update.
    """
    gate = _gate(source)

    def stage(*_args: Any, **options: Any) -> Result:
        """
        Spend the sole original update before yielding actual mocked material evidence.
        """
        assert options["maximum_updates"] == 1
        options["on_blocked"](JointHandoff(source, _crossing(source, 0, 4)))
        return _result(source, newton=1)

    action = Mock(side_effect=stage)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", action)
    result = deviation_sequence.recover(
        source,
        _crossing(source, 0, 4),
        gate,
        lambda: None,
        lambda event: None,
        work=Work(1, 100, 0.35, 2),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        start=deviation_sequence.SequenceStart.BLOCKED_MATING,
    )
    assert result.contact is None and result.detail["iterations"] == result.detail["stages"] == 1
    assert result.detail["length_ceiling_released"] is False
    action.assert_called_once()
    gate.measure.assert_not_called()
