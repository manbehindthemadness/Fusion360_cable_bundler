"""
Align joint closure with the actual ordered mating frames without relaxing contact.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_bend_relocation.model import MovableBends, retract_active
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_fold_relaxation.model import Model as ClosureModel
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_terminal_hardware.check import inspect
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware


def _straight(length: float, offset: float = 0.0, *, reversed_end: bool = False) -> FoldRoute:
    """
    Keep exact target poses while authoring an independently mismatched straight length or end frame.
    """
    origin = Vector3(0, 0, 0)
    tangent, width = Vector3(1, 0, 0), Vector3(0, 1, 0)
    targets = Targets(
        "cap closure control",
        origin,
        Vector3(length, 0, 0),
        tangent,
        Vector3(-1, 0, 0) if reversed_end else tangent,
        width,
        width,
        3,
        0.75,
    )
    piece = PlacedPiece(Pose(origin, tangent, width), Straight(length + offset), "straight")
    return FoldRoute(targets, (piece,), 0.75)


@pytest.mark.parametrize("length", (10.0, 100.0, 1000.0))
@pytest.mark.parametrize("sign", (-1, 1))
def test_small_normalized_error_is_reclosed_to_actual_mating_accuracy(
    length: float, sign: int
) -> None:
    """
    Spend a real joint correction instead of accepting a tiny normalized cap mismatch or snapping targets.
    """
    source = _straight(length, sign * length * 5e-11)
    model = MovableBends(source)
    initial = model.initial
    assert max(map(abs, model.residual(initial))) < 1e-10
    assert 1e-10 < cap_error(source) < 1e-7
    corrected = retract_active(model, initial, lambda: None)
    assert corrected is not None
    assert corrected != initial
    route = model.route(cast(tuple[float, ...], corrected))
    assert route is not None and route.targets is source.targets
    assert cap_error(route) < 1e-10
    assert route.radius_mm == source.radius_mm
    assert len(route.pieces) == 1 and isinstance(route.pieces[0].geometry, Straight)
    hardware = Hardware.create(route.targets, Dimensions.scaled(route.targets))
    report = inspect(route, hardware)
    assert report.status == "clear" and report.cells_checked == 2


def test_closed_frames_need_no_derivatives(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Preserve the cheap stopping path when normalized residual and actual caps already agree.
    """
    model = MovableBends(_straight(100.0))
    forbidden = Mock(side_effect=AssertionError("Closed caps need no Newton derivative"))
    monkeypatch.setattr(ClosureModel, "jacobian", forbidden)
    assert retract_active(model, model.initial, lambda: None) is model.initial
    forbidden.assert_not_called()


def test_zero_local_rotation_is_not_an_ordered_frame_certificate() -> None:
    """
    Decline an unattainable half-turn even when the local rotation residual vanishes.
    """
    model = MovableBends(_straight(100.0, reversed_end=True))
    assert max(map(abs, model.residual(model.initial))) == 0.0
    assert retract_active(model, model.initial, lambda: None) is None


def test_hard_caller_stop_is_not_masked_by_closure() -> None:
    """
    Propagate cancellation or exhausted outer resources before any joint correction.
    """
    model = MovableBends(_straight(100.0, 5e-9))

    def stopped() -> None:
        """
        Represent a hard caller boundary rather than optional closure exhaustion.
        """
        raise TimeoutError("caller stop")

    with pytest.raises(TimeoutError, match="caller stop"):
        retract_active(model, model.initial, stopped)
