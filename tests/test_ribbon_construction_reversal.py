"""
Keep evidence-selected loop reversal within the original construction action and work allocation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_feature_insertion.contact_recovery import Recovery
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import construction_reversal, recovery_queue
from experiments.experiment_ribbon_locked_solver.recovery_selection import Selection
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import ReturnLength
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def source() -> FoldRoute:
    """
    Author distinct signed bends and occupied terminal travel without replaying a gym layout.
    """
    return _route(
        (
            Straight(5),
            fold(2, 1.2, 1, 0.2, 0),
            Straight(8),
            fold(3, 1.2, -0.8, -0.1, 0),
            Straight(6),
        )
    )


def _measurement() -> ContactResult:
    """
    Supply explicit terminal-return evidence at the mocked physical boundary.
    """
    witness = Penetration((0, 3), (0.5, 0, 0), (0.5, 0, 0), Vector3(0, 0, 0))
    return ContactResult("penetration", 1, witness=witness)


@pytest.mark.parametrize("status", ("separated", "unresolved"))
def test_supported_action_receives_only_remaining_work_and_never_starts_another_strategy(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    A failed reflection is a consumed action, while a success retains its own certificate and counters.
    """
    terminal = Mock(spec=Gate)
    certificate = ContactResult("separated", 17) if status == "separated" else None
    expected = Result(
        source,
        certificate,
        {
            "status": status,
            "iterations": 2,
            "newton_steps": 7,
            "contact_pairs": 17,
            "contacts": 1,
            "contact_seconds": 0.01,
        },
    )
    first = Mock(return_value=expected)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.recover_sequence",
        first,
    )
    times = iter((0.0, 0.01, 0.04, 0.04))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.process_time",
        lambda: next(times),
    )
    events: list[dict[str, Any]] = []
    callback = construction_reversal.before_contact_motion(
        source, _measurement(), terminal, 1e-5, lambda: None, events.append
    )
    assert callback is not None
    result = callback(Work(2, 123, 0.2, 1))
    assert result is not None
    assert result.route is (source if certificate else None) and result.contact is certificate
    assert result.pairs == 17 and result.contacts == 1
    assert result.detail["iterations"] == 2 and result.detail["newton_steps"] == 7
    assert result.detail["cpu_seconds"] == pytest.approx(0.04)
    assert first.call_args.kwargs["work"].updates == 2
    assert first.call_args.kwargs["work"].pairs == 123
    assert first.call_args.kwargs["work"].cpu_seconds == pytest.approx(0.19)
    assert first.call_args.kwargs["maximum_length_mm"] == source.material_length_mm
    assert first.call_args.args[2] is terminal
    assert events[-1]["detail"]["purpose"] == "construction_loop_reversal"


@pytest.mark.parametrize("status", ("separated", "unresolved"))
def test_missing_strict_evidence_or_hardware_keeps_original_contact_strategy(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """
    A missing witness, incomplete certificate or disabled hardware grants no reflected action.
    """
    action = Mock(side_effect=AssertionError("No motion without strict evidence"))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.recover_sequence",
        action,
    )
    assert (
        construction_reversal.before_contact_motion(
            source, ContactResult(status, 1), Mock(spec=Gate), 1e-5, lambda: None, lambda e: None
        )
        is None
    )
    assert (
        construction_reversal.before_contact_motion(
            source, _measurement(), None, 1e-5, lambda: None, lambda e: None
        )
        is None
    )


def test_unsupported_topology_returns_to_ordinary_separation_without_motion(
    source: FoldRoute,
) -> None:
    """
    A bracket ending before the first bend contains no return turn to reverse.
    """
    witness = Penetration((0, 1), (0.5, 0, 0), (0.0, 0, 0), Vector3(0, 0, 0))
    callback = construction_reversal.before_contact_motion(
        source,
        ContactResult("penetration", 1, witness=witness),
        Mock(spec=Gate),
        1e-5,
        lambda: None,
        lambda e: None,
    )
    assert callback is not None and callback(Work(2, 123, 0.2, 1)) is None


def test_return_selects_dominant_bracket_fold_and_retains_reduced_update_allocation(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The greatest occupied return turn changes sign while other signs and radii remain fixed.
    """
    expected = Result(
        source,
        None,
        {
            "status": "unresolved",
            "iterations": 1,
            "newton_steps": 1,
            "contacts": 0,
            "contact_pairs": 0,
            "contact_seconds": 0.0,
            "stop_reason": "joint_no_descent",
        },
    )
    selected = Mock(return_value=expected)
    monkeypatch.setattr(deviation_sequence, "recover_joints", selected)
    gate = Mock(spec=Gate)
    gate.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    gate.measure.return_value = Report("clear", 1)
    callback = construction_reversal.before_contact_motion(
        source, _measurement(), gate, 1e-5, lambda: None, lambda e: None
    )
    assert callback is not None
    result = callback(Work(1, 123, 0.2, 1))
    assert result is not None and result.route is None
    selected.assert_called_once()
    ordinal = selected.call_args.kwargs["mode"].selected_fold
    assert ordinal == 0
    assert selected.call_args.kwargs["mode"].length is ReturnLength.RESTORATION_GOAL
    assert callable(selected.call_args.kwargs["on_blocked"])
    assert selected.call_args.kwargs["maximum_updates"] == 1
    model = IncidentJoints(source, ordinal)
    reflected = model.route(model.initial)
    assert reflected is not None and model.preserves(reflected)
    assert reflected.targets is source.targets
    assert tuple(f.angle_radians for f in model.folds) == (1, -0.8)
    assert model.initial[model.indices.index(1)] < 0


def test_source_failure_propagates_before_any_reversal(source: FoldRoute) -> None:
    """
    Preserve hard source/resource cancellation instead of calling it unsupported geometry.
    """
    checkpoint = Mock(side_effect=RuntimeError("source drift"))
    callback = construction_reversal.before_contact_motion(
        source, _measurement(), Mock(spec=Gate), 1e-5, checkpoint, lambda e: None
    )
    assert callback is not None
    with pytest.raises(RuntimeError, match="source drift"):
        callback(Work(2, 123, 0.2, 1))


def test_failed_reversal_stops_the_construction_queue_without_renewing_recovery(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The scheduler retains a failed action's counters without renewing work on another branch.
    """
    measurement = _measurement()
    branch = Branch((0, 1), source, Mock())
    alternative = Branch((1, 0), source, Mock())
    selection = Selection(
        (branch, measurement), 0.3, 1.9, {"status": "selected"}, ((alternative, measurement),)
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.recovery_queue.select_recovery",
        Mock(return_value=selection),
    )
    failed = Result(
        source,
        None,
        {
            "status": "unresolved",
            "iterations": 2,
            "newton_steps": 7,
            "stop_reason": "closure_no_descent",
            "contact_pairs": 17,
            "contacts": 1,
            "contact_seconds": 0.01,
        },
    )
    child = Mock(return_value=failed)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.recover_sequence", child
    )

    def first_motion(*args: Any, **kwargs: Any) -> Recovery:
        """
        Exercise the actual callback with only the original recovery's remaining allowance.
        """
        replacement = kwargs["before_first_motion"](
            Work(4, args[2], kwargs["maximum_cpu_seconds"], kwargs["maximum_seconds"])
        )
        assert replacement is not None
        return replacement

    attempt = Mock(side_effect=first_motion)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.recovery_queue.recover", attempt
    )
    result = recovery_queue.recover_failed(
        ((branch, measurement), (alternative, measurement)),
        123,
        1e-5,
        lambda: None,
        lambda e: None,
        terminal=Mock(spec=Gate),
    )
    attempt.assert_called_once()
    child.assert_called_once()
    assert result.route is None and result.contact is None
    assert result.pairs == 17 and result.detail["iterations"] == 2
    assert result.detail["stop_reason"] == "closure_no_descent"
    assert result.detail["remaining_pair_budget"] == 106


@pytest.mark.parametrize("reported_cpu", (0.04, 0.21))
def test_late_child_certificate_is_discarded(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    reported_cpu: float,
) -> None:
    """
    Even a child's separated result cannot escape the parent's total clock allowance.
    """
    child = Result(
        source,
        ContactResult("separated", 17),
        {
            "status": "separated",
            "iterations": 2,
            "contact_pairs": 17,
            "contacts": 1,
            "contact_seconds": 0.01,
        },
    )
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.recover_sequence",
        Mock(return_value=child),
    )
    times = iter((0.0, 0.01, reported_cpu, 0.21))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_locked_solver.construction_reversal.process_time",
        lambda: next(times),
    )
    callback = construction_reversal.before_contact_motion(
        source, _measurement(), Mock(spec=Gate), 1e-5, lambda: None, lambda e: None
    )
    assert callback is not None
    result = callback(Work(2, 123, 0.2, 1))
    assert result is not None and result.route is None and result.contact is None
    assert result.pairs == 17 and result.detail["stop_reason"] == "local_budget"
