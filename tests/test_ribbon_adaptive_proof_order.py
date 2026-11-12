"""
Use strict hardware evidence before costly contact work without treating either missing proof as acceptance.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import (
    Proposal,
)
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import (
    plan as plan_material,
)
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source


@pytest.fixture
def configured(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FoldRoute, Hardware, Report, Mock]:
    """
    Configure one real boundary-closed module with explicit planner and construction boundaries.
    """
    source, hardware, evidence = _source()
    proposal = _proposal(Window(source, 0, 1))
    planner = Mock(return_value=proposal)
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=_bump(proposal.window)))
    return source, hardware, evidence, planner


def test_strict_current_hardware_witness_defers_contact_then_requires_both_final_proofs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A real unchanged occupied member can guide another rewrite; explicit checker doubles grant final clearance.
    """
    source, hardware, evidence = _source()
    visited: list[FoldRoute] = []

    def propose(route: FoldRoute, observed: Report, *args: Any, **kwargs: Any) -> Proposal:
        """
        Use two authored straight modules while verifying the intermediate witness is still strictly occupied.
        """
        del args, kwargs
        if visited:
            assert observed is evidence and route.pieces[0] is source.pieces[0]
            assert plan_material(route, observed, hardware, lambda: None) is not None
        index = 0 if visited else len(route.pieces) - 1
        visited.append(route)
        return _proposal(Window(route, index, index + 1))

    monkeypatch.setitem(vars(runner), "plan", propose)
    monkeypatch.setitem(vars(runner), "construct", lambda proposal, *args: _bump(proposal.window))
    certificate = ContactResult("separated", 7)
    contact = Mock(return_value=certificate)
    monkeypatch.setitem(vars(runner), "inspect_contact", contact)
    terminal = Mock(
        spec=Gate, hardware=hardware, certify=Mock(side_effect=(evidence, Report("clear", 1)))
    )
    recorded: list[dict[str, Any]] = []
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        recorded.append,
        work=Work(2, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is certificate and len(visited) == 2
    assert result.detail["iterations"] == 2 and result.detail["contacts"] == 1
    assert result.detail["contact_pairs"] == 7 and result.detail["contact_checks_deferred"] == 1
    contact.assert_called_once()
    assert result.detail["affine_witnesses"][0]["capacity"] == 32
    assert (
        contact.call_args.args[0] is result.route
        and contact.call_args.kwargs["maximum_pairs"] == 23
    )
    proofs = [e for e in recorded if e.get("stage") == "adaptive_proof"]
    assert proofs[0]["contact"] is None and proofs[0]["hardware"] == asdict(evidence)
    assert proofs[1]["contact"] == asdict(certificate)


@pytest.mark.parametrize("hardware_status", ("unresolved", "blocked"))
def test_uncertain_or_unwitnessed_hardware_cannot_authorize_more_events_or_acceptance(
    hardware_status: Literal["unresolved", "blocked"],
    configured: tuple[FoldRoute, Hardware, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Neither uncertain report invents a repair direction or substitutes for missing final clearance.
    """
    source, hardware, evidence, planner = configured
    contact = Mock(return_value=ContactResult("unresolved", 11))
    monkeypatch.setitem(vars(runner), "inspect_contact", contact)
    result = runner.recover(
        source,
        evidence,
        Mock(spec=Gate, hardware=hardware, certify=Mock(return_value=Report(hardware_status, 1))),
        lambda: None,
        Mock(),
        work=Work(4, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None and result.route is source
    assert result.detail["stop_reason"] == "uncertain_global_proof"
    assert result.detail["contacts"] == 1 and result.detail["contact_pairs"] == 11
    assert result.detail["contact_checks_deferred"] == 0
    planner.assert_called_once()
    contact.assert_called_once()


@pytest.mark.parametrize("hardware_status", ("unresolved", "blocked"))
def test_unknown_hardware_cannot_suppress_independent_contact_guidance(
    hardware_status: Literal["unresolved", "blocked"],
    configured: tuple[FoldRoute, Hardware, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    An explicit contact-checker witness can reach planning while hardware has no usable witness.

    The contact report is a protocol double; current material validation belongs
    to the planner and is tested separately. No physical clearance is asserted.
    """
    source, hardware, evidence, planner = configured
    assert evidence.witness is not None
    window = Window(source, 0, 1)
    planner.side_effect = (_proposal(window), None)
    witness = Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), evidence.witness.point)
    contact = ContactResult("penetration", 11, witness)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=contact))

    def decline(route: FoldRoute, *args: Any, **kwargs: Any) -> Result:
        """
        Observe independent contact guidance at the correction boundary without claiming physical clearance.
        """
        del args, kwargs
        return Result(
            route,
            None,
            {
                "status": "unresolved",
                "stop_reason": "joint_no_descent",
                "iterations": 1,
                "newton_steps": 0,
                "contacts": 0,
                "contact_pairs": 0,
                "contact_seconds": 0.0,
                "motion_attempted": True,
                "hardware_preparation_only": False,
            },
        )

    correction = Mock(side_effect=decline)
    monkeypatch.setitem(vars(runner), "continue_fixed", correction)
    result = runner.recover(
        source,
        evidence,
        Mock(spec=Gate, hardware=hardware, certify=Mock(return_value=Report(hardware_status, 1))),
        lambda: None,
        Mock(),
        work=Work(4, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None and planner.call_count == 1
    correction.assert_called_once()
    assert correction.call_args.args[1] is contact
    assert result.detail["stop_reason"] == "joint_no_descent"


def test_hardware_clearance_does_not_hide_an_unresolved_contact_report(
    configured: tuple[FoldRoute, Hardware, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep exact incomplete contact evidence, pair costs and hardware-before-contact ordering in the receipt.
    """
    source, hardware, evidence, planner = configured
    order: list[str] = []
    unresolved = ContactResult("unresolved", 11, unresolved_pieces=(1, 3), limit="depth")

    def inspect(*args: Any, **kwargs: Any) -> ContactResult:
        """
        Model one bounded completed proof with unresolved geometry, not clearance.
        """
        del args, kwargs
        order.append("contact")
        return unresolved

    def certify(*args: Any) -> Report:
        """
        Expose the scheduling order independently of the synthetic proof result.
        """
        del args
        order.append("hardware")
        return Report("clear", 1)

    monkeypatch.setitem(vars(runner), "inspect_contact", inspect)
    records: list[dict[str, Any]] = []
    result = runner.recover(
        source,
        evidence,
        Mock(spec=Gate, hardware=hardware, certify=certify),
        lambda: None,
        records.append,
        work=Work(4, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None and result.route is source
    assert order == ["hardware", "contact"] and result.detail["contact_pairs"] == 11
    receipt = next(e for e in records if e.get("stage") == "adaptive_proof")
    assert receipt["contact"] == asdict(unresolved) and receipt["hardware"]["status"] == "clear"
    planner.assert_called_once()


def test_hardware_measurement_cannot_bypass_original_phase_clock(
    configured: tuple[FoldRoute, Hardware, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A hardware result arriving after the phase allowance stops before contact construction or acceptance.
    """
    source, hardware, evidence, _ = configured
    clock = [0.0]
    monkeypatch.setitem(vars(runner), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(runner), "perf_counter", lambda: clock[0])
    contact = Mock(side_effect=AssertionError("Expired work cannot enter contact proof"))
    monkeypatch.setitem(vars(runner), "inspect_contact", contact)

    def late(*args: Any) -> Report:
        """
        Finish a measurement beyond the original phase clock without resetting it.
        """
        del args
        clock[0] = 0.36
        return Report("clear", 1)

    result = runner.recover(
        source,
        evidence,
        Mock(spec=Gate, hardware=hardware, certify=late),
        lambda: None,
        Mock(),
        work=Work(4, 23, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert (
        result is not None
        and result.contact is None
        and result.detail["stop_reason"] == "phase_budget"
    )
    contact.assert_not_called()
