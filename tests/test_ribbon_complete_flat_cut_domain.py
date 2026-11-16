"""
Check complete oblique-cut domains and one combined allowance without sourcecut movement.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_enclosure import NativeFaceBox
from experiments.experiment_ribbon_complete.flat_chart import (
    FlatCoordinateProof,
    MaterialCut,
    certify,
)
from experiments.experiment_ribbon_complete.flat_cut_domain import (
    CutSide,
    certify_domain,
    direction,
)
from tests.test_ribbon_complete_native_flat_cylinder import cylinder
from tests.test_ribbon_complete_native_flat_embedding import chart
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def fixture(extent: Fraction = Fraction(1, 2)) -> tuple[FlatCoordinateProof, NativeFaceBox]:
    """
    Enclose an oblique physical slab0<=s-q<=2 without losing its correlation in an axial box.
    """
    source = replace(
        chart(),
        low=MaterialCut(Fraction(0), Fraction(1)),
        high=MaterialCut(Fraction(2), Fraction(1)),
    )
    box = NativeFaceBox(
        cylinder(),
        "actual-face",
        (Fraction(1), Fraction(0), Fraction(0)),
        (
            (extent, -extent, Fraction(0)),
            (Fraction(1), Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1)),
        ),
    )
    return certify(source), box


def test_oblique_enclosure_bounds_both_whole_face_cuts_and_preserves_gradients() -> None:
    """
    Complete box extrema preserve the original slanted lower and upper planes.
    """
    frame, box = fixture()
    proof = certify_domain(frame, box, box, checkpoint)
    assert proof.status == "within_native_flat_longitudinal_domain"
    assert proof.minimum_gaps_mm == (Fraction(0), Fraction(0))
    assert direction(frame, CutSide.LOW) == (Fraction(1), Fraction(-1), Fraction(0))
    assert direction(frame, CutSide.HIGH) == (Fraction(-1), Fraction(1), Fraction(0))
    for point in (
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(2), Fraction(1), Fraction(1)),
        (Fraction(0), Fraction(-1), Fraction(-1)),
    ):
        s, q, _ = frame.chart.coordinates(point, frame)
        assert frame.chart.low.at(q) <= s <= frame.chart.high.at(q)
    with pytest.raises(ValueError, match="SAME owned"):
        replace(proof, excursion_upper_mm=Fraction(1))


@pytest.mark.parametrize(
    "extent,expected",
    [
        (Fraction(201, 400), "within_native_flat_longitudinal_domain"),
        (Fraction(503, 1000), "unresolved_native_flat_longitudinal_domain"),
    ],
)
def test_both_end_excursions_share_one_inclusive_allowance(extent: Fraction, expected: str) -> None:
    """
    Two individually small end bounds cannot receive separate0.01mm budgets.
    """
    frame, box = fixture(extent)
    proof = certify_domain(frame, box, box, checkpoint)
    assert proof.status == expected
    assert all(-Fraction(1, 100) <= gap < 0 for gap in proof.minimum_gaps_mm)
    assert proof.excursion_upper_mm == 4 * extent - 2
    assert frame.chart.low.offset.numerator == 0 and frame.chart.high.offset.numerator == 2


def test_foreign_owner_stale_frame_and_resource_stop_remain_rejected() -> None:
    """
    Neither unrelated face enclosures nor stale coordinate rows can transfer a domain pass.
    """
    frame, box = fixture()
    with pytest.raises(ValueError, match="SAME actual"):
        certify_domain(frame, box, replace(box, native=replace(box.native)), checkpoint)
    with pytest.raises(ValueError, match="SAME certified"):
        direction(replace(frame, condition_upper=Fraction(0)), CutSide.LOW)

    def stop() -> None:
        """
        Stop before performing domain work when the shared caller allocation is exhausted.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        certify_domain(frame, box, box, stop)
