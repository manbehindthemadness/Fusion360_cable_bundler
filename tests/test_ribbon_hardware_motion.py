"""
Verify a bounded hardware-domain expansion on analytical material, without saved-layout replay.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_terminal_hardware import hardware_motion, joint_contact
from experiments.experiment_ribbon_terminal_hardware.check import Report, inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.run_translation import StraightSlots
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import Protection
from tests.test_ribbon_contact_refinement import _source


def _adaptive_case() -> tuple[FoldRoute, Mock, Report, ContactGuidance]:
    """
    Bind a closed analytical hairpin and its actual intrusion report to one adaptive correction.
    """
    source = _source(0.2)
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    evidence = inspect(source, terminal.hardware)
    assert evidence.status == "blocked" and evidence.witness is not None
    mode = ContactGuidance((FeatureEvidence(source, evidence),), ContactMotion.ADAPTIVE_HARDWARE)
    return source, terminal, evidence, mode


@pytest.mark.parametrize("straight_policy", ("infeasible", "unchanged", "growing", "shortening"))
@pytest.mark.parametrize("exhausted", (False, True))
def test_initial_straight_infeasibility_or_excess_growth_expands_without_renewal(
    monkeypatch: pytest.MonkeyPatch,
    straight_policy: str,
    exhausted: bool,
) -> None:
    """
    Exercise real model/equation/derivative rebinding while mocking only projection dispositions.

    Unchanged and shortening projections retain the original straight domain. An
    infeasible or unnecessarily growing one enables angular preparation before any motion, with the original clock
    and immutable source. Hard exhaustion forbids the new domain. Neither
    mocked projector is physical evidence or complete-ribbon coverage.
    """
    source, terminal, evidence, mode = _adaptive_case()
    clock = [0.0]
    for name in ("process_time", "perf_counter"):
        monkeypatch.setitem(vars(joint_contact), name, lambda: clock[0])
    models: list[SignedJoints] = []
    protected_models: list[SignedJoints] = []
    prepare = joint_contact.prepare_terminal_protection

    def protect(
        model: SignedJoints,
        hardware: Hardware,
        observed: list[joint_contact.FeaturePlane],
        checkpoint: Callable[[], None],
    ) -> tuple[Protection, ...]:
        """
        Observe real simultaneous protection binding before each model's first correction.
        """
        protected_models.append(model)
        guards = prepare(model, hardware, observed, checkpoint)
        assert guards and all(guard.plane.model is model for guard in guards)
        return guards

    monkeypatch.setitem(vars(joint_contact), "prepare_terminal_protection", protect)

    def straight(
        model: SignedJoints, values: tuple[float, ...], *_args: Any, **kwargs: Any
    ) -> tuple[float, ...] | None:
        """
        Supply one linear disposition and simulate time spent in the original preparation.
        """
        assert isinstance(model, StraightSlots)
        assert isinstance(kwargs["evidence"], joint_contact.RunwayEvidence)
        models.append(model)
        clock[0] = 0.2 if exhausted else 0.01
        if straight_policy == "infeasible":
            return None
        direction = (
            0.01
            if straight_policy == "growing"
            else -0.01
            if straight_policy == "shortening"
            else 0.0
        )
        return (direction,) * len(values)

    def angular(
        model: SignedJoints,
        values: tuple[float, ...],
        rows: list[list[float]],
        terms: tuple[float, ...],
        *_args: Any,
        **_kwargs: Any,
    ) -> None:
        """
        Inspect the actual larger domain and derivatives, then decline without moving geometry.
        """
        assert not isinstance(model, StraightSlots) and model.original is source
        assert len(values) > len(models[0].initial) and model.admissible(values)
        assert len(rows) == len(terms) and all(len(row) == len(values) for row in rows)
        assert model.preserves(source)
        rebuilt = model.route(values)
        assert rebuilt is not None and cap_error(rebuilt) < 1e-7
        assert clock[0] == 0.01
        models.append(model)

    monkeypatch.setitem(vars(joint_contact), "shortest_run_step", straight)
    projected = Mock(side_effect=angular)
    monkeypatch.setitem(vars(joint_contact), "redistributed_step", projected)
    events: list[dict[str, Any]] = []
    result = joint_contact.recover(
        source,
        evidence,
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.2,
        maximum_seconds=1,
        maximum_updates=1,
        mode=mode,
    )
    assert result is not None and result.route is source and result.contact is None
    expanded = straight_policy in ("infeasible", "growing") and not exhausted
    assert result.detail["hardware_domain_expanded"] is expanded
    assert projected.call_count == int(expanded)
    if expanded:
        assert (
            projected.call_args.kwargs["guidance_policy"]
            is joint_contact.GuidancePolicy.RESTORATION_MERIT
        )
        assert (
            projected.call_args.kwargs["linear_policy"]
            is joint_contact.LinearPolicy.COUPLED_RESTORATION
        )
    assert protected_models == models
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
    assert result.detail["motion_attempted"] is (
        not exhausted and straight_policy in ("unchanged", "shortening")
    )
    assert result.detail["stop_reason"] == (
        "phase_budget"
        if exhausted
        else "joint_no_descent"
        if straight_policy in ("unchanged", "shortening")
        else "linear_projection_infeasible"
    )
    assert sum(e["status"] == "hardware_motion_expanded" for e in events) == int(expanded)
    if expanded:
        assert next(e for e in events if e["status"] == "hardware_motion_expanded")["reason"] == (
            "straight_growth_beyond_goal"
            if straight_policy == "growing"
            else "linear_projection_infeasible"
        )
    growth = [e for e in events if e["status"] == "hardware_straight_growth_declined"]
    assert not growth


@pytest.mark.parametrize("bank", (-0.3, 0.0, 0.4))
@pytest.mark.parametrize(
    "growth_mm,slack_mm,expected",
    (
        (0, 0, False),
        (-0.1, 0, False),
        (0.1, 0, True),
        (0.1, 0.2, False),
        (0.1, -1, True),
        (1e-8, 0, False),
    ),
)
def test_affine_straight_growth_selects_mobility_without_testing_geometry(
    bank: float, growth_mm: float, slack_mm: float, expected: bool
) -> None:
    """
    Match fixed-bend affine length against real authored material while retaining useful length slack.
    """
    source = _source(bank)
    model = StraightSlots(source)
    delta = (growth_mm / model.scale,) + (0.0,) * (len(model.initial) - 1)
    proposed = model.route(tuple(a + b for a, b in zip(model.initial, delta)))
    assert proposed is not None
    assert proposed.material_length_mm == pytest.approx(source.material_length_mm + growth_mm)
    assert (
        hardware_motion.straight_growth_requires_angles(
            model, delta, source.material_length_mm + slack_mm
        )
        is expected
    )


def test_growth_policy_requires_fixed_bends_and_complete_finite_projection() -> None:
    """
    Reject unsupported algebra instead of interpreting missing or angular motion as straight growth.
    """
    source = _source()
    model = StraightSlots(source)
    for delta, goal in (
        ((), source.material_length_mm),
        ((float("nan"),) * len(model.initial), source.material_length_mm),
        ((0.0,) * len(model.initial), float("inf")),
    ):
        with pytest.raises(ValueError):
            hardware_motion.straight_growth_requires_angles(model, delta, goal)
    angular = SignedJoints(source)
    with pytest.raises(ValueError):
        hardware_motion.straight_growth_requires_angles(
            angular, (0.0,) * len(angular.initial), source.material_length_mm
        )


def test_adaptive_policy_never_turns_unknown_contact_into_hardware_only_evidence() -> None:
    """
    Material uncertainty must retain its own complete constraint instead of silently dropping it.
    """
    source = _source()
    with pytest.raises(ValueError, match="hardware-only or separated"):
        joint_contact.recover(
            source,
            ContactResult("unresolved", 3, limit="pairs"),
            Mock(spec=Gate),
            lambda: None,
            lambda event: None,
            maximum_length_mm=source.material_length_mm,
            minimum_straight_mm=1e-5,
            remaining_pairs=123,
            maximum_cpu_seconds=0.2,
            maximum_seconds=1,
            maximum_updates=1,
            mode=ContactGuidance(motion=ContactMotion.ADAPTIVE_HARDWARE),
        )


def test_expansion_requires_actual_features_and_closed_material() -> None:
    """
    Missing guidance declines; off-target geometry or hard cancellation cannot create a new domain.
    """
    source = _source()
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    mode = ContactGuidance(motion=ContactMotion.ADAPTIVE_HARDWARE)
    assert hardware_motion.expand(source, mode, hardware, lambda: None) is None
    opened = replace(source, targets=replace(source.targets, end=Vector3(100, 0, 0)))
    with pytest.raises(ArithmeticError, match="closed material"):
        hardware_motion.expand(opened, mode, hardware, lambda: None)
    with pytest.raises(RuntimeError, match="source stop"):
        hardware_motion.expand(
            source, mode, hardware, Mock(side_effect=RuntimeError("source stop"))
        )
