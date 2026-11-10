"""
Keep certified layout smoothing aligned with the unchanged absolute mating-cap proof.
"""

from __future__ import annotations

import math
from typing import cast
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_aesthetic import layout_solve
from experiments.experiment_ribbon_aesthetic.layout_model import Model
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_relaxation.closure_policy import ClosurePolicy
from experiments.experiment_ribbon_fold_relaxation.flexible_steps import retract
from experiments.experiment_ribbon_fold_relaxation.model import Model as ClosureModel
from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from tests.test_ribbon_aesthetic import _route
from tests.test_ribbon_cap_retraction import _straight


def test_layout_smoothing_requests_actual_ordered_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Route every optional layout correction through certified closure before contact measurement.
    """
    source = _route((Straight(6), fold(1, 1.2, math.pi / 2, 0, 0), Straight(8)))
    correction = Mock(return_value=None)
    monkeypatch.setitem(vars(layout_solve), "retract", correction)
    result, _ = layout_solve.ease(source, source.material_length_mm * 1.01, lambda: None, Mock())
    assert result is source and 0 < correction.call_count <= 6
    assert all(
        call.kwargs.get("closure_policy") is ClosurePolicy.ORDERED_CAPS
        for call in correction.call_args_list
    )


@pytest.mark.parametrize("length", (10.0, 100.0, 1000.0))
@pytest.mark.parametrize("sign", (-1, 1))
def test_flexible_retraction_corrects_small_normalized_offsets_to_actual_caps(
    length: float, sign: int
) -> None:
    """
    Continue genuine coordinate correction until the same fixed mating frames qualify at every scale.
    """
    source = _straight(length, sign * length * 5e-11)
    model = Model(source)
    initial = model.initial
    assert max(map(abs, model.residual(initial))) < 1e-10
    assert 1e-10 < cap_error(source) < 1e-7
    corrected = retract(
        model,
        initial,
        model.length(initial) + 1,
        lambda: None,
        closure_policy=ClosurePolicy.ORDERED_CAPS,
    )
    assert corrected is not None
    assert corrected != initial
    result = model.route(cast(tuple[float, ...], corrected))
    assert result is not None
    assert result.targets is source.targets and cap_error(result) < 1e-10
    assert result.radius_mm == source.radius_mm
    hardware = Hardware.create(result.targets, Dimensions.scaled(result.targets))
    report = inspect(result, hardware)
    assert report.status == "clear" and report.cells_checked == 2


def test_flexible_default_retains_normalized_exploration() -> None:
    """
    Keep existing routing/prediction callers unchanged until they request ordered-cap certification.
    """
    model = Model(_straight(100.0, 5e-9))
    assert retract(model, model.initial, 2.0, lambda: None) == model.initial


def test_local_rotation_zero_cannot_certify_a_half_turn() -> None:
    """
    Check full ordered frames even when the normalized local rotation residual vanishes.
    """
    model = Model(_straight(100.0, reversed_end=True))
    assert max(map(abs, model.residual(model.initial))) == 0.0
    assert (
        retract(model, model.initial, 2.0, lambda: None, closure_policy=ClosurePolicy.ORDERED_CAPS)
        is None
    )


def test_certified_flexible_retraction_preserves_hard_cancellation() -> None:
    """
    Propagate the caller stop before another numerical correction can run.
    """
    model = Model(_straight(100.0, 5e-9))
    checkpoint = Mock(side_effect=TimeoutError("caller stop"))
    with pytest.raises(TimeoutError, match="caller stop"):
        retract(model, model.initial, 2.0, checkpoint, closure_policy=ClosurePolicy.ORDERED_CAPS)


def test_closed_flexible_caps_need_no_newton_derivatives(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep the exact mating control on the cheap certified stopping path.
    """
    model = Model(_straight(100.0))
    derivative = Mock(side_effect=AssertionError("closed caps need no correction"))
    monkeypatch.setattr(ClosureModel, "jacobian", derivative)
    assert (
        retract(model, model.initial, 2.0, lambda: None, closure_policy=ClosurePolicy.ORDERED_CAPS)
        == model.initial
    )
    derivative.assert_not_called()


def test_invalid_flexible_closure_policy_is_rejected() -> None:
    """
    Reject untyped policy input rather than choosing a weaker closure gate.
    """
    model = Model(_straight(100.0))
    with pytest.raises(ValueError, match="closure policy"):
        retract(
            model,
            model.initial,
            2.0,
            lambda: None,
            closure_policy=cast(ClosurePolicy, cast(object, "bad")),
        )
