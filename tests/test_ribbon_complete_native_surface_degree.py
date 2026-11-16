"""
Separate native filled-domain existence from strict projection conditioning at stationary profile tips.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.cylinder_enclosure import NativeFaceBox
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from experiments.experiment_ribbon_complete.native_boundary_enclosure import (
    FiniteNativeBoundarySide,
    NativeEdgeBox,
)
from experiments.experiment_ribbon_complete.native_cylinder_projection import (
    ActualCylinderProjection,
)
from experiments.experiment_ribbon_complete.native_flat_domain import NativeFlatDomainAccuracy
from experiments.experiment_ribbon_complete.native_material_domain import (
    NativeMaterialDomainCoverage,
    NativeOuterLoop,
)
from experiments.experiment_ribbon_complete.native_profile_accuracy import NativeProfileAccuracy
from experiments.experiment_ribbon_complete.native_surface_degree import NativeSurfaceDegreeCoverage
from experiments.experiment_ribbon_complete.profile_continuity import ProfileContinuity
from tests.test_ribbon_complete_native_material_domain import example
from tests.test_ribbon_complete_native_profile_accuracy import fixture
from tests.test_ribbon_complete_profile_continuity import cap
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def cap_domain() -> tuple[NativeOuterLoop, ProfileContinuity, NativeFlatDomainAccuracy]:
    """
    Enclose a true circular cap whose original b coordinate is doubled and whose native q projection has zero tip derivative.
    """
    _, frame, old_box = fixture()
    zero, one, two = Fraction(0), Fraction(1), Fraction(2)
    conic = cap()
    graph = ProfileContinuity(conic, checkpoint)
    frame = replace(
        frame, columns=(frame.columns[0], frame.columns[1], (zero, zero, Fraction(1, 2)))
    )
    native = replace(old_box.native, profile_label=conic.arc.label)
    box = NativeFaceBox(
        native,
        "native-cap",
        (one, Fraction(18, 25), Fraction(27, 50)),
        (
            (one, zero, zero),
            (zero, Fraction(2, 25), Fraction(3, 50)),
            (zero, Fraction(-9, 25), Fraction(12, 25)),
        ),
    )
    points = (
        (zero, one, zero),
        (two, one, zero),
        (two, Fraction(7, 25), Fraction(24, 25)),
        (zero, Fraction(7, 25), Fraction(24, 25)),
    )
    sides = []
    names = (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
    for index, side in enumerate(names):
        if side in (BoundarySide.LOW, BoundarySide.HIGH):
            center = (zero if side is BoundarySide.LOW else two, Fraction(16, 25), Fraction(12, 25))
            axes = (
                (zero, Fraction(9, 25), zero),
                (zero, zero, Fraction(12, 25)),
                (zero, zero, zero),
            )
        else:
            center = (one, points[index][1], points[index][2])
            axes = ((one, zero, zero), (zero, zero, zero), (zero, zero, zero))
        edge = NativeEdgeBox(
            native=native,
            face_token=box.face_token,
            edge_id=index,
            directed_vertices=(index, (index + 1) % 4),
            vertex_points_mm=(points[index], points[(index + 1) % 4]),
            center_mm=center,
            half_axes_mm=axes,
        )
        sides.append(FiniteNativeBoundarySide(edge, frame, graph, side, checkpoint))
    loop = NativeOuterLoop(tuple(sides), 4, checkpoint)
    profile = NativeProfileAccuracy(conic, frame, (box,), checkpoint)
    domain = NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, box, box, checkpoint), checkpoint
    )
    return loop, graph, domain


def test_stationary_cap_coverage_does_not_grant_a_material_map_pass() -> None:
    """
    A zero projection derivative does not obstruct existence coverage, and the strict inverse gate remains unresolved.
    """
    loop, continuity, domain = cap_domain()
    proof = NativeSurfaceDegreeCoverage(loop, continuity, domain, checkpoint)
    assert domain.status == "within_native_original_flat_domain_accuracy"
    assert proof.status == "qualified_native_surface_domain_by_degree"
    assert proof.forward_upper_mm == proof.reverse_upper_mm == Fraction(0)
    projection = ActualCylinderProjection(loop.sides[0].frame, domain.profile.boxes, checkpoint)
    assert projection.status == "unresolved_actual_native_sq_projection"
    with pytest.raises(ValueError, match="finite-slope"):
        NativeMaterialDomainCoverage(loop, projection, domain, checkpoint)


def test_both_boundary_orientations_preserve_the_same_degree_coverage() -> None:
    """
    Reversing every directed coedge changes winding sign without changing its nonzero magnitude or source identity.
    """
    loop, continuity, domain = cap_domain()
    reversed_sides = tuple(
        replace(
            side,
            box=replace(
                side.box,
                directed_vertices=(side.box.directed_vertices[1], side.box.directed_vertices[0]),
                vertex_points_mm=(side.box.vertex_points_mm[1], side.box.vertex_points_mm[0]),
            ),
            checkpoint=checkpoint,
        )
        for side in reversed(loop.sides)
    )
    reversed_loop = NativeOuterLoop(reversed_sides, 4, checkpoint)
    proof = NativeSurfaceDegreeCoverage(reversed_loop, continuity, domain, checkpoint)
    assert proof.status == "qualified_native_surface_domain_by_degree"
    assert proof.reverse_upper_mm == Fraction(0)


def test_positive_forward_witness_is_charged_with_the_source_continuity_lift() -> None:
    """
    Small actual native radius mismatch remains visible in both directions rather than being cancelled by winding.
    """
    loop, _, domain = example(Fraction(1000001, 1000000))
    proof = NativeSurfaceDegreeCoverage(
        loop, ProfileContinuity(loop.sides[0].graph.conic, checkpoint), domain, checkpoint
    )
    assert proof.forward_upper_mm > 0
    assert proof.reverse_upper_mm > proof.forward_upper_mm
    assert proof.status == "qualified_native_surface_domain_by_degree"


def test_small_individual_side_tubes_cannot_waive_the_combined_reverse_allowance() -> None:
    """
    The square-root lift can exceed0.01mm even while every individual source-side tube is acceptable.
    """
    loop, continuity, domain = cap_domain()
    last = loop.sides[-1]
    changed = replace(
        last,
        box=replace(
            last.box,
            half_axes_mm=(
                *last.box.half_axes_mm[:2],
                (Fraction(1, 10000), Fraction(0), Fraction(0)),
            ),
        ),
        checkpoint=checkpoint,
    )
    assert changed.status == "within_actual_native_finite_side"
    updated = NativeOuterLoop((*loop.sides[:-1], changed), 4, checkpoint)
    proof = NativeSurfaceDegreeCoverage(updated, continuity, domain, checkpoint)
    assert proof.reverse_upper_mm > Fraction(1, 100)
    assert proof.status == "unresolved_native_surface_domain_by_degree"


def test_foreign_continuity_native_domains_and_repeated_boundaries_are_rejected() -> None:
    """
    Numerical coincidence does not replace original source/native ownership or one complete source-side traversal.
    """
    loop, continuity, domain = cap_domain()
    other_loop, other_continuity, other_domain = cap_domain()
    for foreign in ((other_continuity, domain), (continuity, other_domain)):
        with pytest.raises(ValueError, match="SAME actual native"):
            NativeSurfaceDegreeCoverage(loop, *foreign, checkpoint)
    with pytest.raises(ValueError, match="SAME actual native"):
        NativeSurfaceDegreeCoverage(other_loop, continuity, domain, checkpoint)
    repeated = NativeOuterLoop(loop.sides * 2, 8, checkpoint)
    with pytest.raises(ValueError, match="exactly once cyclically"):
        NativeSurfaceDegreeCoverage(repeated, continuity, domain, checkpoint)


def test_native_degree_audit_observes_the_shared_resource_stop() -> None:
    """
    Topological existence does not grant an independent audit or recovery reserve.
    """
    loop, continuity, domain = cap_domain()

    def stop() -> None:
        """
        Refuse further evaluation after allocation expiry.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeSurfaceDegreeCoverage(loop, continuity, domain, stop)
