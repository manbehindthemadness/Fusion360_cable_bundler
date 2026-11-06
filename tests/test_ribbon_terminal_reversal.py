"""
Verify one evidence-selected reversal, complete frame residuals and bounded fallback behavior.
"""

from __future__ import annotations

import math
from typing import Any, Literal
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_route.geometry import Pose, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import reversal
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.reversal_model import (
    ReversalModel,
    frame_rotation,
    incident_fold,
)
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_terminal_gate import _constructor


@pytest.mark.parametrize(
    ("tangent", "width"),
    (
        (Vector3(1, 0, 0), Vector3(0, -1, 0)),
        (Vector3(-1, 0, 0), Vector3(0, 1, 0)),
        (Vector3(-1, 0, 0), Vector3(0, -1, 0)),
    ),
)
def test_half_turn_has_pi_residual_instead_of_false_closure(
    tangent: Vector3, width: Vector3
) -> None:
    """
    Detect each ordered-frame reversal and retain zero for the identical rigid frame.
    """
    target = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    actual = Pose(target.origin, tangent, width)
    assert math.sqrt(sum(v * v for v in frame_rotation(actual, target))) == pytest.approx(math.pi)
    assert frame_rotation(target, target) == (0, 0, 0)


@pytest.mark.parametrize(
    ("terminal", "piece", "expected"),
    (("end", 2, 1), ("start", 2, 0), ("end", 1, 0), ("end", 5, None)),
)
def test_collision_selects_its_incident_fold_without_terminal_index_search(
    terminal: str, piece: int, expected: int | None
) -> None:
    """
    Use material incidence for a straight return and keep a witnessed fold's own identity.
    """
    route = _route(
        (
            Straight(4),
            fold(1, 1.2, 1, 0.2, 0),
            Straight(3),
            fold(2, 1.2, -1, -0.3, 0),
            fold(3, 1.2, 0.5, 0, 0),
            Straight(2),
        )
    )
    witness = Witness(terminal, piece, (0.5, 0, 0), Vector3(0, 0, 0), (0, 0, 0))
    assert incident_fold(route, witness) == expected


def test_reflection_fixes_one_bank_and_all_radii_but_frees_missing_runways() -> None:
    """
    Preserve the selected event and other signs while allowing joint relocation on either side.
    """
    route = _route((fold(2, 1.2, 1, 0.2, 0), fold(3, 1.2, -1, -0.3, 0)))
    model = ReversalModel(route, 0)
    full = model.expanded(model.initial)
    assert full[1] == -model.full.initial[1]
    assert full[2:4] == model.full.initial[2:4]
    assert full[7] == model.full.initial[7]
    second_angle = model.indices.index(5)
    assert model.bounds(second_angle) == (-math.pi, 0)
    first_runway = model.straight_indices[0]
    assert model.initial[first_runway] == 0
    values = list(model.initial)
    values[first_runway] = 0.1
    assert isinstance(model.pieces(tuple(values))[0].geometry, Straight)
    with pytest.raises(ValueError, match="existing fold"):
        ReversalModel(route, 2)


@pytest.mark.parametrize("status", ("clear", "unresolved"))
def test_no_speculative_reversal_without_a_demonstrated_intrusion(
    status: Literal["clear", "unresolved"],
) -> None:
    """
    Leave ordinary contraction eligible when measurements give no supported direction.
    """
    route = _route((Straight(4), fold(2, 1.2, 1, 0, 0)))
    terminal = Mock(spec=Gate)
    terminal.probe.return_value = Report(status, 1)
    assert (
        reversal.correct(
            route,
            terminal,
            lambda: None,
            lambda e: None,
            minimum_straight_mm=1e-5,
            maximum_seconds=2,
        )
        is None
    )


def test_failed_coupled_closure_retains_baseline_and_never_inherits_a_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep an unsuccessful reflection diagnostic and propagate outer cancellation distinctly.
    """
    route = _route((Straight(4), fold(2, 1.2, 1, 0.2, 0)))
    witness = Witness("end", 0, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    terminal = Mock(spec=Gate)
    terminal.probe.return_value = Report("blocked", 1, witness)
    monkeypatch.setitem(vars(reversal), "projected", Mock(return_value=None))
    contact = Mock(side_effect=AssertionError("Unclosed proposal cannot be certified"))
    monkeypatch.setitem(vars(reversal), "inspect_contact", contact)
    events: list[dict[str, Any]] = []
    result = reversal.correct(
        route, terminal, lambda: None, events.append, minimum_straight_mm=1e-5, maximum_seconds=2
    )
    assert result is not None and result.route is route and result.contact is None
    assert result.detail["stop_reason"] == "linear_closure_infeasible"
    assert events[-1]["candidate"] is not None
    contact.assert_not_called()
    with pytest.raises(TimeoutError, match="outer cancellation"):
        reversal.correct(
            route,
            terminal,
            Mock(side_effect=TimeoutError("outer cancellation")),
            events.append,
            minimum_straight_mm=1e-5,
            maximum_seconds=2,
        )


def test_terminal_reversal_substitutes_for_contraction_instead_of_adding_a_second_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve normal smoothing and fallback acceptance after a failed bounded terminal action.
    """
    first = _route((Straight(10),))
    constructor = _constructor(first)
    monkeypatch.setitem(vars(solver_v2), "construct", constructor)
    correction = Mock(
        return_value=Result(
            first, None, {"status": "baseline_retained", "method": "witness_incident_fold_reversal"}
        )
    )
    monkeypatch.setitem(vars(solver_v2), "correct_terminal", correction)
    contract = Mock(side_effect=AssertionError("No renewed contraction allowance"))
    monkeypatch.setitem(vars(solver_v2), "contract", contract)
    result = solver_v2.solve(
        first.targets, Settings(0, False, True, True), lambda: None, lambda e: None
    )
    assert result.route is first
    assert result.detail["contraction"]["method"] == "witness_incident_fold_reversal"
    assert correction.call_args.kwargs["maximum_seconds"] <= 2
    contract.assert_not_called()
