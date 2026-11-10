"""
Verify evidence-driven hardware scheduling without replaying saved layouts or changing work limits.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.runner import restore, snapshot
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_terminal_gate import _constructor


@pytest.mark.parametrize("evidence", ("blocked", "unresolved", "missing_witness"))
@pytest.mark.parametrize("repaired", (False, True))
@pytest.mark.parametrize("fallback_clear", (False, True))
@pytest.mark.parametrize("work_state", ("available", "unselected", "consulted", "exhausted"))
@pytest.mark.parametrize("cached", (False, True))
def test_actual_blocker_prioritizes_one_repair_and_keeps_remaining_fallback(
    monkeypatch: pytest.MonkeyPatch,
    evidence: str,
    repaired: bool,
    fallback_clear: bool,
    work_state: str,
    cached: bool,
) -> None:
    """
    Spend the same late-recovery allocation before another proof only for demonstrated intrusion.

    Mock only workflow boundaries; certificates here test provenance and ordering,
    not physical geometry acceptance. Ordinary unresolved baselines keep their
    existing fallback priority, and a failed repair can still use its own fallback.
    """
    original = _route((Straight(10),))
    consulted, exhausted = work_state == "consulted", work_state == "exhausted"
    contracted, smoothed, corrected = (restore(snapshot(original)) for _ in range(3))
    calls: list[str] = []
    terminal = Mock(spec=Gate)
    terminal.cached_clearance.return_value = Report("clear", 4) if cached else None
    witness = Witness("start", 0, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0))
    terminal.certify.return_value = Report(
        "unresolved" if evidence == "unresolved" else "blocked",
        24,
        witness if evidence == "blocked" else None,
    )

    def permits(route: FoldRoute, stage: str) -> bool:
        """
        Retain route-bound fallback evidence without claiming clearance for the changed candidates.
        """
        calls.append(stage)
        return route is original and stage == "construction_fallback" and (cached or fallback_clear)

    def recover(*args: Any, **options: Any) -> Result:
        """
        Preserve the caller's original remaining limits and return one explicit mocked disposition.
        """
        assert args[0] is contracted and args[1] is terminal
        assert 0 < options["maximum_cpu_seconds"] <= 0.35
        assert 0 < options["maximum_seconds"] <= 2
        assert options["maximum_updates"] == 4
        assert options["remaining_pairs"] == 2048 - 749
        calls.append("recovery")
        return Result(
            corrected,
            ContactResult("separated", 17) if repaired else None,
            {
                "status": "separated" if repaired else "unresolved",
                "contacts": 1,
                "contact_pairs": 17,
                "contact_seconds": 0.01,
                "elapsed_seconds": 0.02,
                "cpu_seconds": 0.02,
                "iterations": 1,
            },
        )

    terminal.permits.side_effect = permits
    terminal.detail.return_value = {"enabled": True}

    def select_contraction(*_args: Any, **options: Any) -> None:
        """
        Distinguish no selected strategy from a strategy entered but returning no replacement.
        """
        options["consultation"].entered = consulted

    replacements = {
        "Gate": Mock(return_value=terminal),
        "construct": _constructor(original),
        "guide_parameters": Mock(return_value=(0.5,)),
        "correct_terminal": Mock(return_value=None),
        "contract": Mock(
            return_value=Result(
                contracted,
                ContactResult("separated", 7),
                {"status": "shortened"},
                ((contracted, ContactResult("unresolved", 1)),)
                if work_state in ("consulted", "unselected")
                else (),
            )
        ),
        "smooth_with_contact": Mock(
            return_value=SimpleNamespace(route=smoothed, contact=None, stages={})
        ),
        "recover_terminal": Mock(side_effect=recover),
        "recover_contracted": Mock(side_effect=select_contraction),
    }
    for name, replacement in replacements.items():
        monkeypatch.setitem(vars(solver_v2), name, replacement)
    if exhausted:
        monkeypatch.setitem(vars(solver_v2), "_remaining_recovery", Mock(return_value=None))
        monkeypatch.setitem(vars(solver_v2), "remaining_completed", Mock(return_value=None))
    outcome = solver_v2.solve(
        original.targets, Settings(0, False, True, True), lambda: None, lambda event: None
    )
    priority = evidence == "blocked" and not consulted and not cached
    fallback_clear = fallback_clear or cached
    if consulted or exhausted:
        assert "recovery" not in calls
        assert outcome.route is (original if fallback_clear else None)
    elif priority:
        assert "recovery" in calls
        if repaired:
            assert "construction_fallback" not in calls and outcome.route is corrected
        else:
            assert calls.index("recovery") < calls.index("construction_fallback")
            assert outcome.route is (original if fallback_clear else None)
    else:
        assert "construction_fallback" in calls
        if fallback_clear:
            assert "recovery" not in calls and outcome.route is original
        else:
            assert calls.index("construction_fallback") < calls.index("recovery")
            assert outcome.route is (corrected if repaired else None)
    assert calls.count("construction_fallback") <= 1


def test_cached_clearance_keeps_exact_identity_and_hard_cancellation() -> None:
    """
    A free certificate lookup never transfers proof or measures again after shared work is exhausted.
    """
    original = _route((Straight(10),))
    equivalent = restore(snapshot(original))
    checkpoint = Mock()
    terminal = Gate(original.targets, checkpoint, lambda event: None)
    assert terminal.cached_clearance(original) is None
    certified = terminal.certify(original, "analytical")
    assert certified.status == "clear"
    checks = terminal.detail()["checks"]
    terminal.cells = 1024
    assert terminal.cached_clearance(original) is certified
    assert terminal.cached_clearance(equivalent) is None
    assert terminal.detail()["checks"] == checks and terminal.cells == 1024
    checkpoint.side_effect = TimeoutError("cached source stop")
    with pytest.raises(TimeoutError, match="cached source stop"):
        terminal.cached_clearance(original)
