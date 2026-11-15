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
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_schedule import Action
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_adaptive_continuation import reply
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
    ) -> ContactResult | None:
        """
        Model the negative checker boundary; its strict inverse behavior is tested independently.
        """
        del self, check
        if route is source:
            return None
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
    planner.assert_not_called()


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

    def discover(
        self: object, route: FoldRoute, report: Report, pairs: int, check: Callable[[], None]
    ) -> ContactResult | None:
        """
        Isolate the later inserted-module crossing from the initial source screen.
        """
        del self, report, pairs, check
        return None if route is source else crossing

    monkeypatch.setattr(runner.HardwareContacts, "inspect", discover)
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


@pytest.mark.parametrize("accepted", (False, True))
def test_initial_competing_crossing_keeps_hardware_and_original_work_before_any_rewrite(
    monkeypatch: pytest.MonkeyPatch, accepted: bool
) -> None:
    """
    Exercise the real continuation/sequence with explicit negative and joint-checker boundaries.

    The mocked occupied crossing is scheduling evidence only; no geometric
    clearance is inferred from this protocol test or its accepted checker double.
    """
    source, hardware, evidence = _source()
    assert evidence.witness is not None
    crossing = ContactResult(
        "penetration",
        3,
        Penetration((0, len(source.pieces) - 1), (0.5, 0, 0), (0.5, 0, 0), evidence.witness.point),
    )
    discovery = Mock(return_value=crossing)
    monkeypatch.setattr(runner.HardwareContacts, "inspect", discovery)
    planner = Mock(return_value=None)
    monkeypatch.setitem(vars(runner), "plan", planner)

    def joint(route: FoldRoute, contact: Penetration, *args: Any, **options: Any) -> Result:
        """
        Verify the same material witness, actual connector evidence and reduced shared allocation.
        """
        del args
        assert route is source and contact is crossing.witness
        mode = options["mode"]
        assert isinstance(mode, MaterialGuidance)
        assert len(mode.evidence) == 1
        assert mode.evidence[0].route is source and mode.evidence[0].report is evidence
        assert options["maximum_updates"] == 1 and options["maximum_newton_steps"] == 6
        assert options["remaining_pairs"] == 97
        return reply(route, accepted)

    stage = Mock(side_effect=joint)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    terminal = Mock(spec=Gate, hardware=hardware)
    terminal.measure.return_value = evidence
    terminal.certify.return_value = Report("clear", 1)
    records: list[dict[str, Any]] = []
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        records.append,
        work=Work(2, 100, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and (result.contact is not None) is accepted
    assert result.detail["roots_attempted"] == result.detail["rewrites"] == 0
    assert result.detail["iterations"] == 1 and result.detail["newton_steps"] == 2
    assert result.detail["contact_pairs"] == 10
    assert result.detail["correction_schedule"] == Action.CORRECT_COMPETING.value
    discovery.assert_called_once()
    stage.assert_called_once()
    if accepted:
        planner.assert_not_called()
        assert terminal.certify.called
    else:
        planner.assert_called_once()
        assert planner.call_args.args[0] is source and planner.call_args.args[1] is evidence
        terminal.certify.assert_not_called()


@pytest.mark.parametrize("kind", ("skipped", "unresolved", "limited"))
def test_initial_negative_uncertainty_preserves_original_hardware_refinement(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """
    A missing or incomplete negative result cannot claim clearance or select a material reversal.
    """
    source, hardware, evidence = _source()
    negative = (
        None
        if kind == "skipped"
        else ContactResult("unresolved", 3, limit="depth" if kind == "limited" else None)
    )
    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(return_value=negative))
    planner = Mock(return_value=None)
    correction = Mock(side_effect=AssertionError("Uncertainty must not invent a material crossing"))
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "continue_fixed", correction)
    terminal = Mock(spec=Gate, hardware=hardware)
    records: list[dict[str, Any]] = []
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        records.append,
        work=Work(2, 100, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is None
    planner.assert_called_once()
    assert planner.call_args.args[0] is source and planner.call_args.args[1] is evidence
    correction.assert_not_called()
    terminal.certify.assert_not_called()
    assert records[0]["status"] == "initial_competing_contact"
    assert records[0]["contact_scope"] == "negative_discovery_only"


@pytest.mark.parametrize("constructed", (False, True))
def test_failed_initial_trial_requires_new_geometry_before_ordinary_correction(
    monkeypatch: pytest.MonkeyPatch, constructed: bool
) -> None:
    """
    Keep the closed incumbent, charge the failed trial, and prohibit correction renewal on unchanged topology.

    Actual closed splicing and occupied hardware evidence exercise ownership;
    explicit correction/checker doubles isolate the nonrenewable work ledger.
    """
    source, hardware, evidence = _source()
    assert evidence.witness is not None
    proposal = _proposal(Window(source, 0, 1))
    local = _bump(proposal.window)
    candidate = proposal.window.splice(local)
    blocked = inspect(candidate, hardware)
    assert blocked.status == "blocked" and blocked.witness is not None
    assert blocked.witness.piece < len(local.pieces)
    crossing = ContactResult(
        "penetration",
        3,
        Penetration((0, len(source.pieces) - 1), (0.5, 0, 0), (0.5, 0, 0), evidence.witness.point),
    )

    def discover(
        self: object, route: FoldRoute, report: Report, pairs: int, check: Callable[[], None]
    ) -> ContactResult | None:
        """
        Supply only the initial competing crossing and no later material evidence.
        """
        del self, report, pairs, check
        return crossing if route is source else None

    def construct(proposed: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute | None:
        """
        Debit a local root even when it fails to produce new closed material.
        """
        del minimum, args
        assert proposed is proposal
        roots.attempted += 1
        return local if constructed else None

    calls: list[Work] = []

    def correct(
        route: FoldRoute, observed: ContactResult | Report, *args: Any, **options: Any
    ) -> Result:
        """
        Verify the original remainder after both the failed trial and the new root.
        """
        del args
        calls.append(options["work"])
        child = reply(route, len(calls) > 1)
        if len(calls) == 1:
            assert route is source and observed is crossing
            assert calls[-1].updates == 1 and calls[-1].newton_steps == 6
            child.detail.update(newton_steps=6, contacts=0, contact_pairs=5)
        else:
            assert constructed and route is not source and observed is blocked
            assert calls[-1].updates == 2 and calls[-1].newton_steps == 18
            assert calls[-1].pairs == 92
            child.detail.update(iterations=2, newton_steps=7)
        return child

    monkeypatch.setattr(runner.HardwareContacts, "inspect", discover)
    planner = Mock(return_value=proposal)
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "construct", construct)
    monkeypatch.setitem(vars(runner), "continue_fixed", correct)
    terminal = Mock(spec=Gate, hardware=hardware, certify=Mock(return_value=blocked))
    result = runner.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        Mock(),
        work=Work(4, 100, 0.35, 2),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and (result.contact is not None) is constructed
    assert len(calls) == (2 if constructed else 1)
    assert result.detail["iterations"] == (4 if constructed else 2)
    assert result.detail["newton_steps"] == (13 if constructed else 6)
    assert result.detail["contact_pairs"] == (15 if constructed else 8)
    assert result.detail["initial_competing_trial"]["newton_steps"] == 6
    planner.assert_called_once()
    assert planner.call_args.args[0] is source and planner.call_args.args[1] is evidence
