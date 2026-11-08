"""
Verify exact mathematical runway removal and remaining-work connector recovery.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import Mock

import pytest

from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from experiments.experiment_ribbon_bend_relocation.solve import Result
from experiments.experiment_ribbon_fold_relaxation.steps import advance, projected, step_limit
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings
from experiments.experiment_ribbon_terminal_hardware import recovery
from experiments.experiment_ribbon_terminal_hardware.reversal import close_update
from experiments.experiment_ribbon_terminal_hardware.reversal_model import (
    NativeReversal,
    ReversalModel,
)
from tests.test_ribbon_aesthetic import _route


def test_fixed_zero_slots_have_no_motion_and_preserve_free_derivatives() -> None:
    """
    A zero-width domain must not be finite-differenced or reappear during closure.
    """
    route = _route((Straight(2), fold(1, 1.2, math.pi / 3, 0.2, 0.2), Straight(3)))
    parent = ReversalModel(route, 0)
    fixed = parent.straight_indices[0]
    model = NativeReversal(route, 0, frozenset((fixed,)))
    values = tuple(0.0 if i == fixed else v for i, v in enumerate(parent.initial))
    ordinary, rows = parent.jacobian(values), model.jacobian(values)
    assert model.bounds(fixed) == (0, 0)
    for original, constrained in zip(ordinary, rows):
        assert constrained[fixed] == 0
        assert all(a == b for i, (a, b) in enumerate(zip(original, constrained)) if i != fixed)
    delta = projected(model, values, rows, [0.0] * len(rows), [1.0] * len(values))
    assert delta is not None and delta[fixed] == 0
    assert advance(model, values, delta, step_limit(model, values, delta, 1))[fixed] == 0
    assert model.original.targets == route.targets


@pytest.mark.parametrize("slots", (frozenset((True,)), frozenset((100,)), frozenset((2,))))
def test_only_real_runway_coordinates_can_be_frozen(slots: frozenset[int]) -> None:
    """
    Angle coordinates and malformed indices cannot silently become fixed geometry.
    """
    route = _route((fold(1, 1.2, math.pi / 3, 0.2, 0.2), Straight(3), fold(1, 1.2, 0.5, 0.2, 0.2)))
    with pytest.raises(ValueError, match="runway"):
        NativeReversal(route, 0, slots)


def test_sub_native_reflection_recloses_then_couples_actual_new_hardware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the rejected case83 targets and all original work caps through both handoffs.
    """
    scene = Scene(
        Config(2481849929, 8, 0.75, 300, 300),
        Goal.from_degrees(22, 9, 63),
        Goal.from_degrees(8, 8, 4),
    )
    records: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    original = recovery.recover_joints

    def measured(*args: Any, **kwargs: Any) -> Result | None:
        """
        Record the actual child allocation without replacing its physical checks.
        """
        allocations.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setitem(vars(recovery), "recover_joints", measured)
    result = solver_v2.solve(
        scene.targets, Settings(1, False, True, True), lambda: None, records.append
    )
    assert result.route is not None and result.route.targets == scene.targets
    assert result.detail["contact"] == "separated"
    assert result.detail["terminal_hardware"]["final_status"] == "clear"
    detail = result.detail["construction"]["recovery"]
    before = detail["native_zero_before_joint"]
    assert before["iterations"] == 2 and before["newton_steps"] == 5
    assert len(allocations) == 1
    assert allocations[0]["maximum_updates"] == 2
    assert 0 < allocations[0]["maximum_cpu_seconds"] < 0.35
    assert 0 < allocations[0]["maximum_seconds"] < 2
    assert allocations[0]["remaining_pairs"] + before["contact_pairs"] == 1512
    assert detail["iterations"] <= 4 and detail["newton_steps"] <= 24
    assert detail["contact_pairs"] <= 1512 and detail["cpu_seconds"] <= 0.35
    assert any(r.get("status") == "native_slots_zeroed" for r in records)
    assert all(
        not isinstance(piece.geometry, Straight) or piece.geometry.material_length_mm > 1e-5
        for piece in result.route.pieces
    )
    assert result.detail["cap_error_mm"] < 1e-7
    assert result.detail["material_metric_error"] < 1e-10


@pytest.mark.parametrize("scale,native_minimum", ((1e-6, 1e-5), (1.0, 1e-5), (1e-6, None)))
def test_native_reclosure_redistributes_caps_without_creating_subminimum_runway(
    scale: float, native_minimum: float | None
) -> None:
    """
    Reclose the same coupled equations through angular travel when absent-runway growth is too small.
    """
    model = Mock(spec=NativeReversal)
    model.scale = scale
    model.straight_indices = (0,)
    model.bounds.side_effect = lambda index: (0.0, math.inf) if index == 0 else (-math.pi, math.pi)
    model.residual.side_effect = lambda values: (values[0] + values[1] - 1.0,) + (0.0,) * 5
    model.jacobian.return_value = [[1.0, 1.0]] + [[0.0, 0.0] for _ in range(5)]
    values, steps, reason = close_update(
        model,
        (0.0, 0.0),
        lambda: None,
        remaining_steps=6,
        minimum_straight_mm=native_minimum,
    )
    assert reason is None and steps <= 6
    assert max(map(abs, model.residual(values))) < 1e-13
    if scale == 1e-6 and native_minimum is not None:
        assert values[0] == 0.0 and values[1] == pytest.approx(1.0)
    else:
        assert values == pytest.approx((0.5, 0.5))
