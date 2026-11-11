"""
Prioritize witnessed hardware obstruction without inventing source contact evidence or renewing recovery.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result as Recovery
from experiments.experiment_ribbon_feature_insertion import solve
from experiments.experiment_ribbon_feature_insertion.allocation import Allocation
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import (
    branch_recovery,
    deferred_construction,
    solver_v2,
)
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_contact_refinement import _source
from tests.test_ribbon_feature_insertion import _targets


def _terminal(source: FoldRoute) -> Mock:
    """
    Keep real hardware intrusion evidence while mocking the external recovery certificate boundary.
    """
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, terminal.hardware)
    assert report.status == "blocked" and report.witness is not None
    terminal.measure.return_value = report
    terminal.certify.return_value = Report("clear", 1)
    return terminal


@pytest.mark.parametrize("disposition", ("blocked", "clear", "unresolved", "missing_witness"))
def test_constructor_defers_only_witnessed_hardware_and_never_invents_contact(
    monkeypatch: pytest.MonkeyPatch, disposition: str
) -> None:
    """
    Run real analytical allocation, mocking only the external hardware/contact measurement boundaries.
    """
    frames = Frames.create(_targets())
    source = _source(0.2)
    terminal = _terminal(source)
    witness = terminal.measure.return_value.witness
    assert witness is not None
    report = {
        "blocked": Report("blocked", 1, witness),
        "clear": Report("clear", 1),
        "unresolved": Report("unresolved", 1),
        "missing_witness": Report("blocked", 1),
    }[disposition]
    terminal.measure.return_value = report
    contact = Mock(return_value=ContactResult("separated", 1))
    monkeypatch.setitem(vars(solve), "inspect_contact", contact)
    events: list[dict[str, Any]] = []
    result = solve.construct(
        Boundary(frames.targets, 0.101),
        frames,
        (0.5,),
        1e-5,
        lambda: None,
        events.append,
        maximum_straight_mm=frames.guide.distances[-1],
        terminal=terminal,
    )
    if disposition == "blocked":
        assert result.route is result.contact is None and result.deferred
        assert result.contacts == result.contact_pairs == 0
        assert result.unattempted_contacts == result.closed_branches
        contact.assert_not_called()
        deferred = [event for event in events if event["stage"] == "feature_contact_deferred"]
        assert deferred and all(event["contact"] == "unmeasured" for event in deferred)
    else:
        assert result.route is not None and result.contact is not None and not result.deferred
        assert contact.called and result.contact.status == "separated"


def test_constructor_hardware_source_error_stops_before_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A failed shared hardware boundary cannot be treated as eligibility or ordinary clearance.
    """
    frames = Frames.create(_targets())
    terminal = Mock(spec=Gate)
    terminal.measure.side_effect = RuntimeError("source changed")
    contact = Mock()
    monkeypatch.setitem(vars(solve), "inspect_contact", contact)
    with pytest.raises(RuntimeError, match="source changed"):
        solve.construct(
            Boundary(frames.targets, 0.101),
            frames,
            (0.5,),
            1e-5,
            lambda: None,
            lambda e: None,
            terminal=terminal,
        )
    contact.assert_not_called()


@pytest.mark.parametrize("optimized", (False, True))
@pytest.mark.parametrize("enabled", (False, True))
def test_only_optimized_hardware_v2_supplies_the_same_gate_to_construction(
    monkeypatch: pytest.MonkeyPatch, optimized: bool, enabled: bool
) -> None:
    """
    Verify actual v2 wiring while leaving all geometry solving at its mocked external boundary.
    """
    terminal = Mock(spec=Gate)
    terminal.detail.return_value = {"enabled": True}
    factory = Mock(return_value=terminal)
    construction = Mock(
        return_value=solve.Result(None, None, "no_fixed_radius_closure", 0, 0, 0, 0)
    )
    monkeypatch.setitem(vars(solver_v2), "Gate", factory)
    monkeypatch.setitem(vars(solver_v2), "construct", construction)
    result = solver_v2.solve(
        _targets(), Settings(0, False, optimized, enabled), lambda: None, lambda e: None
    )
    assert result.route is None
    assert construction.call_args.kwargs["terminal"] is (
        terminal if optimized and enabled else None
    )
    assert factory.call_count == int(enabled)


@pytest.fixture
def pending() -> tuple[solve.Result, Mock, FoldRoute]:
    """
    Retain one actual analytical hardware blocker with contact unmeasured on that source.
    """
    source = _source(0.2)
    terminal = _terminal(source)
    allocation = Mock(spec=Allocation, route=source, chain=SimpleNamespace(roots=(0, 1)))
    result = solve.Result(
        None,
        None,
        "hardware_blocked_contact_deferred",
        1,
        0.002,
        2,
        1,
        contact_pairs=17,
        deferred=(allocation,),
    )
    return result, terminal, source


def _child(source: FoldRoute, separated: bool) -> Recovery:
    """
    Supply only a controlled external recovery disposition, not a physical success claim.
    """
    return Recovery(
        source,
        ContactResult("separated", 7) if separated else None,
        {
            "status": "separated" if separated else "unresolved",
            "iterations": 1,
            "newton_steps": 3,
            "contacts": 1,
            "contact_pairs": 7,
            "contact_seconds": 0.001,
            "stop_reason": "accepted" if separated else "phase_budget",
        },
    )


@pytest.mark.parametrize("outcome", ("accepted", "unresolved", "unsupported", "hardware_blocked"))
def test_one_deferred_action_keeps_real_proof_accounting_and_never_falls_through(
    pending: tuple[solve.Result, Mock, FoldRoute],
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """
    An unmeasured source cannot serve as fallback; child acceptance requires actual named final boundaries.
    """
    original, terminal, source = pending
    child = None if outcome == "unsupported" else _child(source, outcome != "unresolved")
    if outcome == "hardware_blocked":
        terminal.certify.return_value = terminal.measure.return_value
    action = Mock(return_value=child)
    monkeypatch.setitem(vars(deferred_construction), "recover_terminal", action)
    ordinary = Mock(
        side_effect=AssertionError("A failed deferred action cannot renew material work")
    )
    monkeypatch.setitem(vars(branch_recovery), "recover_failed", ordinary)
    events: list[dict[str, Any]] = []
    result, detail = branch_recovery.recover_construction(
        original,
        Frames.create(_targets()),
        1e-5,
        lambda: None,
        events.append,
        selection_policy=branch_recovery.Policy.MONOTONIC,
        terminal=terminal,
    )
    assert detail is not None and detail["source_contact"] == "unmeasured"
    action.assert_called_once()
    ordinary.assert_not_called()
    options = action.call_args.kwargs
    assert options["remaining_pairs"] == 2048 - 17 and options["maximum_updates"] == 4
    assert 0 < options["maximum_cpu_seconds"] <= 0.35 and 0 < options["maximum_seconds"] <= 2
    assert action.call_args.args[0] is source
    assert result.contact_pairs == 17 + (0 if child is None else 7)
    assert result.contacts == 1 + (0 if child is None else 1)
    assert (result.route is not None) is (outcome == "accepted")
    if outcome == "accepted":
        assert result.contact is not None and result.contact.status == "separated"
    else:
        assert result.contact is None


def test_eligibility_time_is_debited_and_source_errors_stop_without_child_work(
    pending: tuple[solve.Result, Mock, FoldRoute], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Even cached eligibility cannot reset the original clocks or suppress hard caller failures.
    """
    original, terminal, _ = pending
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(deferred_construction), name, lambda: clock[0])
    report = terminal.measure.return_value

    def exhausted(*args: object) -> Report:
        """
        Consume the original CPU pool before the proposed child can begin.
        """
        del args
        clock[0] = 0.35
        return report

    terminal.measure.side_effect = exhausted
    action = Mock()
    monkeypatch.setitem(vars(deferred_construction), "recover_terminal", action)
    result, detail = deferred_construction.recover(
        original, terminal, 1e-5, lambda: None, lambda e: None
    )
    assert result.route is result.contact is None and detail["stop_reason"] == "phase_budget"
    action.assert_not_called()
    terminal.measure.side_effect = RuntimeError("source changed")
    with pytest.raises(RuntimeError, match="source changed"):
        deferred_construction.recover(original, terminal, 1e-5, lambda: None, lambda e: None)
    action.assert_not_called()


def test_invalid_child_caps_or_enlarged_work_cannot_be_accepted(
    pending: tuple[solve.Result, Mock, FoldRoute], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Independently retain actual cap/material and original work gates at the new orchestration boundary.
    """
    original, terminal, source = pending
    child = _child(source, True)
    child = replace(
        child, route=replace(source, targets=replace(source.targets, end=Vector3(100, 0, 0)))
    )
    action = Mock(return_value=child)
    monkeypatch.setitem(vars(deferred_construction), "recover_terminal", action)
    with pytest.raises(ArithmeticError, match="ordered caps"):
        deferred_construction.recover(original, terminal, 1e-5, lambda: None, lambda e: None)
    child = _child(source, True)
    child.detail["contact_pairs"] = 2048
    action.return_value = child
    with pytest.raises(ArithmeticError, match="original work"):
        deferred_construction.recover(original, terminal, 1e-5, lambda: None, lambda e: None)
