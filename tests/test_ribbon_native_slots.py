"""
Keep necessary straight activation native-valid within one existing replacement projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from typing import Any, Callable
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware import joint_contact
from experiments.experiment_ribbon_terminal_hardware.active_projection import (
    CoordinateBounds,
    active_step,
)
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.feature_guidance import (
    ContactGuidance,
    ContactMotion,
    FeatureEvidence,
    MaterialGuidance,
)
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.native_slots import NativeSlots, bind
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_contact_refinement import _gate
from tests.test_ribbon_material_return import _witness


@dataclass(frozen=True)
class _Bounds(CoordinateBounds):
    """
    Supply fixed finite linear-control bounds without external geometry or certificates.
    """

    intervals: tuple[tuple[float, float], ...] = ((0.0, 10.0), (-10.0, 10.0), (0.0, 10.0))

    def bounds(self, index: int) -> tuple[float, float]:
        """
        Return one unchanged analytical coordinate interval.
        """
        return self.intervals[index]


@pytest.mark.parametrize("scale", (1e-6, 1.0, 1e6))
@pytest.mark.parametrize("epsilon_mm", (1e-7, 4e-6))
def test_valid_positive_face_preserves_caps_when_zeroing_the_necessary_slot_cannot(
    scale: float, epsilon_mm: float
) -> None:
    """
    The same two-coordinate cap/clearance system admits a native-sized slot but not an exact zero slot.
    """
    source = _Bounds(((0.0, 100.0), (-100.0, 100.0)))
    rows = [[1.0, -1.0]] + [[0.0, 0.0] for _ in range(5)] + [[-1.0, 0.0]]
    residual = (0.0,) * 6 + (epsilon_mm / scale,)
    first = active_step(source, (0.0, 0.0), rows, residual, lambda: None)
    assert first is not None and 0 < first[0] * scale <= 1e-5
    frozen_rows = [[0.0, row[1]] for row in rows]
    assert active_step(source, (0.0, 0.0), frozen_rows, residual, lambda: None) is None
    domain = bind(source, frozenset({0}), first, 1e-5, scale)
    assert domain is not None and domain.minimum * scale > 1e-5
    corrected = active_step(domain, (0.0, 0.0), rows, residual, lambda: None)
    assert corrected is not None and corrected[0] * scale > 1e-5
    assert abs(corrected[0] - corrected[1]) < 1e-14
    assert residual[-1] - corrected[0] <= 1e-14


def test_slot_faces_preserve_other_coordinates_and_decline_impossible_native_floor() -> None:
    """
    Freeze zero/outward slots, activate positive ones, and retain every original upper bound.
    """
    source = _Bounds()
    domain = bind(source, frozenset({0, 2}), (1e-8, 1.0, -1e-12), 1e-5, 1.0)
    assert domain is not None and domain.positive == frozenset({0})
    assert domain.frozen == frozenset({2})
    assert domain.bounds(0) == (domain.minimum, 10.0)
    assert domain.bounds(1) == source.bounds(1)
    assert domain.bounds(2) == (0.0, 0.0)
    tiny = _Bounds(((0.0, 1e-8),))
    assert bind(tiny, frozenset({0}), (1e-9,), 1e-5, 1.0) is None


@pytest.mark.parametrize(
    "minimum,scale", ((0.0, 1.0), (-1.0, 1.0), (1e-5, 0.0), (float("inf"), 1.0))
)
def test_malformed_native_dimensions_cannot_create_a_motion_domain(
    minimum: float, scale: float
) -> None:
    """
    Reject invalid dimensions before selecting any coordinate face.
    """
    with pytest.raises(ValueError, match="finite positive"):
        bind(_Bounds(), frozenset({0}), (1e-8,), minimum, scale)


@pytest.mark.parametrize("positive", (False, True))
def test_existing_second_projection_activates_positive_slivers_and_freezes_zero_directions(
    monkeypatch: pytest.MonkeyPatch, positive: bool
) -> None:
    """
    Exercise actual joint preparation/derivatives and exactly two linear calls, without a geometry step.
    """
    source = _route((fold(2, 1.2, 1, 0, 1), Straight(2), fold(2, 1.2, -1, 0, 1)))
    terminal = _gate(source)
    calls: list[CoordinateBounds] = []
    events: list[dict[str, Any]] = []

    def project(
        model: CoordinateBounds,
        values: tuple[float, ...],
        rows: list[list[float]],
        _terms: tuple[float, ...],
        _checkpoint: Callable[[], None],
        **_kwargs: Any,
    ) -> tuple[float, ...] | None:
        """
        Supply the first tiny direction, then inspect and decline the one replacement projection.
        """
        calls.append(model)
        if len(calls) == 1:
            assert isinstance(model, SignedJoints) and values[0] == 0.0
            return tuple(
                5e-6 / model.scale if index == 0 and positive else 0.0
                for index in range(len(values))
            )
        assert len(calls) == 2
        if positive:
            assert isinstance(model, NativeSlots) and model.positive == frozenset({0})
            first_model = calls[0]
            assert isinstance(first_model, SignedJoints)
            assert model.minimum * first_model.scale > 1e-5
            assert any(row[0] != 0 for row in rows[:6])
        else:
            assert model is calls[0] and all(row[0] == 0 for row in rows)
        return None

    monkeypatch.setitem(vars(joint_contact), "redistributed_step", project)
    result = joint_contact.recover(
        source,
        _witness(0, 2, 0.5, 0.5),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=source.material_length_mm,
        minimum_straight_mm=1e-5,
        remaining_pairs=123,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
        maximum_updates=4,
        mode=MaterialGuidance(0),
    )
    assert result is not None and result.route is source and result.contact is None
    assert len(calls) == 2 and result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
    assert result.detail["native_positive_slot_projections"] == int(positive)
    assert result.detail["stop_reason"] == "native_projection_infeasible"
    assert sum(event["status"] == "native_positive_slot_projection" for event in events) == int(
        positive
    )
    terminal.certify.assert_not_called()


def test_fixed_bend_cleanup_uses_one_native_feasibility_projection_without_restarting_minimization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain initial runway minimization, then use its one replacement pass to satisfy native bounds.
    """
    source = _route((fold(2, 1.2, pi, 0.2, 1), Straight(3)))
    terminal = _gate(source)
    terminal.hardware = Hardware.create(source.targets, Dimensions(10, 10, 10))
    report = inspect(source, terminal.hardware)
    assert report.status == "blocked" and report.witness is not None
    first_model: list[SignedJoints] = []

    def first(
        model: SignedJoints, values: tuple[float, ...], *_args: Any, **_kwargs: Any
    ) -> tuple[float, ...]:
        """
        Retain one original minimizer call while supplying its tiny positive leading-slot direction.
        """
        first_model.append(model)
        assert values[0] == 0.0
        return tuple(5e-6 / model.scale if index == 0 else 0.0 for index in range(len(values)))

    second = Mock(return_value=None)
    minimum = Mock(side_effect=first)
    monkeypatch.setitem(vars(joint_contact), "shortest_run_step", minimum)
    monkeypatch.setitem(vars(joint_contact), "active_step", second)
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
        mode=ContactGuidance((FeatureEvidence(source, report),), ContactMotion.STRAIGHT_SLOTS),
    )
    assert result is not None and result.contact is None
    minimum.assert_called_once()
    second.assert_called_once()
    domain = second.call_args.args[0]
    assert isinstance(domain, NativeSlots) and domain.source is first_model[0]
    assert domain.minimum * first_model[0].scale > 1e-5
    assert result.detail["native_positive_slot_projections"] == 1
    assert result.detail["newton_steps"] == result.detail["contact_pairs"] == 0
