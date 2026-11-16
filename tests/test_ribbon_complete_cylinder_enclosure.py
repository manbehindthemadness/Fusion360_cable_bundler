"""
Check entire-enclosure bounds, loose-box failures and source ownership without boundary conversion.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_coordinates import build
from experiments.experiment_ribbon_complete.cylinder_enclosure import (
    NativeFaceBox,
    certify_enclosure,
)
from tests.test_ribbon_complete_cylinder_coordinates import reference
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_rotated_enclosure_covers_interiors_and_rejects_stale_receipts() -> None:
    """
    A box in the intrinsic basis covers cylinder points for every height and angular ratio in its interior.
    """
    chart = build(reference(), checkpoint)
    a, e, f = chart.evidence.frame.columns
    center = tuple(chart.reference.native.origin[k] + 2 * e[k] for k in range(3))
    box = NativeFaceBox(
        chart.reference.native, "owned-face", center, (a, e, tuple(x / 2 for x in f))
    )
    proof = certify_enclosure(box, chart, checkpoint)
    assert proof.window.status == "certified_intrinsic_cylinder_window"
    assert proof.radial_lower_mm == Fraction(1)
    assert proof.window.maximum_abs_ratio == Fraction(1, 2)
    for h, t in (
        (Fraction(0), Fraction(0)),
        (Fraction(1, 2), Fraction(1, 5)),
        (Fraction(-1, 2), Fraction(-1, 5)),
    ):
        point = chart.project(h, t, checkpoint)
        height, x, y = chart.affine_coordinates(point.point)
        assert abs(height) <= 1
        assert 1 <= x <= 3
        assert abs(y) <= Fraction(1, 2)
        assert abs(y / x) <= proof.window.maximum_abs_ratio
    with pytest.raises(ValueError, match="SAME owned"):
        replace(proof, radial_lower_mm=Fraction(2))
    with pytest.raises(ValueError, match="SAME native"):
        certify_enclosure(replace(box, native=replace(box.native)), chart, checkpoint)


def test_loose_enclosure_and_singular_box_do_not_establish_face_failure() -> None:
    """
    Boxes crossing the negative branch cannot certify, even if an enclosed face might still be valid.
    """
    chart = build(reference(), checkpoint)
    axes = chart.evidence.frame.columns
    box = NativeFaceBox(chart.reference.native, "owned-face", chart.reference.native.origin, axes)
    with pytest.raises(ValueError, match="positive whole-curve"):
        certify_enclosure(box, chart, checkpoint)
    with pytest.raises(ValueError, match="nondegenerate"):
        replace(box, half_axes_mm=(axes[0], axes[0], axes[2]))
