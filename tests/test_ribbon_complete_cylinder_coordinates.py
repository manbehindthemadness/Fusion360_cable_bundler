"""
Check intrinsic cylinder inversion, branch guards and whole-curve angular progress independently of native UVs.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_coordinates import (
    CylinderReference,
    build,
    inspect_curve,
)
from experiments.experiment_ribbon_complete.native_cap_material import NativeCapCurve
from tests.test_ribbon_complete_native_flat_cylinder import cylinder
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def reference() -> CylinderReference:
    """
    Use an exact rational circular arc on a cylinder with deliberately nonunit raw axis.
    """
    return CylinderReference(
        cylinder(),
        (
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(1), Fraction(4, 3)),
            (Fraction(0), Fraction(-7, 25), Fraction(24, 25)),
        ),
        (Fraction(1), Fraction(3, 5), Fraction(1)),
    )


def test_intrinsic_inverse_recovers_world_points_without_native_parameter_values() -> None:
    """
    Explicit rational-ray normalization reconstructs arbitrary positive-branch coordinates within its stated uncertainty.
    """
    chart = build(reference(), checkpoint)
    assert chart.status == "qualified_intrinsic_cylinder_basis"
    for height in (Fraction(-7), Fraction(0), Fraction(10)):
        for ratio in (Fraction(-2), Fraction(0), Fraction(3)):
            projected = chart.project(height, ratio, checkpoint)
            decoded = chart.decode(projected.point, checkpoint)
            assert decoded.status == "within_intrinsic_coordinate_accuracy"
            assert decoded.height_mm == height and decoded.angular_ratio == ratio
            assert decoded.world_upper_mm is not None and decoded.world_upper_mm <= Fraction(1, 100)
            assert projected.error_upper_mm >= 0
    point = (Fraction(5), Fraction(3, 5), Fraction(4, 5))
    decoded = chart.decode(point, checkpoint)
    assert decoded.status == "within_intrinsic_coordinate_accuracy"
    assert decoded.height_mm.numerator == 5 and decoded.height_mm.denominator == 1
    assert decoded.angular_ratio is not None and decoded.angular_ratio.numerator == 0
    with pytest.raises(ValueError, match="SAME native reference"):
        replace(chart, reference=replace(chart.reference))


def test_negative_half_branch_and_off_support_points_are_not_silently_projected_to_pass() -> None:
    """
    Antipodal rays are distinct and a small world reconstruction error remains an explicit dimensional gate.
    """
    chart = build(reference(), checkpoint)
    behind = chart.decode((Fraction(0), Fraction(-1), Fraction(0)), checkpoint)
    assert behind.status == "unresolved_cylinder_branch" and behind.angular_ratio is None
    outside = chart.decode((Fraction(0), Fraction(2), Fraction(0)), checkpoint)
    assert outside.status == "unresolved_intrinsic_coordinate_accuracy"
    accepted = chart.decode((Fraction(0), Fraction(1001, 1000), Fraction(0)), checkpoint)
    assert accepted.status == "within_intrinsic_coordinate_accuracy"
    assert accepted.world_upper_mm is not None and accepted.world_upper_mm > 0


def test_reference_degeneracy_and_incompatible_support_remain_unresolved() -> None:
    """
    A cancelling reference cannot define an angular branch, and a wrong-radius arc cannot qualify by frame alone.
    """
    original = reference()
    opposite = replace(
        original,
        controls=(
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1)),
            (Fraction(0), Fraction(-1), Fraction(0)),
        ),
    )
    assert build(opposite, checkpoint).status == "unresolved_intrinsic_cylinder_basis"
    assert (
        build(
            replace(original, native=replace(original.native, radius_mm=Fraction(2))), checkpoint
        ).status
        == "unresolved_intrinsic_cylinder_basis"
    )


@pytest.mark.parametrize("reverse", (False, True))
def test_whole_cap_branch_is_monotone_in_both_original_curve_directions(reverse: bool) -> None:
    """
    The angular ratio uses rational homogeneous derivatives rather than sampled curve values or original edge angles.
    """
    original = reference()
    chart = build(original, checkpoint)
    curve = NativeCapCurve(original.native.revision, 7, original.controls, original.weights)
    if reverse:
        curve = replace(
            curve, controls=tuple(reversed(curve.controls)), weights=tuple(reversed(curve.weights))
        )
    proof = inspect_curve(chart, curve, checkpoint)
    assert proof.status == "qualified_monotone_cylinder_curve_branch"
    assert proof.radial_lower_mm > 0 and proof.angular_derivative_bounds is not None
    lower, upper = proof.angular_derivative_bounds
    assert upper < 0 if reverse else lower > 0
    with pytest.raises(ValueError, match="SAME intrinsic chart/curve"):
        replace(proof, curve=replace(curve))
    with pytest.raises(ValueError, match="SAME native cylinder revision"):
        inspect_curve(chart, replace(curve, revision="foreign"), checkpoint)


def test_whole_curve_hull_and_stationary_angular_progress_cannot_be_waived_by_endpoint_positions() -> (
    None
):
    """
    Off-branch control excursions and a returning angular trace stay unresolved despite acceptable endpoints.
    """
    original = reference()
    chart = build(original, checkpoint)
    back = NativeCapCurve(
        original.native.revision,
        7,
        (
            (Fraction(0), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(-2), Fraction(-2)),
            (Fraction(0), Fraction(0), Fraction(1)),
        ),
        (Fraction(1),) * 3,
    )
    assert inspect_curve(chart, back, checkpoint).status == "unresolved_cylinder_curve_branch"
    returning = replace(
        back, controls=(original.controls[0], original.controls[1], original.controls[0])
    )
    proof = inspect_curve(chart, returning, checkpoint)
    assert (
        proof.status == "unresolved_cylinder_curve_branch"
        and proof.angular_derivative_bounds is not None
    )
    assert proof.angular_derivative_bounds[0] <= 0 <= proof.angular_derivative_bounds[1]
    fast = replace(
        returning,
        controls=original.controls,
        weights=tuple(w * 100**i for i, w in enumerate(original.weights)),
    )
    progress = inspect_curve(chart, fast, checkpoint)
    assert progress.status == "unresolved_cylinder_curve_branch"
    assert (
        progress.angular_derivative_bounds is not None and progress.angular_derivative_bounds[0] > 0
    )


def test_caller_stop_prevents_intrinsic_coordinate_output() -> None:
    """
    Projection arithmetic and inverse recovery remain inside the caller's shared work allocation.
    """
    chart = build(reference(), checkpoint)
    calls = 0

    def stop() -> None:
        """
        Stop during inverse projection before a coordinate receipt is produced.
        """
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("intrinsic inverse stopped")

    with pytest.raises(RuntimeError, match="inverse stopped"):
        chart.decode((Fraction(0), Fraction(3, 5), Fraction(4, 5)), stop)
