"""
Retain new material crossings during cap restoration without treating negative screens as clearance.
"""

from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_fold_route.contact import ContactResult, Penetration, ProbeResult
from experiments.experiment_ribbon_fold_route.contact_flat_probe import FlatProbe
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import MaterialGuidance
from experiments.experiment_ribbon_terminal_hardware.restoration_screen import screen
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_material_return import _witness


def _crossing() -> FoldRoute:
    """
    Author a three-quarter-turn route whose last straight crosses its leading straight.
    """
    route = _route(
        (
            Straight(10),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(5),
            fold(2, 1.2, math.pi / 2, 0, 0),
            Straight(10),
        )
    )
    return replace(route, targets=replace(route.targets, end=Vector3(99, 99, 99)))


def test_strict_crossing_is_observed_while_caps_remain_open() -> None:
    """
    Detect actual occupied material on an independently authored route without an endpoint solve.
    """
    route = _crossing()
    retained: list[Penetration] = []
    result = screen(
        route, FlatProbe(), 32, lambda: None, lambda observed: retained.append(observed) is None
    )
    witness = result.witness
    assert result.status == "penetration"
    assert witness is not None
    assert witness is retained[0]
    assert retained[0].pieces == (0, 6) and result.pairs_checked <= 32
    assert route.pieces[-1].end_pose().origin != route.targets.end


@pytest.mark.parametrize("allowance", (0, 1, 6, 32))
def test_miss_or_already_retained_crossing_never_grants_clearance(allowance: int) -> None:
    """
    Respect pair bounds while declining already represented evidence without a positive certificate.
    """
    result = screen(_crossing(), FlatProbe(), allowance, lambda: None, lambda witness: False)
    assert result.status == "unresolved" and result.witness is None
    assert 0 <= result.pairs_checked <= allowance


def test_support_budget_is_not_reset_and_source_cancellation_propagates() -> None:
    """
    Keep the original shared support ceiling and stop rather than silently retrying work.
    """
    probe = FlatProbe(supports=2048)
    result = screen(_crossing(), probe, 32, lambda: None, lambda witness: True)
    assert result.status == "unresolved" and result.pairs_checked == 0 and probe.supports == 2048
    with pytest.raises(TimeoutError, match="original stop"):
        screen(
            _crossing(),
            FlatProbe(),
            32,
            Mock(side_effect=TimeoutError("original stop")),
            lambda witness: True,
        )


@pytest.mark.parametrize("malformed", ("count", "identity", "point"))
def test_optional_probe_cannot_invent_work_or_a_material_witness(malformed: str) -> None:
    """
    Recheck callback work, ordered identity and actual strict occupancy before retaining evidence.
    """
    route = _crossing()
    witness = Penetration(
        (0, 1) if malformed == "identity" else (0, 2),
        (0.5, 0.0, 0.0),
        (0.5, 0.0, 0.0),
        Vector3(99, 99, 99),
    )
    probe: Any = Mock(
        supports=0, return_value=ProbeResult(99 if malformed == "count" else 0, witness=witness)
    )
    with pytest.raises(ArithmeticError):
        screen(route, probe, 32, lambda: None, lambda item: True)


@pytest.mark.parametrize("outcome", ("witness", "interrupted", "budget"))
def test_screening_precedes_cap_closure_and_preserves_original_work_accounting(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    """
    Use real joint geometry/constraint construction with controlled projection and measurement boundaries.
    """
    source = _crossing()
    terminal = _gate(source)
    projection_calls = 0

    def projection(
        model: Any, values: tuple[float, ...], *args: Any, **kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Permit one geometric update, then decline within the existing linear allowance.
        """
        nonlocal projection_calls
        del model, args, kwargs
        projection_calls += 1
        limit = 10 if outcome == "budget" else 1
        return (
            tuple(0.01 if i == 0 else 0.0 for i in range(len(values)))
            if projection_calls <= limit
            else None
        )

    evaluation = SimpleNamespace(
        equations=lambda values: (math.exp(-values[0]),) + (0.0,) * 6,
        admissible=lambda values: True,
        constraints_changed=Mock(),
    )
    monkeypatch.setitem(vars(joint_contact), "JointEvaluation", Mock(return_value=evaluation))
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projection)
    monkeypatch.setitem(
        vars(joint_contact),
        "joint_jacobian",
        lambda model, values, *args, **kwargs: [[0.0] * len(values) for _ in range(7)],
    )

    def negative(
        route: FoldRoute,
        probe: FlatProbe,
        maximum_pairs: int,
        checkpoint: Callable[[], None],
        retain: Callable[[Penetration], bool],
        **_options: Any,
    ) -> ContactResult:
        """
        Present a new measured pair at the screen boundary; standalone controls verify strict occupancy.
        """
        del probe
        checkpoint()
        assert maximum_pairs <= 32 and route.targets == source.targets
        if outcome == "interrupted":
            raise vars(joint_contact)["_Exhausted"]()
        if outcome == "budget":
            return ContactResult("unresolved", maximum_pairs)
        witness = _witness(0, 4, 0.5, 0.5)
        assert retain(witness)
        return ContactResult("penetration", 7, witness=witness)

    monkeypatch.setitem(vars(joint_contact), "screen_restoration", negative)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        _witness(0, 6, 0.5, 0.5),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=512,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=MaterialGuidance(0),
    )
    assert result is not None and result.detail["status"] == "unresolved"
    assert result.detail["newton_steps"] == (10 if outcome == "budget" else 1)
    assert result.detail["flat_constraints"] == (2 if outcome == "witness" else 1)
    assert result.detail["restoration_screen_checks"] == (8 if outcome == "budget" else 1)
    expected_pairs = 7 if outcome == "witness" else 32 if outcome == "interrupted" else 256
    assert (
        result.detail["restoration_screen_pairs"]
        == result.detail["contact_pairs"]
        == expected_pairs
    )
    assert result.detail["contacts"] == 0 and result.contact is None
    assert any(e["status"] == "constraint_added" for e in events) == (outcome == "witness")
    terminal.certify.assert_not_called()
