"""
Exercise endpoint-only cut-frame invariants independently of full bend source construction.
"""

from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_chart import FlatRegion, MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import (
    CutSide,
    FlatCutFrame,
    certify_frame_domain,
    frame_direction,
)
from tests.test_ribbon_complete_flat_cut_domain import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_metadata_only_cut_frame_retains_original_oblique_inequalities() -> None:
    """
    Explicit affine metadata suffices for whole-face cut bounds without constructing a bend tensor.
    """
    _, box = fixture()
    zero, one = Fraction(0), Fraction(1)
    frame = FlatCutFrame(
        FlatRegion.STRAIGHT,
        (zero,) * 3,
        ((one, zero, zero), (zero, one, zero), (zero, zero, one)),
        MaterialCut(zero, one),
        MaterialCut(Fraction(2), one),
    )
    assert frame_direction(frame, CutSide.LOW) == (one, -one, zero)
    proof = certify_frame_domain(frame, box, box, checkpoint)
    assert proof.status == "within_native_flat_longitudinal_domain"
    assert proof.minimum_gaps_mm == (zero, zero)


@pytest.mark.parametrize("scale", [Fraction(0), Fraction(1, 2048)])
def test_metadata_port_does_not_waive_invertibility_or_conditioning(scale: Fraction) -> None:
    """
    An incomplete or excessively compressed affine field cannot qualify merely because its metadata are exact.
    """
    zero, one = Fraction(0), Fraction(1)
    with pytest.raises(ValueError, match="Positive conditioned"):
        FlatCutFrame(
            FlatRegion.STRAIGHT,
            (zero,) * 3,
            ((one, zero, zero), (zero, scale, zero), (zero, zero, one)),
            MaterialCut(zero),
            MaterialCut(one),
        )
