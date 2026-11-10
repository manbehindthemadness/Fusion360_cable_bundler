"""
Select actual blocked terminal bends early without renewing work or changing unrelated material turns.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import recovery, terminal_turn
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import IncidentGuidance
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def source() -> FoldRoute:
    """
    Construct analytical ordered folds with distinct radii and existing travel; no gym replay.
    """
    return _route(
        (
            Straight(3),
            fold(2, 1.2, 0.7, 0.2, 0),
            Straight(5),
            fold(3, 1.2, -0.9, -0.3, 0),
            fold(4, 1.2, 0.8, 0.1, 0),
            Straight(4),
        )
    )


def _evidence(terminal: str, piece: int) -> Report:
    """
    Supply explicit intrusion evidence at the mocked terminal measurement boundary.
    """
    return Report(
        "blocked", 1, Witness(terminal, piece, (0.5, 0, 0), Vector3(0, 0, 0), (-0.1, 0, 0))
    )


@pytest.mark.parametrize("terminal,piece,ordinal", (("start", 1, 0), ("end", 3, 1), ("end", 4, 2)))
def test_measured_fold_selects_only_its_own_reversal_with_remaining_allowances(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
    piece: int,
    ordinal: int,
) -> None:
    """
    Include internal and terminal folds without a terminal-index guess or new budget.
    """
    evidence = _evidence(terminal, piece)
    gate = Mock(spec=Gate)
    result = Result(
        source,
        None,
        {
            "status": "unresolved",
            "iterations": 2,
            "newton_steps": 8,
            "contacts": 0,
            "contact_pairs": 0,
            "contact_seconds": 0.0,
        },
    )
    action = Mock(return_value=result)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.terminal_turn.recover_joints", action
    )
    times = iter((0.0, 0.01, 0.08))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.terminal_turn.process_time",
        lambda: next(times),
    )
    events: list[dict[str, Any]] = []
    answer = terminal_turn.recover(
        source,
        evidence,
        gate,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
        maximum_updates=2,
    )
    assert answer is not None and answer.contact is None and answer.route is source
    assert answer.detail["newton_steps"] == 8 and answer.detail["cpu_seconds"] == pytest.approx(
        0.08
    )
    action.assert_called_once()
    options = action.call_args.kwargs
    assert options["maximum_updates"] == 2 and options["remaining_pairs"] == 123
    assert options["maximum_length_mm"] == source.material_length_mm
    assert options["maximum_cpu_seconds"] == pytest.approx(0.19)
    guidance = options["mode"]
    assert isinstance(guidance, IncidentGuidance) and guidance.selected_fold == ordinal
    assert guidance.evidence[0].route is source and guidance.evidence[0].report is evidence
    model = IncidentJoints(source, guidance.selected_fold)
    reflected = model.route(model.initial)
    assert reflected is not None and model.preserves(reflected)
    assert reflected.targets is source.targets
    assert events[0]["status"] == "selected" and events[0]["selected_fold"] == ordinal


@pytest.mark.parametrize(
    "evidence", (Report("clear", 1), Report("unresolved", 512), Report("blocked", 1))
)
def test_missing_strict_witness_does_not_start_reversal(
    source: FoldRoute, evidence: Report
) -> None:
    """
    No guessed bend follows an absent witness or incomplete measurement.
    """
    assert (
        terminal_turn.recover(
            source,
            evidence,
            Mock(spec=Gate),
            lambda: None,
            lambda e: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=100,
            maximum_cpu_seconds=0.2,
            maximum_seconds=1,
            maximum_updates=2,
        )
        is None
    )


def test_failed_terminal_reversal_does_not_start_signed_or_radius_recovery(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The failed chosen action retains its source and counters without another strategy allowance.
    """
    gate = Mock(spec=Gate)
    gate.measure.return_value = _evidence("end", 3)
    failure = Result(source, None, {"status": "unresolved", "stop_reason": "joint_no_descent"})
    action = Mock(return_value=failure)
    forbidden = Mock(side_effect=AssertionError("No second strategy after attempted reversal"))
    monkeypatch.setattr(recovery, "reverse_terminal_fold", action)
    monkeypatch.setattr(recovery, "recover_fold", forbidden)
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.recovery.continue_after_boundary",
        forbidden,
    )
    answer = recovery.recover(
        source,
        gate,
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
        maximum_updates=2,
    )
    assert answer is failure and answer.contact is None
    action.assert_called_once()
    assert action.call_args.kwargs["maximum_updates"] == 2
    forbidden.assert_not_called()


def test_final_child_overrun_discards_its_certificate(
    source: FoldRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preparation and completion overhead cannot turn an over-budget child into accepted output.
    """
    result = Result(source, ContactResult("separated", 1), {"status": "separated"})
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.terminal_turn.recover_joints",
        Mock(return_value=result),
    )
    times = iter((0.0, 0.01, 0.21))
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.terminal_turn.process_time",
        lambda: next(times),
    )
    answer = terminal_turn.recover(
        source,
        _evidence("end", 3),
        Mock(spec=Gate),
        lambda: None,
        lambda e: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
        maximum_updates=2,
    )
    assert answer is not None and answer.route is source and answer.contact is None
    assert (
        answer.detail["status"] == "unresolved" and answer.detail["stop_reason"] == "phase_budget"
    )


def test_hard_source_error_propagates_before_joint_action(source: FoldRoute) -> None:
    """
    Source/cancellation failures cannot become unsupported evidence or a routine geometry stall.
    """
    checkpoint = Mock(side_effect=RuntimeError("source drift"))
    with pytest.raises(RuntimeError, match="source drift"):
        terminal_turn.recover(
            source,
            _evidence("end", 3),
            Mock(spec=Gate),
            checkpoint,
            lambda e: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=100,
            maximum_cpu_seconds=0.2,
            maximum_seconds=1,
            maximum_updates=2,
        )


def test_unsupported_reflected_features_remain_a_recorded_unsuccessful_action(
    source: FoldRoute,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Missing constraint support after selection cannot disappear from recovery accounting.
    """
    monkeypatch.setattr(
        "experiments.experiment_ribbon_terminal_hardware.terminal_turn.recover_joints",
        Mock(return_value=None),
    )
    events: list[dict[str, Any]] = []
    result = terminal_turn.recover(
        source,
        _evidence("end", 3),
        Mock(spec=Gate),
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=100,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
        maximum_updates=2,
    )
    assert result is not None and result.route is source and result.contact is None
    assert result.detail["stop_reason"] == "unsupported_reflected_features"
    assert result.detail["iterations"] == result.detail["newton_steps"] == 0
    assert [event["status"] for event in events] == ["selected", "unresolved"]
