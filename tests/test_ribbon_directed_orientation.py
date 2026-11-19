"""
Verify exact frame factorization with spatially directed intermediate material headings.
"""

from __future__ import annotations

import math

import pytest

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_ribbon_constrained_construction.directed_orientation import factors
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose
from experiments.experiment_ribbon_fold_route.primitives import fold
from experiments.experiment_ribbon_joint_route.frames import rotation_choices
from experiments.experiment_ribbon_reduced_joints.kinematics import rotate

START = Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))


@pytest.mark.parametrize(
    "angles",
    (
        (0.8, 0.15, -1.1, -0.3),
        (-0.6, -0.25, 1.2, 0.4),
        (1.3, -0.4, 0.7, 0.2),
        (-1.2, 0.3, -0.9, -0.2),
    ),
)
def test_feasible_requested_intermediate_heading_is_recovered_exactly(
    angles: tuple[float, ...],
) -> None:
    """
    Known asymmetric crease pairs supply a feasible heading that must be selected with dot product one.
    """
    a, bank_a, b, bank_b = angles
    first = PlacedPiece(START, fold(2, 1.2, a, bank_a, 0), "known first")
    second = PlacedPiece(first.end_pose(), fold(2, 1.2, b, bank_b, 0), "known second")
    wanted = first.end_pose().tangent
    finish = second.end_pose()
    end = Pose(START.origin.translated(wanted, 10), finish.tangent, finish.width)
    derived = factors(START, end, 2, 1.2)
    assert len(derived) == 2
    actual_first = PlacedPiece(START, derived[0], "directed first")
    actual_end = PlacedPiece(actual_first.end_pose(), derived[1], "directed second").end_pose()
    assert dot(actual_first.end_pose().tangent, wanted) == pytest.approx(1.0, abs=1e-10)
    assert magnitude(difference(actual_end.tangent, end.tangent)) < 1e-10
    assert magnitude(difference(actual_end.width, end.width)) < 1e-10


@pytest.mark.parametrize("desired", (Vector3(4, 8, -2), Vector3(-1, 3, 5), Vector3(7, -2, -4)))
def test_displacement_alignment_is_no_worse_than_balanced_bank_roots(desired: Vector3) -> None:
    """
    The directed continuum optimum dominates both legacy discrete balanced-bank choices for heading.
    """
    first = PlacedPiece(START, fold(2, 1.2, 0.8, 0.15, 0), "known first")
    finish = PlacedPiece(first.end_pose(), fold(2, 1.2, -1.1, -0.3, 0), "known second").end_pose()
    end = Pose(desired, finish.tangent, finish.width)
    derived = factors(START, end, 2, 1.2)
    heading = PlacedPiece(START, derived[0], "directed").end_pose().tangent
    for choice in rotation_choices(START, end, 2, 1.2):
        old_heading = PlacedPiece(START, choice[0], "balanced").end_pose().tangent
        assert dot(heading, unit(desired)) >= dot(old_heading, unit(desired)) - 1e-10


def test_directed_factorization_is_covariant_under_rigid_frame_change() -> None:
    """
    World position and axes cannot change the chosen local bend geometry.
    """
    first = PlacedPiece(START, fold(2, 1.2, 0.8, 0.15, 0), "first")
    finish = PlacedPiece(first.end_pose(), fold(2, 1.2, -1.1, -0.3, 0), "second").end_pose()
    end = Pose(Vector3(4, 8, -2), finish.tangent, finish.width)
    axis = unit(Vector3(1, 2, 3))
    shift = Vector3(11, -5, 7)

    def moved(pose: Pose) -> Pose:
        """
        Apply one common proper rotation and translation to the input frames.
        """
        return Pose(
            shift.translated(rotate(pose.origin, axis, 0.7), 1),
            rotate(pose.tangent, axis, 0.7),
            rotate(pose.width, axis, 0.7),
        )

    original = factors(START, end, 2, 1.2)
    changed = factors(moved(START), moved(end), 2, 1.2)
    for a, b in zip(original, changed):
        assert a.angle_radians == pytest.approx(b.angle_radians, abs=1e-10)
        assert a.bank_radians == pytest.approx(b.bank_radians, abs=1e-10)


def test_pure_longitudinal_rotation_keeps_existing_exact_degenerate_construction() -> None:
    """
    A collapsed two-factor heading circle does not invent a singular longitudinal crease.
    """
    end = Pose(Vector3(10, 0, 0), START.tangent, Vector3(0, math.cos(0.7), math.sin(0.7)))
    derived = factors(START, end, 2, 1.2)
    assert len(derived) == 3
    pose = START
    for primitive in derived:
        pose = PlacedPiece(pose, primitive, "degenerate fold").end_pose()
    assert magnitude(difference(pose.tangent, end.tangent)) < 1e-10
    assert magnitude(difference(pose.width, end.width)) < 1e-10
