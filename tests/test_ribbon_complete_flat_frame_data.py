"""
Check endpoint-only affine arithmetic independently of any bend tensor or span extraction.
"""

from dataclasses import replace
from fractions import Fraction

from experiments.experiment_ribbon_complete.flat_chart import (
    FlatRegion,
    LeadFrameData,
    lead_components,
)
from experiments.experiment_ribbon_complete.volume_field import bend_columns


def test_endpoint_metadata_alone_preserves_both_original_lead_frames() -> None:
    """
    Exact bank and endpoint scalars determine the original affine continuation without a midsurface object.
    """
    forward = Fraction(1), Fraction(0), Fraction(0)
    across = Fraction(0), Fraction(1), Fraction(0)
    data = LeadFrameData(
        (Fraction(5), Fraction(6), Fraction(7)),
        forward,
        bend_columns(forward, across, Fraction(3, 5), Fraction(4, 5)),
        Fraction(3, 5),
        Fraction(4, 5),
        Fraction(3),
        Fraction(2),
        Fraction(1),
        Fraction(0),
        Fraction(1),
        1,
    )
    before = lead_components(data, FlatRegion.BEFORE, Fraction(10))
    after = lead_components(data, FlatRegion.AFTER, Fraction(10))
    assert before[0] == data.origin
    assert before[1] == (forward, across, (Fraction(0), Fraction(0), Fraction(1)))
    assert before[2].offset.numerator == 0
    assert before[3].offset == Fraction(2) and before[3].slope == Fraction(-4, 3)
    assert after[0] == (Fraction(16, 5), Fraction(18, 5), Fraction(7))
    assert after[1] == before[1]
    assert after[2].offset == Fraction(7) and after[2].slope == Fraction(-4, 3)
    assert after[3].offset == Fraction(10)
    tiny = replace(
        data, before_mm=Fraction(1) - Fraction(1, 10**15), cosine=Fraction(1), sine=Fraction(1)
    )
    assert lead_components(tiny, FlatRegion.BEFORE, Fraction(10))[3].at(Fraction(1)) == -Fraction(
        1, 10**15
    )


def test_raw_bank_frame_does_not_normalize_captured_nonunit_coefficients() -> None:
    """
    Magnitude and nonunit scalar data remain part of the original affine field.
    """
    result = bend_columns(
        (Fraction(2), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(3), Fraction(0)),
        Fraction(1),
        Fraction(1, 10),
    )
    assert result == (
        (Fraction(2), Fraction(3, 10), Fraction(0)),
        (Fraction(-1, 5), Fraction(3), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(6)),
    )
