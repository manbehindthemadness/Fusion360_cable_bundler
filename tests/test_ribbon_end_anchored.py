"""
Verify connector anchoring without reversing material or hiding the opposite cap error.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import difference, magnitude
from experiments.experiment_ribbon_fold_route.geometry import Pose, Straight, pose_error
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_terminal_hardware.end_anchored import EndAnchoredJoints
from experiments.experiment_ribbon_terminal_hardware.feature_plane import SignedJoints
from tests.test_ribbon_aesthetic import _route


@pytest.mark.parametrize("scale", (1.0, 10.0))
@pytest.mark.parametrize("change", (-0.1, 0.1))
def test_changed_bend_keeps_end_fixed_and_exposes_start_error(scale: float, change: float) -> None:
    """
    Both motion directions anchor the connector and preserve the forward model's intrinsic shape.
    """
    source = _route(
        (
            Straight(2 * scale),
            fold(2 * scale, 1.2, 1.0, 0.2, 0),
            Straight(3 * scale),
            fold(3 * scale, 1.2, -0.7, -0.3, 0),
            Straight(4 * scale),
        )
    )
    model = EndAnchoredJoints(source)
    forward = SignedJoints(source)
    assert max(abs(value) for value in model.residual(model.initial)) < 1e-12
    values = list(model.initial)
    values[4] += change
    coordinates = tuple(values)
    route = model.route(coordinates)
    unanchored = forward.route(coordinates)
    assert route is not None and unanchored is not None
    target = source.targets
    end = Pose(target.end, target.end_tangent, target.end_width)
    assert max(pose_error(route.pieces[-1].end_pose(), end)) < 1e-12
    assert max(pose_error(unanchored.pieces[-1].end_pose(), end)) > 0.01
    assert max(abs(value) for value in model.residual(coordinates)) > 0.001
    assert route.targets == source.targets and model.preserves(route)
    assert model.pieces(coordinates) is model.pieces(coordinates)
    for placed, original in zip(route.pieces, unanchored.pieces):
        assert placed.geometry == original.geometry
        assert placed.label == original.label
    # One rigid placement preserves distances across separate folds and across lanes.
    for first, second in ((0, 4), (1, 3)):
        before = magnitude(
            difference(
                unanchored.pieces[first].surface(0.3, -0.2)[0],
                unanchored.pieces[second].surface(0.7, 0.2)[0],
            )
        )
        after = magnitude(
            difference(
                route.pieces[first].surface(0.3, -0.2)[0],
                route.pieces[second].surface(0.7, 0.2)[0],
            )
        )
        assert after == pytest.approx(before, abs=1e-12)


def test_reversed_start_orientation_is_not_a_zero_closure_residual() -> None:
    """
    A half-turn target mismatch cannot be hidden by the historical skew-vector zero.
    """
    original = _route((Straight(2), fold(2, 1.2, 1, 0.2, 0), Straight(3)))
    target = original.targets
    changed = replace(
        original,
        targets=replace(
            target,
            start_tangent=target.start_tangent.translated(target.start_tangent, -2),
            start_width=target.start_width.translated(target.start_width, -2),
        ),
    )
    model = EndAnchoredJoints(changed)
    # The target end is unchanged; inspect orientation against the actual original start.
    values = model.initial
    actual_start = model.pieces(values)[0].pose
    assert pose_error(actual_start, original.pieces[0].pose)[1] < 1e-12
    assert math.hypot(*model.residual(values)[3:]) == pytest.approx(math.pi)
