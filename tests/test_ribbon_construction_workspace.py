"""
Select closed local travel from real occupied material without saved-layout or outcome lookup.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration
from experiments.experiment_ribbon_fold_route.contact_core import core_witness
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import construction_reversal
from experiments.experiment_ribbon_locked_solver.construction_workspace import closed_return
from experiments.experiment_ribbon_terminal_hardware.adaptive_event_window import events
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.recovery_limits import Work
from tests.test_ribbon_aesthetic import _route


def _return(leading: float, gap: float, outer: bool = True) -> tuple[FoldRoute, Penetration]:
    """
    Author a genuine straight-core return crossing with an optional unrelated outer bend.
    """
    geometries = (
        Straight(leading),
        fold(1, 1.2, math.pi, 0, 0),
        Straight(gap),
        fold(1, 1.2, math.pi, 0, 0),
        Straight(20),
    )
    if outer:
        geometries += (fold(1, 1.2, -0.2, 0.1, 1), Straight(3))
    source = _route(geometries)
    witness = core_witness(source, 0, 4)
    assert witness is not None
    return source, witness


@pytest.mark.parametrize(("leading", "gap"), ((8.0, 1.0), (10.0, 2.0), (12.0, 3.0)))
def test_contained_return_uses_closed_straight_workspace_and_leaves_outer_bend(
    leading: float, gap: float
) -> None:
    """
    Keep both occupied members and their complete local boundary contract in one selected interval.
    """
    source, witness = _return(leading, gap)
    window = closed_return(source, witness)
    assert window is not None and window.source is source
    assert (window.begin, window.end) == (0, 5)
    assert all(window.begin <= member < window.end for member in witness.pieces)
    assert events(window.route) == 2 and events(source) == 3
    assert window.route.targets.start == source.targets.start
    assert window.route.targets.end == source.pieces[4].end_pose().origin
    spliced = window.splice(window.route)
    assert all(a is b for a, b in zip(source.pieces[5:], spliced.pieces[5:]))


def test_whole_route_rewrite_and_open_caps_keep_existing_reversal() -> None:
    """
    Do not call a global rewrite local or transfer an unclosed boundary contract.
    """
    source, witness = _return(10, 1, outer=False)
    assert closed_return(source, witness) is None
    source, witness = _return(10, 1)
    source = replace(source, targets=replace(source.targets, end=Vector3(99, 99, 99)))
    assert closed_return(source, witness) is None


def test_nonlocal_crossing_does_not_rewrite_only_one_of_the_colliders() -> None:
    """
    A true crossing spanning three turns keeps reversal when the selected local window omits a member.
    """
    source = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(10),
            fold(2, 1.2, 0.2, 0.1, 1),
            Straight(3),
        )
    )
    witness = core_witness(source, 0, 6)
    assert witness is not None and closed_return(source, witness) is None


@pytest.mark.parametrize("accepted", (False, True))
def test_first_motion_chooses_one_adaptive_action_under_original_remaining_work(
    monkeypatch: pytest.MonkeyPatch, accepted: bool
) -> None:
    """
    A supported local rewrite replaces reversal; a failed action cannot allocate another strategy.
    """
    source, witness = _return(10, 1)
    certificate = ContactResult("separated", 17) if accepted else None
    result = Result(
        source,
        certificate,
        {
            "status": "separated" if accepted else "unresolved",
            "iterations": 2,
            "newton_steps": 6,
            "contact_pairs": 17,
            "contacts": 1,
            "contact_seconds": 0.01,
        },
    )
    adaptive = Mock(return_value=result)
    reversal = Mock(side_effect=AssertionError("No reversal after adaptive selection"))
    monkeypatch.setattr(construction_reversal, "recover_adaptive", adaptive)
    monkeypatch.setattr(construction_reversal, "recover_sequence", reversal)
    times = iter((0.0, 0.01, 0.04, 0.04))
    monkeypatch.setitem(vars(construction_reversal), "process_time", lambda: next(times))
    recorded: list[dict[str, Any]] = []
    callback = construction_reversal.before_contact_motion(
        source,
        ContactResult("penetration", 1, witness=witness),
        Mock(spec=Gate),
        1e-5,
        lambda: None,
        recorded.append,
    )
    assert callback is not None
    disposition = callback(Work(2, 123, 0.2, 1, 12))
    assert disposition is not None
    assert disposition.route is (source if accepted else None)
    assert disposition.contact is certificate
    assert disposition.detail["purpose"] == "construction_local_deviation"
    assert disposition.detail["iterations"] == 2 and disposition.detail["newton_steps"] == 6
    left = adaptive.call_args.kwargs["work"]
    assert left.updates == 2 and left.pairs == 123 and left.newton_steps == 12
    assert left.cpu_seconds == pytest.approx(0.19)
    assert adaptive.call_count == 1
    reversal.assert_not_called()
    assert recorded[0]["strategy"] == "construction_local_deviation"


def test_source_cancellation_precedes_strategy_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the original hard stop without running either geometric technique.
    """
    source, witness = _return(10, 1)
    adaptive, reversal = Mock(), Mock()
    monkeypatch.setattr(construction_reversal, "recover_adaptive", adaptive)
    monkeypatch.setattr(construction_reversal, "recover_sequence", reversal)
    callback = construction_reversal.before_contact_motion(
        source,
        ContactResult("penetration", 1, witness=witness),
        Mock(spec=Gate),
        1e-5,
        Mock(side_effect=InterruptedError("source stop")),
        Mock(),
    )
    assert callback is not None
    with pytest.raises(InterruptedError, match="source stop"):
        callback(Work(2, 123, 0.2, 1))
    adaptive.assert_not_called()
    reversal.assert_not_called()
