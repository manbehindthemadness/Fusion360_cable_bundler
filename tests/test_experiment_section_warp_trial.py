"""
Keep twist and anchor positions invariant while scaling the local section warp.
"""

import math

import pytest

from cable_bundler.routing.geometry import difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.section_warp_trial import (
    imposed_flex,
    scaled_direction,
)
from experiments.experiment_ribbon_cap_transition.straight_twist import twist_frames


@pytest.mark.parametrize("scale", (0.0, 0.5, 1.0))
def test_warp_changes_only_relative_frames(scale: float) -> None:
    """
    Preserve the banked center and all anchors; terminal deformation remains zero.
    """
    frame = twist_frames(360)[17]
    minus, plus = (0.2, -0.8, 0.5), (-0.2, 0.8, 0.5)
    flex = imposed_flex(frame, minus, plus, scale)
    assert flex.center.width == frame.width
    for x, anchor in ((-14.4, flex.minus), (0.0, flex.center), (14.4, flex.plus)):
        assert (
            magnitude(difference(anchor.position, frame.origin.translated(frame.width, x))) < 1e-12
        )
    terminal = imposed_flex(frame, minus, plus, scale, terminal=True)
    for x in (-14.4, -8.0, 0.0, 8.0, 14.4):
        expected = frame.origin.translated(frame.width, x).translated(frame.thickness, 0.4)
        assert magnitude(difference(terminal.point(x, 0.4), expected)) < 1e-12


def test_scale_is_angular_not_vector_blending() -> None:
    """
    Half warp halves the actual guide tilt angle and zero warp is planar.
    """
    full = scaled_direction((0.4, 0.7, 0.1), 1)
    half = scaled_direction((0.4, 0.7, 0.1), 0.5)
    assert math.acos(half.z) == pytest.approx(math.acos(full.z) / 2)
    assert dot(full, full) == pytest.approx(1)
    zero = imposed_flex(twist_frames(360)[12], (0.4, 0.7, 0.1), (-0.4, -0.7, 0.1), 0)
    assert zero.minus.width == zero.center.width == zero.plus.width


@pytest.mark.parametrize(
    "local,scale", (((1.0, 0.0), 1), ((0.0, 0.0, -1.0), 1), ((1.0, 0.0, 1.0), 2))
)
def test_invalid_warp_inputs_rejected(local: tuple[float, ...], scale: float) -> None:
    """
    Reject ambiguous or out-of-scope directions without fallback axes.
    """
    with pytest.raises(ValueError):
        scaled_direction(local, scale)
