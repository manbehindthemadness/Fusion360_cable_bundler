"""
Check fixed anchors, perpendicular frames and cap preservation independently of Fusion.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude
from experiments.experiment_ribbon_cap_transition.section_flex import flex_section
from experiments.experiment_secure_discrete_ribbon.frames import RibbonFrame


@pytest.fixture
def frame() -> RibbonFrame:
    """
    Provide a translated orthonormal section with positive X width.
    """
    return RibbonFrame(Vector3(3, 4, 5), Vector3(0, 0, 1), Vector3(1, 0, 0), Vector3(0, 1, 0))


def test_three_anchors_and_local_planes(frame: RibbonFrame) -> None:
    """
    Preserve all positions while changing both local edge planes independently.
    """
    tangents = (Vector3(0.3, 0.6, 1), frame.tangent, Vector3(-0.4, -0.5, 1))
    section = flex_section(frame, tangents[0], tangents[2])
    for x, anchor, tangent in zip(
        (-14.4, 0, 14.4), (section.minus, section.center, section.plus), tangents
    ):
        assert (
            magnitude(difference(section.point(x, 0), frame.origin.translated(frame.width, x)))
            < 1e-12
        )
        assert abs(dot(anchor.width, tangent)) < 1e-12
        assert abs(dot(anchor.thickness, tangent)) < 1e-12
        epsilon = 1e-5
        nearby = x + epsilon if x < 14.4 else x - epsilon
        derivative = difference(section.point(nearby, 0), section.point(x, 0))
        assert abs(dot(derivative, tangent)) / epsilon < 1e-5
    assert abs(section.point(10, 0.75).z - 5) > 0.01
    assert (
        magnitude(
            difference(section.point(0, 0.75), frame.origin.translated(frame.thickness, 0.75))
        )
        < 1e-12
    )


@pytest.mark.parametrize("terminal", [False, True])
def test_planar_identity_and_terminal_override(frame: RibbonFrame, terminal: bool) -> None:
    """
    Keep planar controls exact and prevent fitted endpoint tangents changing caps.
    """
    tangent = Vector3(0.5, 0.5, 1) if terminal else frame.tangent
    section = flex_section(frame, tangent, tangent, terminal=terminal)
    for x in (-14.4, -10, 0, 4.5, 14.4):
        expected = frame.origin.translated(frame.width, x).translated(frame.thickness, 0.75)
        assert magnitude(difference(section.point(x, 0.75), expected)) < 1e-12


@pytest.mark.parametrize("reach", [0, -1, math.nan])
def test_invalid_reach_rejected(frame: RibbonFrame, reach: float) -> None:
    """
    Reject malformed section bounds before deformation.
    """
    with pytest.raises(ValueError):
        flex_section(frame, frame.tangent, frame.tangent, reach=reach)


def test_degenerate_guide_rejected(frame: RibbonFrame) -> None:
    """
    Do not silently choose a new orientation for a width-parallel guide tangent.
    """
    with pytest.raises(ValueError):
        flex_section(frame, frame.width, frame.tangent)
