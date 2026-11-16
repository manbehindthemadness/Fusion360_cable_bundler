"""
Verify composed domain errors share one allowance and retain valid zero-width source tips.
"""

from dataclasses import replace
from fractions import Fraction

from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain
from experiments.experiment_ribbon_complete.native_flat_domain import NativeFlatDomainAccuracy
from experiments.experiment_ribbon_complete.native_profile_accuracy import NativeProfileAccuracy
from tests.test_ribbon_complete_native_profile_accuracy import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def test_exact_profile_and_cuts_produce_one_original_domain_witness() -> None:
    """
    Exact component evidence composes without inventing a dimensional error or a new coordinate map.
    """
    conic, frame, box = fixture()
    profile = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    cuts = certify_frame_domain(frame, box, box, checkpoint)
    proof = NativeFlatDomainAccuracy(profile, cuts, checkpoint)
    assert proof.status == "within_native_original_flat_domain_accuracy"
    assert proof.distance_upper_mm is not None and proof.distance_upper_mm.numerator == 0


def test_individually_acceptable_components_cannot_double_the_allowance() -> None:
    """
    A conservative profile bound and two-end excursion can jointly exceed0.01mm despite passing separately.
    """
    conic, frame, box = fixture(radius=Fraction(10001, 10000))
    profile = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    wider = replace(
        box, half_axes_mm=((Fraction(2009, 2000), Fraction(0), Fraction(0)), *box.half_axes_mm[1:])
    )
    cuts = certify_frame_domain(frame, wider, wider, checkpoint)
    assert profile.status == "within_native_original_profile_accuracy"
    assert cuts.status == "within_native_flat_longitudinal_domain"
    proof = NativeFlatDomainAccuracy(profile, cuts, checkpoint)
    assert proof.status == "unresolved_native_original_flat_domain_accuracy"
    assert proof.distance_upper_mm is not None and proof.distance_upper_mm > Fraction(1, 100)


def test_zero_source_tip_is_retained_without_dividing_by_its_extent() -> None:
    """
    A source interval may close at its tip while the global affine coordinate field remains valid.
    """
    conic, frame, box = fixture()
    frame = replace(frame, high=MaterialCut(Fraction(1), Fraction(-1)))
    profile = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    proof = NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, box, box, checkpoint), checkpoint
    )
    assert proof.minimum_source_width_mm.numerator == 0
    assert proof.distance_upper_mm is not None
