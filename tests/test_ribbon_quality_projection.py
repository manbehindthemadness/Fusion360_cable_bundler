"""
Verify simultaneous scalar inequalities and strict rejection at the nonlinear certificate boundary.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.experiment_ribbon_fold_route.geometry import Straight
from experiments.experiment_ribbon_terminal_hardware import fold_recovery
from experiments.experiment_ribbon_terminal_hardware.check import Report
from experiments.experiment_ribbon_terminal_hardware.feature_plane import FeaturePlane, SignedJoints
from experiments.experiment_ribbon_terminal_hardware.gate import Gate
from experiments.experiment_ribbon_terminal_hardware.model import Dimensions, Hardware
from experiments.experiment_ribbon_terminal_hardware.quality_projection import quality_step
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("bound,expected", ((-2.0, 1.0), (-0.5, None)))
def test_nonbinding_margin_stays_free_but_every_linear_bound_is_enforced(
    bound: float, expected: float | None
) -> None:
    """
    Require x=1 and y>=x while allowing y<=2, or reject incompatible y<=0.5.
    """
    model = Mock(spec=SignedJoints)
    model.bounds.return_value = (-10.0, 10.0)
    rows = [[1.0, 0.0]] + [[0.0, 0.0]] * 5 + [[1.0, -1.0], [0.0, 1.0]]
    equation = (-1.0,) + (0.0,) * 5 + (0.0, bound)
    checkpoint = Mock()
    result = quality_step(model, (0.0, 0.0), rows, equation, checkpoint)
    assert checkpoint.call_count == 4
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx((1.0, expected))


def test_coordinate_bound_cannot_be_ignored_by_feature_projection() -> None:
    """
    A zero runway cannot move negative to satisfy an otherwise valid scalar projection.
    """
    model = Mock(spec=SignedJoints)
    model.bounds.return_value = (0.0, 10.0)
    rows = [[0.0]] * 6 + [[1.0]]
    assert quality_step(model, (0.0,), rows, (0.0,) * 6 + (1.0,), lambda: None) is None


def test_projection_checkpoint_failure_propagates() -> None:
    """
    Source, cancellation and resource errors cannot become optional quality rejections.
    """
    checkpoint = Mock(side_effect=RuntimeError("source changed"))
    with pytest.raises(RuntimeError, match="source changed"):
        quality_step(Mock(spec=SignedJoints), (0.0,), [[0.0]] * 7, (0.0,) * 7, checkpoint)


def test_growth_constraint_does_not_accept_an_uncertified_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A length-rejected closed fold proposal may activate quality but cannot bypass projection/contact.
    """
    source = _route((Straight(10),))
    model = SignedJoints(source)
    monkeypatch.setattr(
        FeaturePlane, "create", Mock(return_value=SimpleNamespace(gap=lambda _: 1e-7 / model.scale))
    )
    terminal = Mock(spec=Gate)
    terminal.hardware = Hardware.create(source.targets, Dimensions.scaled(source.targets))
    projection = Mock(return_value=None)
    monkeypatch.setitem(vars(fold_recovery), "quality_step", projection)
    contact = Mock(side_effect=AssertionError("No certificate before feasible closure"))
    monkeypatch.setitem(vars(fold_recovery), "inspect_contact", contact)
    events: list[dict[str, object]] = []
    result = fold_recovery.recover(
        source,
        Report("blocked", 1),
        terminal,
        lambda: None,
        events.append,
        maximum_length_mm=9.9,
        minimum_straight_mm=1e-5,
        remaining_pairs=700,
        maximum_cpu_seconds=0.35,
        maximum_seconds=2,
    )
    assert result is not None and result.route is source and result.contact is None
    assert result.detail["maximum_length_mm"] == 9.9
    assert result.detail["stop_reason"] == "joint_projection_infeasible"
    assert result.detail["newton_steps"] == 0
    assert [e["remaining_updates"] for e in events if e["status"] == "quality_activated"] == [4]
    projection.assert_called_once()
    contact.assert_not_called()
    terminal.measure.assert_not_called()
