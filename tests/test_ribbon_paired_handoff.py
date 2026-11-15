"""
Keep paired return handoffs inside original adaptive ownership, hardware and resource pools.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result as FixedResult
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_paired_return.sequence import Result
from experiments.experiment_ribbon_terminal_hardware import adaptive_event_recovery as runner
from experiments.experiment_ribbon_terminal_hardware import paired_event_handoff as handoff
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_construction import Roots
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_plan import Proposal
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.joint_handoff import JointHandoff
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_adaptive_continuation import reply
from tests.test_ribbon_adaptive_events import _bump
from tests.test_ribbon_adaptive_handoff import Prepared
from tests.test_ribbon_adaptive_handoff import prepared as prepared


@pytest.mark.parametrize("accepted", [False, True])
def test_parent_absorbs_every_child_charge_and_retains_coexisting_hardware(
    accepted: bool, prepared: Prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A failed child cannot renew work or replace the incumbent; success spends the same original pool.

    Geometry and proof boundaries are explicitly doubled. This verifies parent
    accounting and evidence ownership at a refinement entry, not physical clearance.
    """
    witness = Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), prepared.source.targets.start)
    crossing = ContactResult("penetration", 3, witness)
    discovery = Mock(side_effect=(None, crossing))
    monkeypatch.setattr(runner.HardwareContacts, "inspect", discovery)
    certificate = ContactResult("separated", 7)

    def paired(
        source: FoldRoute,
        evidence: ContactResult,
        hardware: Report | None,
        terminal: Gate,
        checkpoint: Any,
        record: Any,
        **kwargs: Any,
    ) -> Result:
        """
        Verify the genuine residual allowance before returning one explicit child receipt.
        """
        assert source is not prepared.source and evidence is crossing
        assert hardware is prepared.evidence and terminal is prepared.terminal
        assert kwargs["maximum_roots"] == 4
        left = kwargs["work"]
        assert (left.updates, left.pairs, left.newton_steps) == (2, 28, 23)
        assert 0 < left.cpu_seconds < 0.35 and 0 < left.wall_seconds < 2
        checkpoint()
        record({"stage": "test_paired_boundary"})
        prepared.clock[0] += 0.03
        return Result(
            source if accepted else None,
            source,
            certificate if accepted else crossing,
            source,
            {
                "updates": 2,
                "roots_debited": 2,
                "newton_steps": 4,
                "pairs": 7,
                "contact_checks": 1,
                "contact_seconds": 0.01,
                "status": "accepted" if accepted else "unresolved",
                "stop_reason": "accepted" if accepted else "allocation_unresolved",
            },
        )

    child = Mock(side_effect=paired)
    monkeypatch.setitem(vars(runner), "recover_pair", child)
    result = runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        lambda event: None,
        work=Work(3, 31, 0.35, 2, 24),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and child.call_count == 1
    assert result.detail["iterations"] == 3 and result.detail["roots_attempted"] == 6
    assert result.detail["newton_steps"] == 5 and result.detail["contact_pairs"] == 10
    assert result.detail["contacts"] == 1
    assert (result.contact is certificate) == accepted
    assert (result.route is prepared.source) == (not accepted)


def test_absent_root_allowance_cannot_even_prepare_a_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Admission never derives or prepares geometry after the original root reserve is unavailable.
    """
    classify, recover = Mock(), Mock()
    monkeypatch.setitem(vars(handoff), "bracket", classify)
    monkeypatch.setitem(vars(handoff), "recover_pair", recover)
    assert (
        handoff.recover(
            Mock(),
            ContactResult("penetration", 1, Mock()),
            None,
            Mock(),
            lambda: None,
            lambda event: None,
            work=Work(1, 20, 0.35, 2, 6),
            maximum_roots=1,
            minimum_straight_mm=1e-5,
        )
        is None
    )
    assert not classify.called and not recover.called


def test_parent_refines_closed_child_handoff_without_renewing_correction(
    prepared: Prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Resume current rejected geometry with one genuinely remaining parent update and original roots.

    Construction/proof boundaries are doubled; this proves handoff accounting
    and lifecycle, not full physical geometry coverage.
    """
    witness = Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), prepared.source.targets.start)
    crossing = ContactResult("penetration", 3, witness)
    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(side_effect=(None, crossing)))
    prepared.terminal.certify.side_effect = (prepared.evidence, Report("clear", 1))

    def construct(proposal: Proposal, minimum: float, roots: Roots, *args: Any) -> FoldRoute:
        """
        Charge one existing fit while supplying independently authored closed local material.
        """
        assert minimum > 0 and args
        roots.attempted += 1
        return _bump(proposal.window)

    monkeypatch.setitem(vars(runner), "construct", construct)

    def paired(source: FoldRoute, evidence: ContactResult, *args: Any, **kwargs: Any) -> Result:
        """
        Yield one closed actual candidate before charging an unnecessary second child action.
        """
        assert evidence is crossing and args
        assert kwargs["maximum_roots"] == 7 and kwargs["work"].updates == 2
        kwargs["on_event_refinement"](JointHandoff(source, crossing))
        return Result(
            None,
            source,
            crossing,
            source,
            {
                "updates": 1,
                "roots_debited": 2,
                "newton_steps": 0,
                "pairs": 7,
                "contact_checks": 1,
                "contact_seconds": 0.01,
                "status": "unresolved",
                "stop_reason": "event_refinement_handoff",
            },
        )

    child = Mock(side_effect=paired)
    monkeypatch.setitem(vars(runner), "recover_pair", child)
    certificate = ContactResult("separated", 5)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(return_value=certificate))
    records: list[dict[str, Any]] = []
    result = runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        records.append,
        work=Work(3, 31, 0.35, 2, 24),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is certificate and child.call_count == 1
    assert result.detail["iterations"] == 3 and result.detail["roots_attempted"] == 4
    assert result.detail["newton_steps"] == 0 and result.detail["contact_pairs"] == 15
    assert result.detail["paired_material_resumes"] == result.detail["closed_material_resumes"] == 1
    assert any(e.get("action") == "refine_after_closed_paired_handoff" for e in records)


@pytest.mark.parametrize("accepted", [False, True])
def test_initial_pair_trial_is_bounded_and_failure_preserves_fallback(
    prepared: Prepared, monkeypatch: pytest.MonkeyPatch, accepted: bool
) -> None:
    """
    Failed simple correction precedes paired motion inside the original action and Newton pool.

    Failed motion retains the original closed source and actual hardware blocker;
    proof and geometry boundaries are doubled to isolate this protocol.
    """
    crossing = ContactResult(
        "penetration",
        3,
        Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), prepared.source.targets.start),
    )

    def discover(*args: Any, **kwargs: Any) -> ContactResult:
        """
        Charge simulated negative discovery time before computing the child's allowance.
        """
        del args, kwargs
        prepared.clock[0] += 0.02
        return crossing

    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(side_effect=discover))
    certificate = ContactResult("separated", 7)
    failed = reply(prepared.source, False)
    failed.detail.update(newton_steps=6, contacts=0, contact_pairs=0)
    fixed = Mock(return_value=failed)
    monkeypatch.setitem(vars(runner), "continue_fixed", fixed)

    def paired(
        source: FoldRoute,
        observed: ContactResult,
        hardware: Report | None,
        *args: Any,
        **kwargs: Any,
    ) -> Result:
        """
        Report a fully charged bounded initial trial while checking source and clock ownership.
        """
        assert (
            source is prepared.source
            and observed is crossing
            and hardware is prepared.evidence
            and args
        )
        assert fixed.call_count == 1
        left = kwargs["work"]
        assert (left.updates, left.newton_steps, left.pairs, kwargs["maximum_roots"]) == (
            2,
            12,
            28,
            2,
        )
        assert left.cpu_seconds == pytest.approx(0.33) and left.wall_seconds == pytest.approx(1.98)
        return Result(
            source if accepted else None,
            source,
            certificate if accepted else crossing,
            source,
            {
                "updates": 2,
                "roots_debited": 2,
                "newton_steps": 8,
                "pairs": 7,
                "contact_checks": 1,
                "contact_seconds": 0.01,
                "status": "accepted" if accepted else "unresolved",
                "stop_reason": "accepted" if accepted else "allocation_unresolved",
            },
        )

    child = Mock(side_effect=paired)
    monkeypatch.setitem(vars(runner), "recover_pair", child)
    planner = Mock(wraps=runner.plan)
    monkeypatch.setitem(vars(runner), "plan", planner)
    monkeypatch.setitem(vars(runner), "construct", Mock(return_value=None))
    records: list[dict[str, Any]] = []
    result = runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        records.append,
        work=Work(4, 31, 0.35, 2, 24),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and child.call_count == 1
    assert result.detail["roots_attempted"] == 2 and result.detail["newton_steps"] == 14
    assert result.detail["contact_pairs"] == 10 and "initial_paired_trial" in result.detail
    if accepted:
        assert result.contact is certificate and not planner.called
    else:
        assert result.contact is None and result.route is prepared.source
        assert (
            planner.call_args.args[0] is prepared.source
            and planner.call_args.args[1] is prepared.evidence
        )
        fallback = next(
            e for e in records if e.get("action") == "refine_after_bounded_paired_trial"
        )
        assert (
            fallback["remaining_updates"] == 1
            and fallback["remaining_roots"] == 6
            and fallback["source_retained"]
        )


def test_successful_initial_correction_never_spends_paired_roots(
    prepared: Prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve an accepted simpler correction before introducing a second root-family trial.

    Clearance is an explicit boundary double; this checks scheduling and charges.
    """
    crossing = ContactResult(
        "penetration",
        3,
        Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), prepared.source.targets.start),
    )
    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(return_value=crossing))
    fixed = Mock(return_value=reply(prepared.source))
    paired = Mock(side_effect=AssertionError("Accepted initial correction needs no paired roots"))
    monkeypatch.setitem(vars(runner), "continue_fixed", fixed)
    monkeypatch.setitem(vars(runner), "recover_pair", paired)
    result = runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        lambda event: None,
        work=Work(4, 31, 0.35, 2, 24),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is fixed.return_value.contact
    assert fixed.call_count == 1 and not paired.called
    assert result.detail["iterations"] == 1 and result.detail["roots_attempted"] == 0


def test_owned_module_correction_precedes_paired_family_change(
    prepared: Prepared, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Keep the established owned-module correction entry before spending paired branch roots.

    An authored insertion supplies real lineage; contact and correction are boundary doubles.
    """

    def discover(source: FoldRoute, *args: Any, **kwargs: Any) -> ContactResult | None:
        """
        Place the strict blocker inside the actual newly inserted terminal module.
        """
        del args, kwargs
        if source is prepared.source:
            return None
        return ContactResult(
            "penetration",
            3,
            Penetration(
                (len(source.pieces) - 2, len(source.pieces) - 1),
                (0.5, 0, 0),
                (0.5, 0, 0),
                source.targets.start,
            ),
        )

    monkeypatch.setattr(runner.HardwareContacts, "inspect", Mock(side_effect=discover))

    def correct(source: FoldRoute, *args: Any, **kwargs: Any) -> FixedResult:
        """
        Return one charged correction certificate for the actual inserted route.
        """
        assert source is not prepared.source and args and kwargs
        return reply(source)

    fixed = Mock(side_effect=correct)
    paired = Mock(side_effect=AssertionError("Owned module correction has priority"))
    prepared.terminal.certify.side_effect = (Report("clear", 1),)
    monkeypatch.setitem(vars(runner), "inspect_contact", Mock(side_effect=discover))
    monkeypatch.setitem(vars(runner), "continue_fixed", fixed)
    monkeypatch.setitem(vars(runner), "recover_pair", paired)
    result = runner.recover(
        prepared.source,
        prepared.evidence,
        prepared.terminal,
        lambda: None,
        lambda event: None,
        work=Work(2, 31, 0.35, 2, 24),
        maximum_length_mm=100,
        minimum_straight_mm=1e-5,
    )
    assert result is not None and result.contact is not None
    assert fixed.call_count == 1 and not paired.called
    assert result.detail["roots_attempted"] == 4
