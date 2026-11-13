"""
Charge early negative discovery without transferring acceptance, source identity or correction work.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_adaptive_events import _bump, _proposal, _source


@pytest.mark.parametrize("crossing", (False, True))
@pytest.mark.parametrize("hardware_clear", (False, True))
def test_current_crossing_can_refine_before_correction_but_never_replace_final_proofs(
    monkeypatch: pytest.MonkeyPatch,
    crossing: bool,
    hardware_clear: bool,
) -> None:
    """
    Use real closed splices and explicit checker doubles to test scheduling and shared pair accounting.
    """
    source, hardware, evidence = _source()
    negative: list[ContactResult] = []
    planned: list[Report | ContactResult] = []

    def discover(
        self: object, route: FoldRoute, report: Report, pairs: int, check: Callable[[], None]
    ) -> ContactResult:
        """
        Model the negative checker boundary; its strict inverse behavior is tested independently.
        """
        del self, check
        assert report is evidence and pairs == 100
        assert evidence.witness is not None
        negative_result = ContactResult(
            "penetration" if crossing else "unresolved",
            3,
            Penetration(
                (0, len(route.pieces) - 1), (0.5, 0, 0), (0.5, 0, 0), evidence.witness.point
            )
            if crossing
            else None,
        )
        negative.append(negative_result)
        return negative_result

    def propose(
        route: FoldRoute, observed: Report | ContactResult, *args: Any, **kwargs: Any
    ) -> Proposal:
        """
        Keep the second refinement inside the original two-update allowance.
        """
        del args, kwargs
        planned.append(observed)
        if len(planned) == 2:
            assert observed is (negative[0] if crossing else evidence)
        member = len(route.pieces) - 1 if len(planned) == 1 else 0
        return _proposal(Window(route, member, member + 1))

    def construct(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Debit one original root for each independently authored boundary-closed module.
        """
        del minimum, args
        roots.attempted += 1
        return _bump(proposal.window)

    monkeypatch.setattr(runner.HardwareContacts, "inspect", discover)
    monkeypatch.setitem(vars(runner), "plan", propose)
    monkeypatch.setitem(vars(runner), "construct", construct)
    correct = Mock(
        side_effect=AssertionError("Competing current crossing should use pending refinement")
    )
    monkeypatch.setitem(vars(runner), "continue_fixed", correct)
    proof = ContactResult("separated", 7)
    complete = Mock(return_value=proof)
    monkeypatch.setitem(vars(runner), "inspect_contact", complete)
    terminal = Mock(spec=Gate, hardware=hardware)
    terminal.certify.side_effect = (evidence, Report("clear", 1) if hardware_clear else evidence)
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(2, 100, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and len(planned) == 2 and len(negative) == 1
    assert result.detail["iterations"] == 2 and result.detail["roots_attempted"] == 2
    assert result.detail["newton_steps"] == 0
    assert result.detail["contact_pairs"] == (10 if hardware_clear else 3)
    assert result.detail.get("hardware_contact_refinements", 0) == int(crossing)
    correct.assert_not_called()
    if hardware_clear:
        assert result.contact is proof
        complete.assert_called_once()
        assert complete.call_args.kwargs["maximum_pairs"] == 97
    else:
        assert result.contact is None and result.route is source
        complete.assert_not_called()


def test_interrupted_negative_query_charges_only_its_bounded_upper_allowance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A phase stop during discovery cannot renew comparisons or proceed into another action.
    """
    source, hardware, evidence = _source()
    clock = [0.0]
    monkeypatch.setitem(vars(runner), "process_time", lambda: clock[0])
    proposal = _proposal(Window(source, len(source.pieces) - 1, len(source.pieces)))
    planner = Mock(return_value=proposal)
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=_bump(proposal.window)))

    def interrupt(
        self: object, route: FoldRoute, report: Report, pairs: int, check: Callable[[], None]
    ) -> None:
        """
        Expire the original parent clock while its first bounded query is active.
        """
        del self, route, report
        assert pairs == 10
        clock[0] = 0.36
        check()

    monkeypatch.setattr(runner.HardwareContacts, "inspect", interrupt)
    terminal = Mock(spec=Gate, hardware=hardware, certify=Mock(return_value=evidence))
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(3, 10, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is None
    assert result.detail["stop_reason"] == "phase_budget"
    assert (
        result.detail["contact_pairs"]
        == result.detail["interrupted_hardware_discovery_pairs"]
        == 10
    )
    planner.assert_called_once()


def test_contained_crossing_preserves_hardware_correction_and_shared_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A competing internal crossing cannot repeatedly preempt correction of its own intact module.
    """
    source, hardware, evidence = _source()
    assert evidence.witness is not None
    begin = evidence.witness.piece
    proposal = _proposal(Window(source, begin, begin + 1))
    planner = Mock(return_value=proposal)
    monkeypatch.setitem(vars(runner), "plan", planner)

    def construct(proposed: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Insert one actual closed module and debit its original fitted root.
        """
        del minimum, args
        roots.attempted += 1
        return _bump(proposed.window)

    monkeypatch.setitem(vars(runner), "construct", construct)
    crossing = ContactResult(
        "penetration",
        3,
        Penetration((begin, begin + 2), (0.5, 0, 0), (0.5, 0, 0), evidence.witness.point),
    )
    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(return_value=crossing))
    proof = ContactResult("separated", 7)

    def correct(route: FoldRoute, observed: Report, *args: Any, **kwargs: Any) -> Result:
        """
        Model the existing correction boundary, retaining hardware evidence and reduced budgets.
        """
        del args
        assert observed is evidence
        assert kwargs["work"].updates == 1 and kwargs["work"].pairs == 97
        return Result(
            route,
            proof,
            {
                "iterations": 1,
                "newton_steps": 2,
                "contacts": 1,
                "contact_pairs": 7,
                "contact_seconds": 0.0,
                "status": "separated",
                "stop_reason": "accepted",
            },
        )

    correction = Mock(side_effect=correct)
    monkeypatch.setitem(vars(runner), "continue_fixed", correction)
    terminal = Mock(spec=Gate, hardware=hardware, certify=Mock(return_value=evidence))
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(2, 100, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is proof
    assert result.detail["contact_pairs"] == 10 and result.detail["newton_steps"] == 2
    assert result.detail["iterations"] == 2 and result.detail["roots_attempted"] == 1
    assert result.detail.get("hardware_contact_refinements", 0) == 0
    planner.assert_called_once()
    correction.assert_called_once()
