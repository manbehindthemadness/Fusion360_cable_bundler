"""
Use measured contraction failures without discarding a safe route or replenishing work budgets.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_bend_relocation.solve import Result as Contraction
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch, ImprovementPolicy
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_bounds import Cell, Span
from experiments.experiment_ribbon_fold_route.contact_cap_support import CapPolicy
from experiments.experiment_ribbon_locked_solver import contraction_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from tests.test_ribbon_branch_recovery import _construction
from tests.test_ribbon_flat_contact import load_routes


@pytest.mark.parametrize("outcome", ("improved", "failed", "not_better"))
def test_only_certified_monotonic_improvement_replaces_the_baseline(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """
    Reuse remaining pairs and original time limits while counting even unsuccessful work.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    contact = source.rejected[0][1]
    contraction = Contraction(source.route, None, {}, ((compact.route, contact),))
    corrected = (
        compact.route
        if outcome == "improved"
        else source.route
        if outcome == "not_better"
        else None
    )
    certificate = ContactResult("separated", 245) if corrected else None
    attempt = Mock(return_value=Recovery(corrected, certificate, 245, 1, 0.03, {"iterations": 2}))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    result = contraction_recovery.recover_contracted(
        contraction, frames, 447, 1e-5, lambda: None, lambda event: None
    )
    assert result is not None and result.pairs == 245
    assert attempt.call_args.args[0] is compact.route and attempt.call_args.args[2] == 447
    assert attempt.call_args.kwargs["cap_policy"] is CapPolicy.ANALYTIC_SUPPORT
    assert 0 < attempt.call_args.kwargs["maximum_cpu_seconds"] <= 0.35
    assert 0 < attempt.call_args.kwargs["maximum_seconds"] <= 2
    assert result.detail["accepted_improvement"] is (outcome == "improved")
    assert (result.route is not None) is (outcome == "improved")


@pytest.mark.parametrize("condition", ("unmeasured", "not_shorter", "no_pairs"))
def test_no_speculative_work_without_improvement_evidence_or_unused_pairs(
    monkeypatch: pytest.MonkeyPatch, condition: str
) -> None:
    """
    Skip pair-limit-only evidence, non-improving geometry and exhausted original work.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    route = source.route if condition == "not_shorter" else compact.route
    contact = (
        ContactResult("unresolved", 1024, limit="pairs")
        if condition == "unmeasured"
        else source.rejected[0][1]
    )
    contraction = Contraction(source.route, None, {}, ((route, contact),))
    attempt = Mock(side_effect=AssertionError("No eligible measured correction"))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    result = contraction_recovery.recover_contracted(
        contraction,
        frames,
        0 if condition == "no_pairs" else 447,
        1e-5,
        lambda: None,
        lambda event: None,
    )
    assert result is None
    attempt.assert_not_called()


def test_explicit_cpu_reservation_is_not_replenished(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Subtract preparation from a reduced caller allowance before invoking the strict correction.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    contraction = Contraction(source.route, None, {}, ((compact.route, source.rejected[0][1]),))
    clock = iter((0.0, 0.05, 0.06))
    monkeypatch.setitem(vars(contraction_recovery), "process_time", lambda: next(clock))
    attempt = Mock(return_value=Recovery(None, None, 0, 0, 0, {"iterations": 0}))
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    contraction_recovery.recover_contracted(
        contraction, frames, 610, 1e-5, lambda: None, lambda e: None, maximum_cpu_seconds=0.2
    )
    assert attempt.call_args.kwargs["maximum_cpu_seconds"] == pytest.approx(0.15)


@pytest.mark.parametrize("allowance", (0.0, 0.36, True, float("nan")))
def test_cpu_sublimits_cannot_expand_or_disable_the_original_cap(allowance: Any) -> None:
    """
    Reject malformed or enlarged scheduling allowances before optional work.
    """
    source, frames, _ = _construction()
    assert source.route is not None
    with pytest.raises(ValueError, match="remaining CPU"):
        contraction_recovery.recover_contracted(
            Contraction(source.route, None, {}),
            frames,
            610,
            1e-5,
            lambda: None,
            lambda e: None,
            maximum_cpu_seconds=allowance,
        )


@pytest.mark.parametrize("policy", tuple(ImprovementPolicy))
def test_terminal_length_policy_can_accept_worse_guide_with_a_strict_certificate(
    monkeypatch: pytest.MonkeyPatch, policy: ImprovementPolicy
) -> None:
    """
    Compare against completed baseline geometry before and after correction without replenishing work.
    """
    source, frames, compact = _construction()
    assert source.route is not None
    baseline = Branch.measure((), source.route, frames.guide)
    worse_guide = replace(compact, guide=replace(compact.guide, rms_mm=1e6))
    measurement = Mock(side_effect=[baseline, worse_guide, worse_guide])
    monkeypatch.setattr(Branch, "measure", measurement)
    certificate = ContactResult("separated", 245)
    attempt = Mock(
        return_value=Recovery(compact.route, certificate, 245, 1, 0.03, {"iterations": 2})
    )
    monkeypatch.setitem(vars(contraction_recovery), "recover", attempt)
    contraction = Contraction(source.route, None, {}, ((compact.route, source.rejected[0][1]),))
    result = contraction_recovery.recover_contracted(
        contraction,
        frames,
        447,
        1e-5,
        lambda: None,
        lambda event: None,
        improvement_policy=policy,
    )
    if policy is ImprovementPolicy.MATERIAL_LENGTH:
        assert (
            result is not None and result.route is compact.route and result.contact is certificate
        )
        assert result.pairs == 245 and attempt.call_args.args[2] == 447
        assert measurement.call_count == 3
    else:
        assert result is None
        attempt.assert_not_called()


@pytest.mark.parametrize("proven_contact", (False, True))
def test_proven_contact_preserves_legacy_repair_but_uncertain_contact_can_prioritize_hardware(
    monkeypatch: pytest.MonkeyPatch,
    proven_contact: bool,
) -> None:
    """
    Use evidence certainty rather than case identity, and never renew work after a chosen strategy fails.
    """
    fixture = load_routes()
    baseline, compact_route = fixture["separated"], fixture["incident_source"]
    frames = Frames.create(baseline.targets)
    fold_index = next(
        i for i, p in enumerate(compact_route.pieces) if isinstance(p.geometry, CylindricalFold)
    )
    point = compact_route.pieces[fold_index].pose.origin
    cell = Cell(0, Span(0, 1), Span(-1, 1), Span(-0.1, 0.1))
    measured = (
        ContactResult(
            "penetration", 1, witness=Penetration((0, 1), (0.5, 0, 0), (0.5, 0, 0), point)
        )
        if proven_contact
        else ContactResult(
            "unresolved",
            1,
            unresolved_pieces=(0, 1),
            limit="depth",
            unresolved_regions=(cell, cell),
        )
    )
    contraction = Contraction(baseline, None, {}, ((compact_route, measured),))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report(
        "blocked", 1, Witness("end", fold_index, (0.5, 0, 0), point, (0, 0, 0))
    )
    failure = Recovery(None, None, 12, 1, 0.01, {"iterations": 2})
    legacy, incident = Mock(return_value=failure), Mock(return_value=failure)
    monkeypatch.setitem(vars(contraction_recovery), "recover", legacy)
    monkeypatch.setitem(vars(contraction_recovery), "recover_incident", incident)
    result = contraction_recovery.recover_contracted(
        contraction,
        frames,
        447,
        1e-5,
        lambda: None,
        lambda e: None,
        maximum_cpu_seconds=0.2,
        improvement_policy=ImprovementPolicy.MATERIAL_LENGTH,
        terminal=terminal,
    )
    assert result is not None and result.route is None and result.pairs == 12
    if proven_contact:
        terminal.measure.assert_not_called()
        incident.assert_not_called()
        legacy.assert_called_once()
    else:
        legacy.assert_not_called()
        incident.assert_called_once()
        assert incident.call_args.args[0] is compact_route
        assert 0 < incident.call_args.kwargs["maximum_cpu_seconds"] < 0.2
        assert incident.call_args.kwargs["remaining_pairs"] == 447
