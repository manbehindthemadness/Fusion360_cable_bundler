"""
Prevent finite-width steering overshoot and inward fold returns at fixed targets.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import ZERO, Pose, extend, pose_error
from experiments.experiment_ribbon_fold_route.steering import translation


@pytest.mark.parametrize("lateral,height", [(0.2, 0.1), (-0.2, -0.1), (20.0, -4.0), (-20.0, 4.0)])
@pytest.mark.parametrize("runway", [0.0, 0.8])
def test_small_and_large_translations_never_reverse_the_steering_run(
    lateral: float,
    height: float,
    runway: float,
) -> None:
    """
    Invert finite offsets while retaining one outward pair and one height pair.
    """
    start = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
    desired = Vector3(60, lateral, height)
    radius = 0.75 / 0.996 * (1 + 1e-9)
    pieces = translation(desired, radius, 4.8, runway, 0.75, ())
    assert max(pose_error(extend(start, pieces), Pose(desired, start.tangent, start.width))) < 1e-8
    folds = [piece for piece in pieces if isinstance(piece, CylindricalFold)]
    assert len(folds) == 4  # No additional half-turns to cancel an overshot displacement.
    assert folds[0].angle_radians == -folds[1].angle_radians
    assert math.copysign(1, folds[0].angle_radians) == -math.copysign(1, height)
    if abs(lateral) < 1:
        assert abs(folds[0].bank_radians) < math.pi / 4


@pytest.mark.parametrize("height", [-0.01, 0.01])
def test_small_height_changes_reduce_the_turn_instead_of_doubling_back(height: float) -> None:
    """
    Close a near-flat S through two small transverse bends without a reversal loop.
    """
    start = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
    desired = Vector3(10, 0, height)
    pieces = translation(desired, 0.76, 4.8, 0.0, 0.75, ())
    assert max(pose_error(extend(start, pieces), Pose(desired, start.tangent, start.width))) < 1e-9
    folds = [piece for piece in pieces if isinstance(piece, CylindricalFold)]
    assert len(folds) == 2
    assert all(abs(piece.angle_radians) < math.pi / 2 for piece in folds)
