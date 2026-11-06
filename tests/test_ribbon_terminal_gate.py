"""
Verify strict opt-in terminal acceptance without changing route initialization.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import gate
from experiments.experiment_ribbon_terminal_hardware.check import Report
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_smoothing_contact import _sequence


def _constructor(first: FoldRoute) -> Mock:
    """
    Retain a complete self-separated first-pass record for acceptance-stage unit checks.
    """
    return Mock(
        return_value=SimpleNamespace(
            route=first,
            contact=ContactResult("separated", 749, reason="first pass geometry"),
            status="separated",
            contacts=1,
            contact_pairs=749,
            contact_seconds=0.0,
            closed_branches=1,
            unattempted_contacts=0,
            rejected=(),
        )
    )


@pytest.mark.parametrize("value", (None, 0, 1, "true"))
def test_terminal_settings_require_an_explicit_boolean(value: Any) -> None:
    """
    Reject implicit hardware consent while preserving disabled historical records.
    """
    with pytest.raises(ValueError, match="explicit boolean"):
        Settings(terminal_hardware=value)
    assert not Settings.parse({"smoothing_percent": 0, "material_uv": False}).terminal_hardware
    assert Settings.parse(asdict(Settings(terminal_hardware=True))).terminal_hardware


def test_cached_clearance_survives_exhaustion_but_never_transfers_to_another_route() -> None:
    """
    Keep an exact safe fallback without granting another immutable object an unmeasured pass.
    """
    route = _route((Straight(10),))
    other = restore(snapshot(route))
    measure = gate.Gate(route.targets, lambda: None, lambda event: None)
    assert measure.permits(route, "construction")
    checks = measure.detail()["checks"]
    measure.cells = 1024
    assert measure.permits(route, "final")
    assert not measure.permits(other, "smoothing")
    assert measure.detail()["checks"] == checks + 1
    assert measure.detail()["outcomes"]["unresolved"] == 1
    assert measure.cells == 1024 and measure.cache_hits == 1


def test_intervening_solver_time_is_not_charged_as_terminal_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Accumulate only work inside measurement calls rather than wall time since gate creation.
    """
    route = _route((Straight(10),))
    clock = [0.0]
    monkeypatch.setitem(vars(gate), "process_time", lambda: clock[0])
    monkeypatch.setitem(vars(gate), "perf_counter", lambda: clock[0])

    def inspect(*args: Any, **kwargs: Any) -> Report:
        """
        Exercise cooperative per-cell timing with a small deterministic measurement cost.
        """
        del args
        clock[0] += 0.02
        kwargs["checkpoint"]()
        return Report("clear", 1)

    monkeypatch.setitem(vars(gate), "inspect", inspect)
    measure = gate.Gate(route.targets, lambda: None, lambda event: None)
    assert measure.permits(route, "construction")
    clock[0] += 100
    assert measure.permits(restore(snapshot(route)), "final")
    assert measure.cpu_seconds == pytest.approx(0.04)
    assert measure.wall_seconds == pytest.approx(0.04)


def test_outer_checkpoint_error_cannot_be_relabelled_as_a_terminal_rejection() -> None:
    """
    Preserve caller source/resource errors even when a route already has cached clearance.
    """
    route = _route((Straight(10),))
    checkpoint = Mock()
    measure = gate.Gate(route.targets, checkpoint, lambda event: None)
    assert measure.permits(route, "construction")
    checkpoint.side_effect = TimeoutError("outer resource stop")
    with pytest.raises(TimeoutError, match="outer resource stop"):
        measure.permits(route, "final")


def test_incomplete_initializer_probe_preserves_final_measurement_and_shared_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Do not cache32cell exhaustion as a final verdict or renew work before the full check.
    """
    route = _route((Straight(10),))
    limits: list[int] = []

    def inspect(*args: Any, **kwargs: Any) -> Report:
        """
        Exhaust only the early probe and independently clear the complete final measurement.
        """
        del args
        limits.append(kwargs["maximum_cells"])
        return Report("unresolved", 32) if limits[-1] == 32 else Report("clear", 7)

    monkeypatch.setitem(vars(gate), "inspect", inspect)
    measure = gate.Gate(route.targets, lambda: None, lambda event: None)
    assert measure.probe(route, "before_contraction").status == "unresolved"
    assert measure.permits(route, "final")
    assert measure.permits(route, "cached_final")
    assert limits == [32, 512]
    assert measure.detail()["cells"] == 39
    assert measure.detail()["checks"] == 2 and measure.cache_hits == 1
    assert measure.detail()["outcomes"] == {"clear": 1, "blocked": 0, "unresolved": 1}


def test_hardware_blocked_smoothing_keeps_first_pass_and_its_contact_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Never apply a smoothed route's certificate to the retained hardware-safe baseline.
    """
    first = _route((Straight(10),))
    changed = replace(first, pieces=(replace(first.pieces[0], geometry=Straight(10.1)),))
    smoothed_contact = ContactResult("separated", 1563, reason="smoothed geometry")
    _sequence(
        monkeypatch,
        {"status": "accepted", "contact": asdict(smoothed_contact), "route": snapshot(changed)},
        changed,
    )
    monkeypatch.setitem(vars(solver_v2), "construct", _constructor(first))
    terminal = Mock(spec=gate.Gate)
    terminal.permits.side_effect = lambda route, stage: route is first
    terminal.detail.return_value = {"enabled": True}
    monkeypatch.setitem(vars(solver_v2), "Gate", Mock(return_value=terminal))
    audit = Mock(side_effect=AssertionError("First pass certificate must be retained"))
    monkeypatch.setitem(vars(solver_v2), "inspect_contact", audit)
    result = solver_v2.solve(
        first.targets, Settings(1, False, False, True), lambda: None, lambda event: None
    )
    assert result.route is first
    assert result.detail["contact_measurement"]["pairs_checked"] == 749
    assert result.detail["final_contact_source"] == "hardware_safe_first_pass"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    audit.assert_not_called()


@pytest.mark.parametrize("final_clear", (False, True))
def test_unresolved_work_geometry_can_finish_before_strict_final_acceptance(
    monkeypatch: pytest.MonkeyPatch,
    final_clear: bool,
) -> None:
    """
    Preserve ordinary initialization while allowing only an independently cleared final route through.
    """
    first = _route((Straight(10),))
    final = restore(snapshot(first))
    contact = ContactResult("separated", 1563, reason="final geometry")
    _sequence(
        monkeypatch,
        {"status": "accepted", "contact": asdict(contact), "route": snapshot(final)},
        final,
    )
    constructor = _constructor(first)
    monkeypatch.setitem(vars(solver_v2), "construct", constructor)
    terminal = Mock(spec=gate.Gate)
    terminal.permits.side_effect = lambda route, stage: route is final and final_clear
    terminal.detail.return_value = {"enabled": True}
    monkeypatch.setitem(vars(solver_v2), "Gate", Mock(return_value=terminal))
    result = solver_v2.solve(
        first.targets, Settings(1, False, False, True), lambda: None, lambda e: None
    )
    assert "terminal" not in constructor.call_args.kwargs
    assert (result.route is final) is final_clear
    assert result.first_pass is first
    assert result.inspection_route is (None if final_clear else final)
    assert result.detail["terminal_hardware"]["final_status"] == (
        "clear" if final_clear else "unresolved"
    )
