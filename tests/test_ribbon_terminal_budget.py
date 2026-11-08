"""
Keep late reflection work inside its remaining trust travel and preserve strict fallback proof.
"""

from __future__ import annotations

import math
from functools import cached_property
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_fold_relaxation.steps import MAXIMUM_ANGULAR_STEP_RADIANS
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report, Witness, inspect
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.reversal import close_update
from experiments.experiment_ribbon_terminal_hardware.straight_quality import StraightQuality
from tests.test_ribbon_aesthetic import _route


class _LinearCaps(MovableBends):
    """
    Expose independent angular and runway coordinates for an analytical closure contract.
    """

    @cached_property
    def initial(self) -> tuple[float, ...]:
        """
        Start both independent coordinates at zero.
        """
        return (0.0, 0.0)

    @cached_property
    def straight_indices(self) -> tuple[int, ...]:
        """
        Exclude only the actual runway from the angular trust allowance.
        """
        return (1,)

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Keep runway travel nonnegative without adding a runway trust limit.
        """
        return (0.0, math.inf) if index == 1 else (-10.0, 10.0)

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Require four radians in the analytical angular coordinate.
        """
        return (values[0] - 4, 0, 0, 0, 0, 0)

    def jacobian(self, values: tuple[float, ...]) -> list[list[float]]:
        """
        Return the exact derivative of the analytical cap equations.
        """
        return [[1.0, 0.0]] + [[0.0, 0.0] for _ in range(5)]


class _StraightCaps(_LinearCaps):
    """
    Require long straight travel while the angular coordinate is already correct.
    """

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Require four length units in the independent runway coordinate.
        """
        return (values[1] - 4, 0, 0, 0, 0, 0)

    def jacobian(self, values: tuple[float, ...]) -> list[list[float]]:
        """
        Differentiate only the analytical runway equation.
        """
        return [[0.0, 1.0]] + [[0.0, 0.0] for _ in range(5)]


class _CurvedCaps(_LinearCaps):
    """
    Require more than one actual Newton correction despite a small first angular step.
    """

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Retain a nonlinear residual after the first exact linear correction.
        """
        return (math.tan(values[0]) - 0.1, 0, 0, 0, 0, 0)

    def jacobian(self, values: tuple[float, ...]) -> list[list[float]]:
        """
        Return the analytical tangent derivative at the current coordinate.
        """
        return [[1 / math.cos(values[0]) ** 2, 0.0]] + [[0.0, 0.0] for _ in range(5)]


def test_oversized_local_correction_yields_without_applying_another_step() -> None:
    """
    Preserve the current pose when the linear correction exceeds all allocated angular travel.
    """
    model = _LinearCaps(_route((Straight(4),)))
    values, steps, reason = close_update(model, model.initial, lambda: None, remaining_steps=4)
    assert values == model.initial and steps == 0 and reason == "linear_trust_budget"
    for allocation in (None, 24):
        values, steps, reason = close_update(
            model, model.initial, lambda: None, remaining_steps=allocation
        )
        assert steps == 6 and reason is None
        assert values[0] == pytest.approx(6 * MAXIMUM_ANGULAR_STEP_RADIANS)


def test_runway_length_is_not_mistaken_for_angular_travel() -> None:
    """
    A long permitted straight correction may close in one step without an angular budget veto.
    """
    model = _StraightCaps(_route((Straight(4),)))
    values, steps, reason = close_update(model, model.initial, lambda: None, remaining_steps=1)
    assert values == (0.0, 4.0) and steps == 1 and reason is None


def test_remaining_step_count_is_not_renewed_by_a_small_first_motion() -> None:
    """
    Stop a still-unclosed nonlinear frame after its sole permitted Newton correction.
    """
    model = _CurvedCaps(_route((Straight(4),)))
    values, steps, reason = close_update(model, model.initial, lambda: None, remaining_steps=1)
    assert values[0] == pytest.approx(0.1) and steps == 1
    assert reason == "closure_step_budget" and model.residual(values)[0] > 1e-13


@pytest.mark.parametrize("allocation", (0, 25, True, 1.5))
def test_invalid_or_renewed_allocation_is_rejected_before_work(allocation: Any) -> None:
    """
    Require a positive integer subset of the original twenty-four corrections.
    """
    model = _LinearCaps(_route((Straight(4),)))
    checkpoint = Mock(side_effect=AssertionError("No work for an invalid allocation"))
    with pytest.raises(ValueError, match="remaining original Newton"):
        close_update(model, model.initial, checkpoint, remaining_steps=allocation)
    checkpoint.assert_not_called()


@pytest.mark.parametrize("accepted", (False, True))
def test_yield_transfers_only_remaining_work_and_never_inherits_clearance(
    monkeypatch: pytest.MonkeyPatch, accepted: bool
) -> None:
    """
    Use the original signed source and reduced allocation; a failed child grants no certificate.
    """
    source = _route((fold(2, 1.2, 1, 0.2, 0), Straight(3), fold(2, 1.2, -1, -0.3, 0)))
    witness = Witness("end", 1, (0.5, 0, 0), Vector3(0, 0, 0), (-1, 0, 0))
    terminal = Mock(spec=Gate)
    terminal.measure.return_value = Report("blocked", 1, witness)
    model = SimpleNamespace(initial=(), residual=lambda _: (1.0,) * 6, route=lambda _: source)
    monkeypatch.setitem(vars(recovery), "ReversalModel", Mock(return_value=model))
    closed = Mock(return_value=((), 2, "linear_trust_budget"))
    monkeypatch.setitem(vars(recovery), "close_update", closed)
    forbidden = Mock(side_effect=AssertionError("An unclosed reflection has no certificate"))
    monkeypatch.setitem(vars(recovery), "inspect_contact", forbidden)
    contact = ContactResult("separated", 13) if accepted else None
    child = Mock(
        return_value=Result(
            source,
            contact,
            {
                "status": "separated" if accepted else "unresolved",
                "iterations": 1,
                "newton_steps": 3,
                "contacts": int(accepted),
                "contact_pairs": 13 if accepted else 0,
                "contact_seconds": 0.01 if accepted else 0,
            },
        )
    )
    monkeypatch.setitem(vars(recovery), "recover_fold", child)
    ceiling = source.material_length_mm
    result = recovery.recover(
        source,
        terminal,
        lambda: None,
        lambda event: None,
        maximum_length_mm=ceiling,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
    )
    assert result is not None and result.contact is contact
    assert result.detail["status"] == ("separated" if accepted else "unresolved")
    assert result.detail["iterations"] == 2 and result.detail["newton_steps"] == 5
    assert result.detail["contact_pairs"] == (13 if accepted else 0)
    assert closed.call_args.kwargs["remaining_steps"] == 24
    call = child.call_args
    assert call.args[0] is source and call.kwargs["quality"] == StraightQuality(ceiling, 3)
    assert call.kwargs["maximum_updates"] == 3 and call.kwargs["remaining_pairs"] == 700
    assert 0 < call.kwargs["maximum_cpu_seconds"] < 0.2
    assert 0 < call.kwargs["maximum_seconds"] < 1
    forbidden.assert_not_called()


def test_route_recovery_uses_the_existing_joint_fallback_within_original_limits() -> None:
    """
    Clear the actual case78 connector without a new model, root, radius or work allowance.
    """
    scene = Scene(
        Config(1080035090, 3, 0.75, 300, 300),
        Goal.from_degrees(6, 1, 35),
        Goal.from_degrees(8, 8, 20),
    )
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, lambda event: None
    )
    assert result.route is not None
    route = result.route
    detail = result.detail["construction"]["recovery"]
    assert detail["method"] == "constrained_straight_feature"
    assert detail["fixed_reversal_declined"]["stop_reason"] == "linear_trust_budget"
    assert detail["iterations"] == 3 and detail["newton_steps"] == 10
    assert detail["fixed_reversal_declined"]["newton_steps"] == 6
    assert detail["cpu_seconds"] < 0.35 and detail["elapsed_seconds"] < 2
    assert result.detail["construction"]["contact_pairs"] <= 2048
    assert route.material_length_mm <= result.detail["construction"]["raw_length_mm"]
    assert result.detail["contact"] == "separated"
    assert cap_error(route) < 1e-10 and material_error(route) < 1e-10
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    assert inspect(route, hardware).status == "clear"
