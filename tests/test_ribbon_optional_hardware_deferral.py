"""
Preserve unused recovery work when an optional unsupported crossing has a measured unsafe baseline.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_feature_insertion.contact_recovery import (
    BaselinePolicy,
    Recovery,
)
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import fallback_feasibility, solver_v2
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


@pytest.fixture
def route() -> FoldRoute:
    """
    Author one analytical material route; mocked measurements below test workflow, not physical clearance.
    """
    return _route((Straight(3), fold(2, 1.2, 0.8, 0.1, 1), Straight(4)))


def _crossing(route: FoldRoute) -> ContactResult:
    """
    Supply explicit checker-boundary evidence without executing geometry recovery on a saved layout.
    """
    return ContactResult(
        "penetration", 5, Penetration((0, 2), (0.5, 0, 0), (0.5, 0, 0), route.pieces[0].pose.origin)
    )


def _report(route: FoldRoute, status: str) -> Report:
    """
    Keep actual-witness eligibility distinct from uncertain and malformed mocked reports.
    """
    witness = Witness("end", 0, (0.5, 0, 0), route.pieces[0].pose.origin, (-0.1, 0, 0))
    return Report(
        "blocked" if status == "missing_witness" else status,
        3,
        witness if status == "blocked" else None,
    )


@pytest.mark.parametrize("status", ("blocked", "clear", "unresolved", "missing_witness"))
def test_unsupported_optional_motion_defers_only_for_demonstrated_baseline_intrusion(
    route: FoldRoute, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    """
    Measure the original baseline through the same gate, preserving current action without a strict blocker.
    """
    selected = restore(snapshot(route))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = _report(route, status)
    paired, support = Mock(return_value=None), Mock(return_value=None)
    forbidden = Mock(
        side_effect=AssertionError("Unsupported topology must not start a coupled solve")
    )
    monkeypatch.setitem(vars(fallback_feasibility), "paired_return_fold", paired)
    monkeypatch.setitem(vars(fallback_feasibility), "mating_supported", support)
    monkeypatch.setitem(vars(fallback_feasibility), "recover_mating", forbidden)
    monkeypatch.setitem(vars(fallback_feasibility), "recover_paired_return", forbidden)
    crossing = _crossing(selected)
    prepare = fallback_feasibility.before_optional_motion(
        route, selected, crossing, terminal, 1e-5, lambda: None, Mock()
    )
    assert prepare is not None
    result = prepare(Work(4, 100, 0.35, 2))
    terminal.measure.assert_called_once_with(route, "fallback_feasibility")
    support.assert_called_once()
    assert support.call_args.args[:2] == (selected, crossing)
    forbidden.assert_not_called()
    if status != "blocked":
        assert result is None
        return
    assert result is not None and result.route is None and result.contact is None
    assert result.pairs == result.contacts == result.detail["iterations"] == 0
    assert result.detail["status"] == "deferred"
    assert result.detail["stop_reason"] == "blocked_baseline_before_optional_motion"


@pytest.mark.parametrize("spent", (0.03, 0.36))
def test_preparation_is_deducted_without_consuming_or_renewing_geometry_work(
    route: FoldRoute, monkeypatch: pytest.MonkeyPatch, spent: float
) -> None:
    """
    Carry only genuinely unused CPU and original wall span into the existing solver reservation.
    """
    clock = [0.0]
    for module in (fallback_feasibility, solver_v2):
        for name in ("process_time", "perf_counter"):
            if hasattr(module, name):
                monkeypatch.setitem(vars(module), name, lambda: clock[0])
    monkeypatch.setitem(vars(fallback_feasibility), "paired_return_fold", Mock(return_value=None))
    monkeypatch.setitem(vars(fallback_feasibility), "mating_supported", Mock(return_value=None))
    terminal = Mock(spec=Gate)

    def measure(candidate: FoldRoute, stage: str) -> Report:
        """
        Charge the existing shared measurement and selection to the caller's original clocks.
        """
        assert candidate is route and stage == "fallback_feasibility"
        clock[0] += spent
        return _report(route, "blocked")

    terminal.measure.side_effect = measure
    prepare = fallback_feasibility.before_optional_motion(
        route, route, _crossing(route), terminal, 1e-5, lambda: None, Mock()
    )
    assert prepare is not None
    result = prepare(Work(4, 100, 0.35, 2))
    assert result is not None and result.detail["cpu_seconds"] == pytest.approx(spent)
    assert result.detail["elapsed_seconds"] == pytest.approx(spent)
    assert result.pairs == result.contacts == result.detail["iterations"] == 0
    if spent >= 0.35:
        assert result.detail["status"] == "unresolved"
        assert result.detail["stop_reason"] == "priority_budget"
        assert solver_v2._remaining_recovery(result.detail, 0.0, 4) is None
    else:
        assert solver_v2._remaining_recovery(result.detail, 0.0, 4) == pytest.approx((0.32, 1.97))


@pytest.mark.parametrize("kind", ("disabled", "uncertain", "no_witness"))
def test_absent_hardware_or_contact_evidence_cannot_defer(
    route: FoldRoute, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """
    Do not invent eligibility from an unavailable gate or an incomplete material measurement.
    """
    terminal = Mock(spec=Gate)
    forbidden = Mock(side_effect=AssertionError("No supported material evidence"))
    monkeypatch.setitem(vars(fallback_feasibility), "paired_return_fold", forbidden)
    measurement = (
        ContactResult("unresolved", 1) if kind == "uncertain" else ContactResult("penetration", 1)
    )
    prepare = fallback_feasibility.before_optional_motion(
        route,
        route,
        measurement,
        None if kind == "disabled" else terminal,
        1e-5,
        lambda: None,
        Mock(),
    )
    if prepare is not None:
        assert prepare(Work(4, 100, 0.35, 2)) is None
    else:
        assert kind == "disabled"
    forbidden.assert_not_called()
    terminal.measure.assert_not_called()


@pytest.mark.parametrize("kind", ("paired", "mating"))
def test_supported_first_motion_keeps_its_existing_strategy(
    route: FoldRoute, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """
    Preserve supported coupled restoration, with the exact original gate and remaining work.
    """
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = _report(route, "blocked")
    monkeypatch.setitem(
        vars(fallback_feasibility),
        "paired_return_fold",
        Mock(return_value=0 if kind == "paired" else None),
    )
    monkeypatch.setitem(
        vars(fallback_feasibility),
        "mating_supported",
        Mock(return_value=SimpleNamespace(clipped_straights=True)),
    )
    child = Recovery(route, ContactResult("separated", 7), 7, 1, 0.001, {"iterations": 1})
    action = Mock(return_value=child)
    monkeypatch.setitem(vars(fallback_feasibility), "recover_mating", action)
    monkeypatch.setitem(vars(fallback_feasibility), "recover_paired_return", action)
    prepare = fallback_feasibility.before_optional_motion(
        route, route, _crossing(route), terminal, 1e-5, lambda: None, Mock()
    )
    assert prepare is not None
    result = prepare(Work(4, 100, 0.35, 2))
    assert result is not None and result.route is route and result.pairs == 7
    action.assert_called_once()
    if kind == "mating":
        assert action.call_args.kwargs["baseline_policy"] is BaselinePolicy.RESTORE_BLOCKED
        assert action.call_args.args[3] is terminal
    else:
        assert action.call_args.args[2] is terminal
        assert action.call_args.kwargs["remaining_pairs"] == 100


def test_gate_failure_propagates_instead_of_declining_optional_motion(
    route: FoldRoute, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Preserve cancellation/source/host failures as hard stops before any recovery motion.
    """
    monkeypatch.setitem(vars(fallback_feasibility), "paired_return_fold", Mock(return_value=None))
    monkeypatch.setitem(vars(fallback_feasibility), "mating_supported", Mock(return_value=None))
    terminal = Mock(spec=Gate)
    terminal.measure.side_effect = RuntimeError("source drift")
    prepare = fallback_feasibility.before_optional_motion(
        route, route, _crossing(route), terminal, 1e-5, lambda: None, Mock()
    )
    assert prepare is not None
    with pytest.raises(RuntimeError, match="source drift"):
        prepare(Work(4, 100, 0.35, 2))
