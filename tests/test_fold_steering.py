"""
Prevent finite-width steering overshoot and inward fold returns at fixed targets.
"""

import math

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import ZERO, Pose, extend, pose_error
from experiments.experiment_ribbon_fold_route.steering import signed_distance, translation


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


@pytest.mark.parametrize("arrival_height", [-2.5, 2.5])
def test_initial_reversal_bows_away_from_the_opposite_cap(arrival_height: float) -> None:
    """
    Mirror the initial bends without changing their closure, length or radius.
    """
    start = Pose(ZERO, Vector3(1, 0, 0), Vector3(0, 1, 0))
    pieces = signed_distance(-4.0, 0.76, 1.8, 0.0, arrival_height=arrival_height)
    pose = extend(start, pieces)
    assert max(pose_error(pose, Pose(Vector3(-4, 0, 0), start.tangent, start.width))) < 1e-9
    folded = extend(start, pieces[:1])
    assert folded.origin.z * arrival_height < 0
    assert abs(folded.origin.z) == pytest.approx(2 * 0.76)
    assert sum(piece.material_length_mm for piece in pieces) == pytest.approx(
        4 + 2 * math.pi * 0.76
    )
