"""
Check exact material decoding and continuous noncancelling label-error transfer on native supports.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_coordinates import build
from experiments.experiment_ribbon_complete.cylinder_enclosure import (
    NativeFaceBox,
    certify_enclosure,
)
from experiments.experiment_ribbon_complete.native_flat_cylinder import enclose
from experiments.experiment_ribbon_complete.native_flat_embedding import certify
from experiments.experiment_ribbon_complete.native_flat_material import (
    FlatNativeMaterialField,
    bind,
)
from tests.test_ribbon_complete_cylinder_coordinates import reference
from tests.test_ribbon_complete_native_flat_cylinder import circle
from tests.test_ribbon_complete_native_flat_embedding import chart
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def field(shear: Fraction = Fraction(0)) -> FlatNativeMaterialField:
    """
    Retain an explicit affine material frame and its actual-style full cylinder-face enclosure.
    """
    original = chart()
    source = replace(original, columns=((Fraction(1), shear, Fraction(0)), *original.columns[1:]))
    ref = reference()
    arc = circle()
    support = enclose(source, arc, ref.native, 0, "revision", checkpoint)
    embedding = certify(support, checkpoint)
    intrinsic = build(ref, checkpoint)
    a, e, f = intrinsic.evidence.frame.columns
    box = NativeFaceBox(
        ref.native,
        "native-face",
        tuple(2 * x for x in e),
        (tuple(2 * x for x in a), e, tuple(x / 2 for x in f)),
    )
    return bind(embedding, certify_enclosure(box, intrinsic, checkpoint), checkpoint)


def test_actual_native_points_decode_without_uv_or_longitudinal_normalization() -> None:
    """
    The same physical affine inverse recovers native points and exactly reconstructs their world positions.
    """
    result = field()
    assert result.status == "qualified_flat_native_material_field"
    for s in (Fraction(0), Fraction(1), Fraction(2)):
        point = s, Fraction(3, 5), Fraction(4, 5)
        material = result.coordinates(point)
        assert material == point
        assert result.embedding.support.chart.point(*material) == point
    assert result.complete_increment_upper_mm.numerator == 0


def test_small_source_axis_drift_bounds_combined_labels_and_every_increment() -> None:
    """
    A nonzero radial source drift cannot disappear through cancellation or small endpoint position errors.
    """
    shear = Fraction(1, 1000000)
    result = field(shear)
    assert result.status == "qualified_flat_native_material_field"
    assert result.increment_error_rate > 0
    for start, stop in (
        (Fraction(0), Fraction(2)),
        (Fraction(1, 4), Fraction(3, 4)),
        (Fraction(1), Fraction(2)),
    ):
        first = result.coordinates((start, Fraction(1), Fraction(0)))
        last = result.coordinates((stop, Fraction(1), Fraction(0)))
        # The V=0 source ray projects exactly onto this unit-cylinder generator.
        assert first == (start, 1 - shear * start, Fraction(0))
        assert last == (stop, 1 - shear * stop, Fraction(0))
        label_error = sum(abs(a - b) for a, b in zip(last, (stop, Fraction(1), Fraction(0))))
        increment_error = sum(
            abs(b - a - expected)
            for a, b, expected in zip(first, last, (stop - start, Fraction(0), Fraction(0)))
        )
        assert label_error <= result.label_error_upper_mm
        assert (
            increment_error
            <= result.increment_error_rate * (stop - start)
            <= result.complete_increment_upper_mm
        )


def test_stale_bounds_foreign_native_face_and_resource_stop_are_rejected() -> None:
    """
    Derived label receipts cannot be transferred or created after their caller's allocation stops.
    """
    result = field()
    with pytest.raises(ValueError, match="SAME owned"):
        replace(result, label_error_upper_mm=result.label_error_upper_mm + 1)
    with pytest.raises(ValueError, match="SAME qualified"):
        replace(result, frame=replace(result.frame, condition_upper=Fraction(0)))
    with pytest.raises(ValueError, match="SAME owned"):
        bind(result.embedding, field().native_face, checkpoint)

    def stop() -> None:
        """
        Refuse any new coordinate qualification after the shared allocation stops.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        bind(result.embedding, result.native_face, stop)
