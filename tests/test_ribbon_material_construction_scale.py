"""
Condition native construction without changing physical material, order or dimensionless data.
"""

from __future__ import annotations

import math
from typing import cast

import pytest

from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import PlacedPiece, Pose, Straight
from experiments.experiment_ribbon_fold_route.material_cylinder import cylinder
from experiments.experiment_ribbon_fold_route.material_profile import material_profile
from experiments.experiment_ribbon_fold_route.material_scale import NativeScale, construction
from experiments.experiment_ribbon_fold_route.material_surfaces import material_patches


@pytest.mark.parametrize("lines,diameter", ((3, 0.5), (6, 2.0)))
@pytest.mark.parametrize("angle,bank", ((0.04, 0.1), (-0.06, -0.1)))
def test_binary_construction_preserves_the_complete_ordered_material_map(
    lines: int, diameter: float, angle: float, bank: float
) -> None:
    """
    Conjugate an authored straight and oblique fold, including profile heights and actual cap frames.
    """
    pose = Pose(Vector3(12, -9, 2), Vector3(1, 0, 0), Vector3(0, 1, 0))
    straight = PlacedPiece(pose, Straight(4 * diameter), "authored straight")
    width = (lines + 0.2) * diameter
    fold = PlacedPiece(
        straight.end_pose(),
        CylindricalFold(2 * diameter, angle, bank, width, width, width),
        "authored fold",
    )
    pieces = (straight, fold)
    profile = material_profile(lines, diameter)
    patches = material_patches(pieces, profile)
    scaled = construction(pieces, patches, NativeScale.CONDITIONED, lambda: None)
    assert scaled.policy.factor == 1024
    assert len(scaled.pieces) == len(pieces) and len(scaled.patches) == len(patches)
    for original, actual in zip(pieces, scaled.pieces):
        assert actual.pose.tangent is original.pose.tangent
        assert actual.pose.width is original.pose.width and actual.label == original.label
        assert actual.geometry.material_length_mm / 1024 == original.geometry.material_length_mm
        for u in (0.0, 0.3, 1.0):
            expected = original.surface(u, diameter / 3)
            observed = actual.surface(u, diameter * 1024 / 3)
            for first, second in zip(expected[:2], observed[:2]):
                assert (second.x / 1024, second.y / 1024, second.z / 1024) == pytest.approx(
                    (first.x, first.y, first.z), abs=1e-12
                )
        end, scaled_end = original.end_pose(), actual.end_pose()
        assert scaled_end.tangent == end.tangent and scaled_end.width == end.width
    for before, after in zip(patches, scaled.patches):
        assert (after.piece_index, after.region, after.profile_index) == (
            before.piece_index,
            before.region,
            before.profile_index,
        )
        assert after.degree_u == before.degree_u and after.knots_u is before.knots_u
        assert after.profile.weights is before.profile.weights
        assert after.profile.label == before.profile.label
        assert after.error_bound_mm / 1024 == before.error_bound_mm
        for original_row, scaled_row in zip(before.rows, after.rows):
            for original_point, scaled_point in zip(original_row, scaled_row):
                assert tuple(
                    math.ldexp(v, -10) for v in (scaled_point.x, scaled_point.y, scaled_point.z)
                ) == (original_point.x, original_point.y, original_point.z)
        assert (
            tuple((q / 1024, b / 1024) for q, b in after.profile.controls)
            == before.profile.controls
        )
        if before.region != "bend":
            old_support = cylinder(pieces[before.piece_index], before)
            new_support = cylinder(scaled.pieces[after.piece_index], after)
            assert new_support.radius_mm / 1024 == old_support.radius_mm
            assert new_support.axis == old_support.axis
            assert (
                new_support.origin.x / 1024,
                new_support.origin.y / 1024,
                new_support.origin.z / 1024,
            ) == pytest.approx(
                (old_support.origin.x, old_support.origin.y, old_support.origin.z), abs=1e-12
            )


def test_unit_policy_retains_original_objects_and_cancellation_is_never_ignored() -> None:
    """
    Keep the explicit legacy representation and source/resource failures distinct from a scaled result.
    """
    pieces = (
        PlacedPiece(
            Pose(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(1), "unit"
        ),
    )
    patches = material_patches(pieces, material_profile(3, 0.5))
    identity = construction(pieces, patches, NativeScale.UNIT, lambda: None)
    assert identity.pieces is pieces and identity.patches is patches
    calls = 0

    def stop() -> None:
        """
        Stop within construction preparation under the original caller's clock.
        """
        nonlocal calls
        calls += 1
        if calls == 3:
            raise TimeoutError("original resource ceiling")

    with pytest.raises(TimeoutError, match="original resource"):
        construction(pieces, patches, NativeScale.CONDITIONED, stop)


def test_untyped_scale_cannot_select_an_unbounded_magnification() -> None:
    """
    An arbitrary factor cannot expand the fixed experimental conditioning policy.
    """
    with pytest.raises(ValueError, match="explicit"):
        construction((), (), cast(NativeScale, cast(object, 2048)), lambda: None)


@pytest.mark.parametrize("coordinate", (math.inf, math.nan, 1e308))
def test_unrepresentable_dimensions_stop_before_native_authoring(coordinate: float) -> None:
    """
    Finite overflow and nonfinite data cannot become a partially scaled construction or a new factor.
    """
    piece = PlacedPiece(
        Pose(Vector3(coordinate, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0)), Straight(1), "invalid"
    )
    with pytest.raises((ValueError, OverflowError)):
        construction((piece,), (), NativeScale.CONDITIONED, lambda: None)
