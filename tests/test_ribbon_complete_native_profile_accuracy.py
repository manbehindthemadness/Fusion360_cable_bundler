"""
Distinguish uniform branch-aware profile distance from small implicit residuals and unsupported conics.
"""

from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from experiments.experiment_ribbon_complete.cylinder_enclosure import NativeFaceBox
from experiments.experiment_ribbon_complete.flat_chart import FlatRegion, MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import FlatCutFrame
from experiments.experiment_ribbon_complete.native_profile_accuracy import (
    NativeProfileAccuracy,
    chord_gradient,
)
from experiments.experiment_ribbon_complete.profile_conic import EllipseArc
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_native_flat_cylinder import cylinder
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def fixture(
    radius: Fraction = Fraction(1), branch: int = 1
) -> tuple[EllipseArc, FlatCutFrame, NativeFaceBox]:
    """
    Enclose a complete exact rational106-degree unit-circle arc or its opposite branch.
    """
    data: Any = (
        (
            (Fraction(1), Fraction(0)),
            (Fraction(1), Fraction(4, 3)),
            (Fraction(-7, 25), Fraction(24, 25)),
        ),
        (Fraction(1), Fraction(3, 5), Fraction(1)),
        "circle",
    )
    conic = EllipseArc(MaterialArc(*data))
    zero, one = Fraction(0), Fraction(1)
    frame = FlatCutFrame(
        FlatRegion.STRAIGHT,
        (zero,) * 3,
        ((one, zero, zero), (zero, one, zero), (zero, zero, one)),
        MaterialCut(zero),
        MaterialCut(Fraction(2)),
    )
    box = NativeFaceBox(
        replace(cylinder(), radius_mm=radius),
        "native-face",
        (one, branch * radius * Fraction(12, 25), branch * radius * Fraction(16, 25)),
        (
            (one, zero, zero),
            (zero, radius * Fraction(3, 25), radius * Fraction(4, 25)),
            (zero, -radius * Fraction(16, 25), radius * Fraction(12, 25)),
        ),
    )
    return conic, frame, box


def test_exact_whole_arc_has_zero_residual_and_distance_without_native_uv() -> None:
    """
    An exact circle conic and complete enclosing box qualify without point-grid or parameter correspondence.
    """
    conic, frame, box = fixture()
    assert chord_gradient(conic, frame) == (Fraction(0), Fraction(24, 25), Fraction(32, 25))
    proof = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    assert proof.status == "within_native_original_profile_accuracy"
    assert proof.implicit_residual_upper.numerator == 0
    assert proof.distance_upper_mm is not None and proof.distance_upper_mm.numerator == 0
    assert conic.center == (Fraction(0), Fraction(0))
    assert conic.chord_offset > 0 and conic.angular_scale_squared > 0


def test_zero_residual_wrong_arc_and_large_distance_do_not_receive_profile_passes() -> None:
    """
    The opposite circle arc has identical implicit support, while a radius mismatch can have the correct branch.
    """
    conic, frame, box = fixture(branch=-1)
    wrong = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    assert wrong.implicit_residual_upper.numerator == 0
    assert wrong.status == "unresolved_native_original_profile_accuracy"
    assert wrong.distance_upper_mm is None
    conic, frame, box = fixture(radius=Fraction(51, 50))
    mismatch = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    assert mismatch.status == "unresolved_native_original_profile_accuracy"
    assert mismatch.distance_upper_mm is not None and mismatch.distance_upper_mm > Fraction(1, 100)


@pytest.mark.parametrize(
    "points,weights",
    [
        (((0, 0), (1, 0), (2, 0)), (1, 1, 1)),
        (((1, 0), (1, 1), (0, 1)), (1, 2, 1)),
        (((1, 0), (1, 1), (0, 1)), (1, 0, 1)),
    ],
)
def test_unsupported_profile_cannot_gain_acceptance_from_a_residual(
    points: Any, weights: Any
) -> None:
    """
    Collinear, nonelliptic and nonpositive-weight profiles require another qualified method.
    """
    with pytest.raises(ValueError):
        EllipseArc(MaterialArc(points, weights, "circle"))


def test_coordinate_field_and_source_ownership_survive_while_resource_stop_is_honored() -> None:
    """
    Proof witnesses never change source data, and new derived receipts cannot bypass the caller's budget.
    """
    conic, frame, box = fixture()
    with pytest.raises(ValueError, match="SAME original"):
        NativeProfileAccuracy(
            conic,
            frame,
            (replace(box, native=replace(box.native, profile_label="foreign")),),
            checkpoint,
        )

    def stop() -> None:
        """
        Refuse work before residual evaluation after the caller's allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeProfileAccuracy(conic, frame, (box,), stop)
    assert box.native.radius_mm == Fraction(1) and conic.arc.label == "circle"


def test_affine_ellipse_under_shear_uses_the_same_uniform_world_support_proof() -> None:
    """
    A noncircular material profile and nonorthogonal frame still reproduce the exact captured world cylinder.
    """
    original, frame, box = fixture()
    controls: Any = tuple(
        (Fraction(q) / 2 + Fraction(b) / 4, 2 * Fraction(b)) for q, b in original.arc.controls
    )
    ellipse = EllipseArc(MaterialArc(controls, original.arc.weights, original.arc.label))
    changed = replace(
        frame,
        columns=(
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(2), Fraction(0)),
            (Fraction(0), Fraction(-1, 4), Fraction(1, 2)),
        ),
    )
    proof = NativeProfileAccuracy(ellipse, changed, (box,), checkpoint)
    assert proof.status == "within_native_original_profile_accuracy"
    assert proof.implicit_residual_upper.numerator == 0
    assert proof.distance_upper_mm is not None and proof.distance_upper_mm.numerator == 0
