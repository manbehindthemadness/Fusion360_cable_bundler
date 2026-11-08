"""
Verify strict length policy and nonrenewing fallback from a failed fixed terminal reversal.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import fold_recovery, recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.straight_quality import StraightQuality
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize(
    "ceiling,updates", ((0, 1), (float("inf"), 1), (True, 1), (2, 0), (2, 5), (2, True))
)
def test_quality_rejects_invalid_or_renewed_work(ceiling: Any, updates: Any) -> None:
    """
    Reject invalid quality bounds and update allocations before geometric work.
    """
    with pytest.raises(ValueError):
        StraightQuality(ceiling, updates)


def test_quality_target_is_inside_original_bound_at_different_scales() -> None:
    """
    Avoid equality-roundoff acceptance without expanding either large or tiny quality ceilings.
    """
    for ceiling in (1e-5, 27.15, 5000):
        policy = StraightQuality(ceiling, 3)
        assert 0 < policy.target_mm < ceiling
        assert ceiling - policy.target_mm <= 1.01e-7
        assert policy.newton_steps == 18


def test_quality_cannot_replace_the_callers_original_ceiling() -> None:
    """
    Reject a mismatched policy before model preparation or terminal measurement.
    """
    source = _route((Straight(10),))
    with pytest.raises(ValueError, match="original quality ceiling"):
        fold_recovery.recover(
            source,
            Report("unresolved", 1),
            Mock(spec=Gate),
            lambda: None,
            lambda e: None,
            maximum_length_mm=10,
            minimum_straight_mm=1e-5,
            remaining_pairs=700,
            maximum_cpu_seconds=0.2,
            maximum_seconds=1,
            quality=StraightQuality(11, 3),
        )


@pytest.mark.parametrize("declined", (False, True))
def test_only_failed_length_gate_uses_original_source_and_remaining_phase(
    monkeypatch: pytest.MonkeyPatch, declined: bool
) -> None:
    """
    Preserve a working fixed reversal, or share only its unused work with constrained joint motion.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), Straight(3), fold(2, 1.2, -1, -0.3, 0)))
    witness = Witness("end", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    terminal = Mock(spec=Gate)
    terminal.measure.side_effect = (Report("blocked", 1, witness), Report("clear", 1))
    model = SimpleNamespace(
        initial=(), straight_indices=(), residual=lambda _: (0.0,) * 6, route=lambda _: source
    )
    monkeypatch.setitem(vars(recovery), "ReversalModel", Mock(return_value=model))
    monkeypatch.setitem(vars(recovery), "decline_initial_length", Mock(return_value=False))
    monkeypatch.setitem(vars(recovery), "close_update", Mock(return_value=((), 2, None)))
    monkeypatch.setitem(vars(recovery), "_same_folds", Mock(return_value=True))
    contact = ContactResult("separated", 13)
    monkeypatch.setitem(vars(recovery), "inspect_contact", Mock(return_value=contact))
    result_detail = {
        "status": "separated",
        "iterations": 1,
        "newton_steps": 3,
        "contacts": 1,
        "contact_pairs": 13,
        "contact_seconds": 0.01,
    }
    direct = Mock(return_value=Result(source, contact, result_detail))
    monkeypatch.setitem(vars(recovery), "recover_fold", direct)
    ceiling = source.material_length_mm + (-0.1 if declined else 0.1)
    result = recovery.recover(
        source,
        terminal,
        lambda: None,
        lambda e: None,
        maximum_length_mm=ceiling,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
    )
    assert result is not None and result.contact is contact
    if declined:
        direct.assert_called_once()
        call = direct.call_args
        assert call.args[0] is source
        assert call.kwargs["quality"] == StraightQuality(ceiling, 3)
        assert call.kwargs["remaining_pairs"] == 700
        assert 0 < call.kwargs["maximum_cpu_seconds"] < 0.2
        assert 0 < call.kwargs["maximum_seconds"] < 1
        assert result.detail["iterations"] == 2
        assert result.detail["newton_steps"] == 5
        assert result.detail["contact_pairs"] == 13
        assert (
            result.detail["fixed_reversal_declined"]["stop_reason"] == "construction_length_ceiling"
        )
    else:
        direct.assert_not_called()
        assert result.detail["status"] == "separated"
