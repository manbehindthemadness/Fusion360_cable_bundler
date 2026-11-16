"""
Check original cut/profile intersections without source edits, zero rounding or independent error allowances.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.clipped_flat_domain import (
    ClippedNativeFlatDomainAccuracy,
    ClippedProfileDomain,
)
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain
from experiments.experiment_ribbon_complete.material_polygon import MaterialPolygon
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from experiments.experiment_ribbon_complete.native_flat_domain import NativeFlatDomainAccuracy
from experiments.experiment_ribbon_complete.native_material_domain import NativeOuterLoop
from experiments.experiment_ribbon_complete.native_profile_accuracy import NativeProfileAccuracy
from experiments.experiment_ribbon_complete.native_surface_degree import NativeSurfaceDegreeCoverage
from experiments.experiment_ribbon_complete.profile_continuity import (
    ProfileContinuity,
    ordered_profile_q,
)
from tests.test_ribbon_complete_native_surface_degree import cap_domain
from tests.test_ribbon_complete_profile_continuity import cap
from tests.test_ribbon_complete_volume_injectivity import checkpoint


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_cut_intersection_retains_original_conic_and_direction(reverse: bool) -> None:
    """
    Signed cut roots clip the source domain rather than replacing its original profile or rounding a negative width.
    """
    loop, _, _ = cap_domain()
    continuity = ProfileContinuity(cap(reverse=reverse), checkpoint)
    frame = replace(loop.sides[0].frame, high=MaterialCut(Fraction(9, 10), Fraction(-1)))
    clipped = ClippedProfileDomain(continuity, frame, checkpoint)
    assert clipped.conic is continuity.conic
    assert clipped.frame is frame
    assert clipped.interval == (Fraction(7, 25), Fraction(9, 10))
    assert clipped.minimum_source_width_mm == Fraction(0)
    assert clipped.witness_q_shift_mm == Fraction(1, 10)
    assert ordered_profile_q(clipped) == (
        (Fraction(7, 25), Fraction(9, 10)) if reverse else (Fraction(9, 10), Fraction(7, 25))
    )
    polygon = MaterialPolygon(frame, clipped)
    zero_tip = BoundarySide.END1 if reverse else BoundarySide.END0
    polygon.validate_sides(
        tuple(
            side
            for side in (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
            if side is not zero_tip
        )
    )
    assert polygon.inradius_mm > 0


def test_positive_width_slope_clips_the_other_end_without_changing_constraints() -> None:
    """
    Both signs of the affine width use their exact half-line intersection.
    """
    loop, continuity, _ = cap_domain()
    frame = replace(loop.sides[0].frame, high=MaterialCut(Fraction(-1, 2), Fraction(1)))
    clipped = ClippedProfileDomain(continuity, frame, checkpoint)
    assert clipped.interval == (Fraction(1, 2), Fraction(1))
    assert clipped.witness_q_shift_mm == Fraction(11, 50)


@pytest.mark.parametrize(
    "cut",
    [
        MaterialCut(Fraction(-1)),
        MaterialCut(Fraction(0)),
        MaterialCut(Fraction(7, 25), Fraction(-1)),
    ],
)
def test_empty_or_lower_dimensional_domains_are_not_rounded_into_source_faces(
    cut: MaterialCut,
) -> None:
    """
    No area remains for a native face when the original inequalities exclude the full interval or retain only a tip.
    """
    loop, continuity, _ = cap_domain()
    with pytest.raises(ValueError, match="original clipped profile domain"):
        ClippedProfileDomain(continuity, replace(loop.sides[0].frame, high=cut), checkpoint)


@pytest.mark.parametrize(
    "epsilon,accepted", [(Fraction(1, 10**16), True), (Fraction(1, 10000), False)]
)
def test_negative_tip_width_gets_an_explicit_joint_witness_cost(
    epsilon: Fraction, accepted: bool
) -> None:
    """
    A native triangular cap uses its original cuts; the clipping and longitudinal costs share one0.01mm allowance.
    """
    loop, continuity, old_domain = cap_domain()
    frame = replace(loop.sides[0].frame, high=MaterialCut(1 - epsilon, Fraction(-1)))
    old_box = old_domain.profile.boxes[0]
    profile = NativeProfileAccuracy(continuity.conic, frame, (old_box,), checkpoint)
    # This parallelepiped encloses the triangular strip s>=0, s+q<=1.
    high_box = replace(
        old_box,
        center_mm=(Fraction(9, 50), Fraction(23, 50), Fraction(12, 25)),
        half_axes_mm=(
            (Fraction(27, 50), Fraction(-27, 50), Fraction(0)),
            (Fraction(-9, 50), Fraction(-9, 50), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(12, 25)),
        ),
    )
    cuts = certify_frame_domain(frame, old_box, high_box, checkpoint)
    old = NativeFlatDomainAccuracy(profile, cuts, checkpoint)
    assert old.distance_upper_mm is None
    clipped = ClippedProfileDomain(continuity, frame, checkpoint)
    proof = ClippedNativeFlatDomainAccuracy(profile, cuts, clipped, checkpoint)
    assert clipped.witness_q_shift_mm == epsilon
    assert proof.distance_upper_mm is not None
    assert proof.distance_upper_mm == continuity.variation(epsilon) + 3 * epsilon
    assert (proof.status == "within_native_original_flat_domain_accuracy") is accepted


def test_unclipped_native_bounds_are_exact_and_degree_ownership_is_preserved() -> None:
    """
    Existing positive-width evidence is unchanged, while a foreign clipping domain cannot grant coverage.
    """
    loop, continuity, old = cap_domain()
    clipped = ClippedProfileDomain(continuity, loop.sides[0].frame, checkpoint)
    domain = ClippedNativeFlatDomainAccuracy(old.profile, old.cuts, clipped, checkpoint)
    assert domain.distance_upper_mm == old.distance_upper_mm == 0
    updated = NativeOuterLoop(
        tuple(replace(side, graph=clipped, checkpoint=checkpoint) for side in loop.sides),
        4,
        checkpoint,
    )
    assert (
        NativeSurfaceDegreeCoverage(updated, continuity, domain, checkpoint).status
        == "qualified_native_surface_domain_by_degree"
    )
    with pytest.raises(ValueError, match="SAME actual native"):
        NativeSurfaceDegreeCoverage(loop, continuity, domain, checkpoint)
    with pytest.raises(ValueError, match="SAME original clipped"):
        ClippedNativeFlatDomainAccuracy(
            old.profile,
            old.cuts,
            replace(clipped, frame=replace(clipped.frame), checkpoint=checkpoint),
            checkpoint,
        )


def test_clipped_domain_work_observes_the_shared_resource_stop() -> None:
    """
    Exact interval intersection does not create a new recovery or audit allocation.
    """
    loop, continuity, _ = cap_domain()

    def stop() -> None:
        """
        Refuse further proof work after allocation expiry.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        ClippedProfileDomain(continuity, loop.sides[0].frame, stop)
