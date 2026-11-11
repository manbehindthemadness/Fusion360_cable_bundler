"""
Verify two-terminal motion protection without invented obstruction or clearance evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_feature_insertion.separation import Region
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.active_projection import (
    CoordinateBounds,
    active_step,
)
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    FeatureEvidence,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.incident_model import IncidentJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware, Terminal
from experiments.experiment_ribbon_terminal_hardware.terminal_protection import (
    Protection,
    prepare,
    uncovered,
)
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _source


@dataclass(frozen=True)
class _TwoCoordinates(CoordinateBounds):
    """
    Supply a finite symmetric domain for an authored linear compensation control.
    """

    intervals: tuple[tuple[float, float], ...] = ((-10.0, 10.0),) * 2

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Retain the same finite coordinate domain for both comparison systems.
        """
        return self.intervals[index]


def _two_folds(scale: float, sign: float, lead: float) -> FoldRoute:
    """
    Author two signed terminal folds and one occupied interior span at independently scaled fixed caps.
    """
    source = _route(
        (
            *((Straight(lead * scale),) if lead else ()),
            fold(2 * scale, 1.2 * scale, sign * 0.8, 0.2, scale),
            Straight(6 * scale),
            fold(2 * scale, 1.2 * scale, -sign * 0.7, -0.2, scale),
            *((Straight(lead * scale),) if lead else ()),
        )
    )
    return replace(source, targets=replace(source.targets, diameter_mm=scale), radius_mm=scale)


@pytest.mark.parametrize("scale", (0.2, 1.0, 20.0))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
@pytest.mark.parametrize("lead", (0.0, 2.0))
def test_both_terminal_neighborhoods_have_full_material_source_gap_protection(
    scale: float, sign: float, lead: float
) -> None:
    """
    Preserve real initial gaps for both bend signs/scales, excluding mating and absent straight material.
    """
    source = _two_folds(scale, sign, lead)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    guards = prepare(model, hardware, [], lambda: None)
    assert len(guards) == 4
    assert {guard.plane.box.terminal for guard in guards} == set(Terminal)
    expected = {
        (Terminal.START, Region(0, False)),
        (Terminal.START, Region(1, True)),
        (Terminal.END, Region(1, False)),
        (Terminal.END, Region(1, True)),
    }
    assert {(guard.plane.box.terminal, guard.plane.reference) for guard in guards} == expected
    for guard in guards:
        assert guard.plane.model is model and guard.plane.members == (guard.plane.reference,)
        gap = guard.plane.gap(model.initial)
        assert guard.minimum_gap == min(gap, 1e-7 / model.scale)
        assert guard.residual(model.initial) <= 0
    assert model.original is source


def test_actual_observed_members_take_precedence_and_zero_material_is_not_invented() -> None:
    """
    Reuse actual member coverage, including the same bend at different fixed terminals independently.
    """
    source = _source()
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    guards = prepare(model, hardware, [], lambda: None)
    assert len(guards) == 2
    first = next(guard for guard in guards if guard.plane.box.terminal is Terminal.START)
    remaining = prepare(model, hardware, [first.plane], lambda: None)
    assert len(remaining) == 1 and remaining[0].plane.box.terminal is Terminal.END
    assert uncovered(guards, [first.plane]) == remaining
    assert uncovered(guards, []) == guards
    straight = _route((Straight(10),))
    assert (
        prepare(
            SignedJoints(straight),
            Hardware.create(straight.targets, Dimensions.scaled(straight.targets)),
            [],
            lambda: None,
        )
        == ()
    )


@pytest.mark.parametrize("selected", (0, 1))
def test_reflected_initial_pose_cannot_redefine_original_terminal_protection(selected: int) -> None:
    """
    Keep original source gap families and margins when one incident bend starts already reversed.
    """
    source = _two_folds(1, 1, 2)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    ordinary = prepare(SignedJoints(source), hardware, [], lambda: None)
    reflected = IncidentJoints(source, selected)
    protections = prepare(reflected, hardware, [], lambda: None)
    baseline = tuple(reflected.full.initial[index] for index in reflected.indices)
    assert baseline != reflected.initial
    assert len(protections) == len(ordinary)
    for actual, expected in zip(protections, ordinary):
        assert (
            actual.plane.reference,
            actual.plane.box,
            actual.plane.family,
            actual.plane.side,
        ) == (
            expected.plane.reference,
            expected.plane.box,
            expected.plane.family,
            expected.plane.side,
        )
        assert actual.minimum_gap == expected.minimum_gap
        assert actual.residual(baseline) <= 0


def test_gap_protection_cannot_be_substituted_for_a_clearance_report() -> None:
    """
    Retain an overlapping enclosure as non-worsening motion guidance without asserting physical validity.
    """
    source = _source()
    hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, hardware)
    assert report.status == "blocked" and report.witness is not None
    model = SignedJoints(source)
    guards = prepare(model, hardware, [], lambda: None)
    assert all(guard.residual(model.initial) <= 0 for guard in guards)
    assert all(not hasattr(guard, "status") and not hasattr(guard, "witness") for guard in guards)
    overlapping = Mock(spec=FeaturePlane)
    overlapping.gap.return_value = -0.2
    assert Protection(overlapping, -0.2).residual(model.initial) == 0.0


@pytest.mark.parametrize("angle,allowed_touch", ((pi / 2, True), (pi, False)))
def test_only_complete_mating_cap_certificate_can_retain_a_nonpositive_enclosure(
    angle: float, allowed_touch: bool
) -> None:
    """
    Keep certified quarter-turn mating touch, but restore uncertified full-fold enclosure overlap.
    """
    source = _route((fold(2, 1.2, angle, 0, 1),))
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    protections = prepare(model, hardware, [], lambda: None)
    assert len(protections) == 2
    for protection in protections:
        original_gap = protection.plane.gap(model.initial)
        if allowed_touch:
            assert protection.minimum_gap == min(original_gap, 1e-7 / model.scale)
            assert protection.residual(model.initial) <= 0
        else:
            assert original_gap < 0
            assert protection.minimum_gap == 1e-7 / model.scale
            assert protection.residual(model.initial) > 0


def test_satisfied_opposite_terminal_inequality_changes_the_same_linear_correction() -> None:
    """
    One authored two-coordinate compensation system must repair one side without worsening the other.
    """
    plane = Mock(spec=FeaturePlane)
    plane.gap.side_effect = lambda values: values[1] - values[0]
    guard = Protection(plane, 0.0)
    model = _TwoCoordinates()
    caps = [[0.0, 0.0] for _ in range(6)]
    ordinary = active_step(
        model, (0.0, 0.0), caps + [[-1.0, 0.0]], (0.0,) * 6 + (1.0,), lambda: None
    )
    protected = active_step(
        model,
        (0.0, 0.0),
        caps + [[-1.0, 0.0], [1.0, -1.0]],
        (0.0,) * 6 + (1.0, guard.residual((0.0, 0.0))),
        lambda: None,
    )
    assert ordinary is not None and protected is not None
    assert guard.residual(ordinary) > 0
    assert guard.residual(protected) <= 1e-14 and protected[0] >= 1 - 1e-14


def test_protection_preparation_retains_hard_cancellation_and_fixed_targets() -> None:
    """
    Neither different hardware inputs nor caller cancellation can become optional successful guidance.
    """
    source = _two_folds(1, 1, 2)
    model = SignedJoints(source)
    hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    with pytest.raises(InterruptedError, match="source cancellation"):
        prepare(model, hardware, [], Mock(side_effect=InterruptedError("source cancellation")))
    other = _two_folds(2, 1, 2)
    with pytest.raises(ValueError, match="same fixed"):
        prepare(
            model,
            Hardware.create(other.targets, Dimensions.scaled(other.targets)),
            [],
            lambda: None,
        )


def test_preparation_exhaustion_consumes_original_work_without_any_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Stop locally before geometry or certificates when simultaneous protection preparation exhausts work.
    """
    source = _source()
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, terminal.hardware)
    monkeypatch.setitem(
        vars(joint_contact),
        "prepare_terminal_protection",
        Mock(side_effect=joint_contact._Exhausted()),
    )
    result = joint_contact.recover(
        source,
        report,
        terminal,
        lambda: None,
        lambda _: None,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=ContactGuidance((FeatureEvidence(source, report),)),
    )
    assert result is not None and result.contact is None and result.route is source
    assert result.detail["stop_reason"] == "phase_budget"
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
    terminal.certify.assert_not_called()
