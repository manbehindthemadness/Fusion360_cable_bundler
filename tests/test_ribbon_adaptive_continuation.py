"""
Check residual correction entry and contracts on authored material, without saved-layout replay.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Literal
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import (
    adaptive_event_continuation as continuation,
)
from experiments.experiment_ribbon_terminal_hardware import deviation_sequence
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import Window
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
)
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from tests.test_ribbon_adaptive_events import _bump, _source


def moved(source: FoldRoute, amount: float = 0.001) -> FoldRoute:
    """
    Use actual fixed-topology equations to move an authored hairpin while opposite terminal slots compensate.
    """
    model = StraightSlots(source)
    values = list(model.initial)
    values[0] += amount / model.scale
    values[-1] += amount / model.scale
    route = model.route(tuple(values))
    assert route is not None and cap_error(route) < 1e-10 and material_error(route) < 1e-10
    return route


def reply(route: FoldRoute, accepted: bool = True) -> Result:
    """
    Supply explicit checker/solver boundary accounting, not physical clearance evidence.
    """
    return Result(
        route,
        ContactResult("separated", 7) if accepted else None,
        {
            "iterations": 1,
            "newton_steps": 2,
            "contacts": 1,
            "contact_pairs": 7,
            "contact_seconds": 0.001,
            "cpu_seconds": 0.01,
            "elapsed_seconds": 0.02,
            "status": "separated" if accepted else "unresolved",
            "stop_reason": "accepted" if accepted else "projection_failed",
        },
    )


@pytest.fixture
def system() -> tuple[FoldRoute, Report, Mock]:
    """
    Author nine folds while preserving the real occupied hardware member and its original target poses.
    """
    source, hardware, evidence = _source()
    window = Window(source, len(source.pieces) - 1, len(source.pieces))
    source = window.splice(_bump(window))
    gate = Mock(spec=Gate, hardware=hardware)
    gate.measure.return_value = evidence
    gate.certify.return_value = Report("clear", 1)
    return source, evidence, gate


def run(
    system: tuple[FoldRoute, Report, Mock],
    *,
    checkpoint: Callable[[], None] | None = None,
    record: Callable[[dict[str, Any]], None] | None = None,
    work: Work | None = None,
) -> Result:
    """
    Invoke only the continuation boundary under a small genuinely remaining allocation.
    """
    source, evidence, gate = system
    return continuation.recover(
        source,
        evidence,
        gate,
        checkpoint or (lambda: None),
        record or Mock(),
        work=work or Work(2, 23, 0.35, 2, 23),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )


def test_real_fixed_topology_motion_keeps_caps_and_material_beyond_six_events(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Validate actual affine cap compensation; final clearance is explicitly a boundary double.
    """
    source, evidence, gate = system
    changed = moved(source)
    child = Mock(return_value=reply(changed))
    monkeypatch.setitem(vars(continuation), "recover_sequence", child)
    result = run(system)
    assert result.route is changed and result.contact is not None
    assert child.call_args.args[1] is evidence and len(source.pieces) != len(changed.pieces)
    assert result.route.material_length_mm > source.material_length_mm
    assert 0 < child.call_args.kwargs["work"].cpu_seconds < 0.35
    gate.certify.assert_called_once_with(changed, "adaptive_continuation_final")


@pytest.mark.parametrize(
    "field,value",
    (
        ("iterations", True),
        ("iterations", 3),
        ("newton_steps", 24),
        ("newton_steps", 7),
        ("contact_pairs", 24),
        ("contacts", -1),
        ("contacts", True),
        ("contact_seconds", float("nan")),
        ("cpu_seconds", -1),
        ("elapsed_seconds", float("inf")),
    ),
)
def test_child_cannot_hide_or_enlarge_completed_work(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    """
    Reject overspend, undersized logical update counts, booleans and malformed clocks before acceptance.
    """
    child = reply(moved(system[0]))
    child.detail[field] = value
    monkeypatch.setitem(vars(continuation), "recover_sequence", Mock(return_value=child))
    with pytest.raises(ArithmeticError):
        run(system)


@pytest.mark.parametrize("violation", ("target", "radius", "events", "native_floor", "incomplete"))
def test_child_certificate_cannot_override_fixed_geometry_contracts(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
    violation: str,
) -> None:
    """
    A nominal solver success cannot waive target identity, bend topology, native slots or complete contact proof.
    """
    source = system[0]
    changed = moved(source, 1e-6 if violation == "native_floor" else 0.001)
    if violation == "target":
        changed = replace(changed, targets=replace(changed.targets, name="another target owner"))
    elif violation == "radius":
        changed = replace(changed, radius_mm=changed.radius_mm + 0.1)
    elif violation == "events":
        changed = replace(changed, pieces=changed.pieces[2:])
    child = reply(changed)
    if violation == "incomplete":
        child = replace(child, contact=ContactResult("separated", 7, limit="pairs"))
    monkeypatch.setitem(vars(continuation), "recover_sequence", Mock(return_value=child))
    with pytest.raises(ArithmeticError, match="contract"):
        run(system)


def test_expired_preparation_cannot_start_or_renew_the_child(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Receipt/source-guard overhead belongs to the original residual allocation.
    """
    clock = [0.0]
    monkeypatch.setitem(vars(continuation), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(continuation), "perf_counter", lambda: clock[0])
    child = Mock(side_effect=AssertionError("No remaining preparation allowance"))
    monkeypatch.setitem(vars(continuation), "recover_sequence", child)

    def record(event: dict[str, Any]) -> None:
        """
        Model receipt work consuming the remaining phase before any child stage.
        """
        del event
        clock[0] = 0.36

    result = run(system, record=record)
    assert result.contact is None and result.detail["stop_reason"] == "preparation_exhausted"
    assert result.detail["iterations"] == result.detail["newton_steps"] == 0
    child.assert_not_called()


@pytest.mark.parametrize("hardware_status", ("blocked", "unresolved"))
def test_contact_success_still_requires_current_hardware_clearance(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
    hardware_status: Literal["blocked", "unresolved"],
) -> None:
    """
    A child contact certificate cannot stand in for the independent final route-bound hardware check.
    """
    source, _, gate = system
    gate.certify.return_value = Report(hardware_status, 1)
    monkeypatch.setitem(
        vars(continuation), "recover_sequence", Mock(return_value=reply(moved(source)))
    )
    result = run(system)
    assert result.contact is None and result.route is source
    assert (
        result.detail["stop_reason"] == "final_hardware_not_clear"
        and result.detail["contact_pairs"] == 7
    )


def test_source_failure_remains_a_hard_stop_before_child_work(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Caller cancellation/source errors propagate without becoming an unsupported fallback or renewed action.
    """
    child = Mock(side_effect=AssertionError("No child after a hard source failure"))
    monkeypatch.setitem(vars(continuation), "recover_sequence", child)
    with pytest.raises(RuntimeError, match="source"):
        run(system, checkpoint=Mock(side_effect=RuntimeError("source changed")))
    child.assert_not_called()


def test_hardware_only_sequence_entry_keeps_zero_corrections_without_fake_contact(
    system: tuple[FoldRoute, Report, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise the actual sequence entry and guidance selection with a declined explicit joint boundary.
    """
    source, evidence, gate = system
    stage = Mock(return_value=None)
    monkeypatch.setitem(vars(deviation_sequence), "recover_joints", stage)
    result = deviation_sequence.recover(
        source,
        evidence,
        gate,
        lambda: None,
        Mock(),
        work=Work(1, 23, 0.35, 2, 0),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )
    assert result.route is source and result.contact is None and result.detail["iterations"] == 1
    mode = stage.call_args.kwargs["mode"]
    assert isinstance(mode, ContactGuidance) and mode.motion is ContactMotion.ADAPTIVE_HARDWARE
    assert mode.evidence[0].route is source and stage.call_args.args[1] is evidence
    assert stage.call_args.kwargs["maximum_newton_steps"] == 0


def test_real_joint_entry_cannot_move_when_original_corrections_are_exhausted(
    system: tuple[FoldRoute, Report, Mock],
) -> None:
    """
    Run actual witness preparation and joint equations with zero corrections on authored nine-fold material.
    """
    source, evidence, gate = system
    records: list[dict[str, Any]] = []
    result = deviation_sequence.recover(
        source,
        evidence,
        gate,
        lambda: None,
        records.append,
        work=Work(1, 23, 0.35, 2, 0),
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
    )
    assert result.route is source and result.contact is None and result.detail["newton_steps"] == 0
    assert result.detail["stop_reason"] == "joint_update_limit"
    assert result.detail["motion_attempted"] is False
    assert result.detail["hardware_preparation_only"] is True
    assert any(
        e.get("stage") == "joint_flat_contact" and e.get("status") == "started" for e in records
    )


@pytest.mark.parametrize(
    "report", (Report("clear", 1), Report("unresolved", 1), Report("blocked", 1))
)
def test_hardware_entry_cannot_invent_a_strict_witness(
    system: tuple[FoldRoute, Report, Mock],
    report: Report,
) -> None:
    """
    Reject uncertainty or unwitnessed labels before a new joint strategy can start.
    """
    source, _, gate = system
    with pytest.raises(ValueError, match="occupied witness"):
        deviation_sequence.recover(
            source,
            report,
            gate,
            lambda: None,
            Mock(),
            work=Work(1, 23, 0.35, 2),
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
        )
    gate.measure.assert_not_called()
