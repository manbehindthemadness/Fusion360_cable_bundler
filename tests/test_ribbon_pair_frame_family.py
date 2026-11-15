"""
Verify continuous orientation elimination without declaring positional or physical feasibility.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from experiments.experiment_ribbon_paired_return.frame_family import FrameFamily


def _family(scale: float, sign: int) -> FrameFamily:
    """
    Create independent unequal-bank/radius factors in a rotated translated frame.
    """
    start = Pose(Vector3(2 * scale, -3 * scale, 5 * scale), Vector3(0, 1, 0), Vector3(0, 0, 1))
    first = CylindricalFold(0.6 * scale, sign * 1.4, 0.3, 3.15 * scale, 0.8 * scale, 0.9 * scale)
    second = CylindricalFold(0.9 * scale, sign * -2.1, -0.2, 3.15 * scale, 0.7 * scale, 0.8 * scale)
    middle = PlacedPiece(start, first, "First analytical factor").end_pose()
    end = PlacedPiece(middle, second, "Second analytical factor").end_pose()
    return FrameFamily(start, end, (first, second))


@pytest.mark.parametrize("scale", [0.5, 1, 100])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("delta", [-0.01, 0, 0.01])
def test_bank_motion_preserves_frames_radii_and_extra_material(
    scale: float, sign: int, delta: float
) -> None:
    """
    Preserve the complete ordered frame while allowing the companion bank to differ.
    """
    family = _family(scale, sign)
    following = family.at(family.reference[0].bank_radians + delta)
    assert following is not None
    pose = family.start
    for old, new in zip(family.reference, following):
        assert new.radius_mm == old.radius_mm and new.width_mm == old.width_mm
        assert old.angle_radians * new.angle_radians > 0
        old_lead = old.width_mm / 2 * abs(math.tan(old.bank_radians))
        new_lead = new.width_mm / 2 * abs(math.tan(new.bank_radians))
        assert new.before_mm - new_lead == pytest.approx(old.before_mm - old_lead)
        assert new.after_mm - new_lead == pytest.approx(old.after_mm - old_lead)
        pose = PlacedPiece(pose, new, "Analytical continued factor").end_pose()
    assert magnitude(difference(pose.tangent, family.end.tangent)) < 1e-10
    assert magnitude(difference(pose.width, family.end.width)) < 1e-10
    if delta == 0:
        for old, new in zip(family.reference, following):
            assert new.angle_radians == pytest.approx(old.angle_radians)
            assert new.bank_radians == pytest.approx(old.bank_radians)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True])
def test_invalid_bank_raises_without_a_branch_guess(invalid: float) -> None:
    """
    Invalid external coordinates cannot become a hidden alternate orientation trial.
    """
    with pytest.raises(ValueError, match="finite"):
        _family(1, 1).at(invalid)


def test_singular_or_longitudinal_chart_declines() -> None:
    """
    An indeterminate identity chart or invalid material crease does not add folds.
    """
    family = _family(1, 1)
    assert family.at(math.pi / 2) is None
    assert replace(family, end=family.start).at(0.3) is None
