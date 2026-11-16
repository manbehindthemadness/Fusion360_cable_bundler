"""
Account for omitted finite source sides by measured native junctions while retaining strict default coverage.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.boundary_cycle_candidates import BoundaryCycleCandidates
from experiments.experiment_ribbon_complete.boundary_traversal import (
    BoundaryTransitionBounds,
    BoundaryTraversalPolicy,
    junctions_sq,
)
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain
from experiments.experiment_ribbon_complete.material_polygon import MaterialPolygon
from experiments.experiment_ribbon_complete.native_boundary_distance import BoundarySide
from experiments.experiment_ribbon_complete.native_boundary_enclosure import (
    FiniteNativeBoundarySide,
    NativeEdgeBox,
)
from experiments.experiment_ribbon_complete.native_flat_domain import NativeFlatDomainAccuracy
from experiments.experiment_ribbon_complete.native_material_domain import NativeOuterLoop
from experiments.experiment_ribbon_complete.native_profile_accuracy import NativeProfileAccuracy
from experiments.experiment_ribbon_complete.native_surface_degree import NativeSurfaceDegreeCoverage
from experiments.experiment_ribbon_complete.profile_continuity import ProfileContinuity
from tests.test_ribbon_complete_native_material_domain import example
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def triangle(gap: Fraction) -> tuple[NativeOuterLoop, NativeFlatDomainAccuracy]:
    """
    Enclose an actual triangular cylinder strip beneath an unchanged quadrilateral source with a finite missing generator.
    """
    original, _, old_domain = example()
    first = original.sides[0]
    zero = Fraction(0)
    half_q, b = Fraction(3, 5), Fraction(4, 5)
    width = 2 * half_q + gap
    frame = replace(first.frame, high=MaterialCut(half_q + gap, Fraction(-1)))
    points = ((zero, -half_q, b), (width, -half_q, b), (zero, half_q, b))
    names = (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.LOW)
    sides = []
    for index, name in enumerate(names):
        if name is BoundarySide.END0:
            center = (width / 2, -half_q, b)
            axes = ((width / 2, zero, zero), (zero,) * 3, (zero,) * 3)
        else:
            center = (width / 2 if name is BoundarySide.HIGH else zero, zero, Fraction(9, 10))
            axes = (
                ((-width / 2 if name is BoundarySide.HIGH else zero), half_q, zero),
                (zero, zero, Fraction(1, 10)),
                (zero,) * 3,
            )
        box = NativeEdgeBox(
            native=first.box.native,
            face_token=first.box.face_token,
            edge_id=index,
            directed_vertices=(index, (index + 1) % 3),
            vertex_points_mm=(points[index], points[(index + 1) % 3]),
            center_mm=center,
            half_axes_mm=axes,
        )
        sides.append(FiniteNativeBoundarySide(box, frame, first.graph, name, checkpoint))
    loop = NativeOuterLoop(tuple(sides), 3, checkpoint)
    profile_box = old_domain.profile.boxes[0]
    profile = NativeProfileAccuracy(first.graph.conic, frame, (profile_box,), checkpoint)
    high_box = replace(
        profile_box,
        center_mm=(Fraction(3, 10) + gap / 4, Fraction(-3, 10) + gap / 4, Fraction(9, 10)),
        half_axes_mm=(
            (Fraction(9, 10) + gap / 4, -Fraction(9, 10) - gap / 4, zero),
            (Fraction(-3, 10) - gap / 4, Fraction(-3, 10) - gap / 4, zero),
            (zero, zero, Fraction(1, 10)),
        ),
    )
    domain = NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, profile_box, high_box, checkpoint), checkpoint
    )
    assert domain.distance_upper_mm == Fraction(0)
    return loop, domain


@pytest.mark.parametrize(
    "gap,qualified",
    [(Fraction(1, 10**12), True), (Fraction(1, 1000), False), (Fraction(1, 50), False)],
)
def test_finite_missing_side_is_fully_charged_and_strict_default_is_preserved(
    gap: Fraction, qualified: bool
) -> None:
    """
    A finite missing generator never becomes zero, and a small individual bridge may still fail the combined lift.
    """
    loop, domain = triangle(gap)
    continuity = ProfileContinuity(loop.sides[0].graph.conic, checkpoint)
    with pytest.raises(ValueError, match="exactly once cyclically"):
        NativeSurfaceDegreeCoverage(loop, continuity, domain, checkpoint)
    proof = NativeSurfaceDegreeCoverage(
        loop, continuity, domain, checkpoint, BoundaryTraversalPolicy.FINITE_BRIDGES
    )
    assert proof.boundary.omitted_source_sides == (BoundarySide.END1,)
    assert proof.boundary.collar_upper_mm == gap
    assert (proof.status == "qualified_native_surface_domain_by_degree") is qualified
    assert proof.forward_upper_mm == Fraction(0)
    assert proof.reverse_upper_mm > gap
    if gap == Fraction(1, 1000):
        assert all(side.status == "within_actual_native_finite_side" for side in loop.sides)
        assert proof.reverse_upper_mm > Fraction(1, 100)


def test_reverse_boundary_and_contiguous_splits_keep_the_same_bridge_bound() -> None:
    """
    Direction changes and native split coedges cannot erase the omitted source path or its cost.
    """
    loop, domain = triangle(Fraction(1, 10**12))
    polygon = MaterialPolygon(loop.sides[0].frame, loop.sides[0].graph)
    names = tuple(side.side for side in loop.sides)
    points = junctions_sq(
        loop.sides[0].frame, tuple(side.box.vertex_points_mm[1] for side in loop.sides)
    )
    forward = BoundaryTransitionBounds(
        polygon, names, points, BoundaryTraversalPolicy.FINITE_BRIDGES, checkpoint
    )
    reversed_sides = []
    for side in reversed(loop.sides):
        source_box = side.box
        reversed_box = replace(
            source_box,
            directed_vertices=(source_box.directed_vertices[1], source_box.directed_vertices[0]),
            vertex_points_mm=(source_box.vertex_points_mm[1], source_box.vertex_points_mm[0]),
        )
        reversed_sides.append(replace(side, box=reversed_box, checkpoint=checkpoint))
    backward_loop = NativeOuterLoop(tuple(reversed_sides), 3, checkpoint)
    proof = NativeSurfaceDegreeCoverage(
        backward_loop,
        ProfileContinuity(loop.sides[0].graph.conic, checkpoint),
        domain,
        checkpoint,
        BoundaryTraversalPolicy.FINITE_BRIDGES,
    )
    assert proof.boundary.collar_upper_mm == forward.corner_upper_mm
    split = BoundaryTransitionBounds(
        polygon,
        (names[0], names[1], names[1], names[2]),
        (points[0], points[0], points[1], points[2]),
        BoundaryTraversalPolicy.FINITE_BRIDGES,
        checkpoint,
    )
    assert split.corner_upper_mm == forward.corner_upper_mm


def test_unique_query_fallback_does_not_rank_multiple_complete_assignments() -> None:
    """
    Complete association stays strict by default; explicit bridge patterns may identify a missing source side.
    """
    loop, _ = triangle(Fraction(1, 10**12))
    polygon = MaterialPolygon(loop.sides[0].frame, loop.sides[0].graph)
    candidates = tuple((side.side,) for side in loop.sides)
    strict = BoundaryCycleCandidates(polygon, candidates, checkpoint)
    assert strict.assignment_count == 0
    fallback = BoundaryCycleCandidates(
        polygon, candidates, checkpoint, BoundaryTraversalPolicy.FINITE_BRIDGES
    )
    assert fallback.unique_assignment == tuple(side.side for side in loop.sides)
    ambiguous = BoundaryCycleCandidates(polygon, (tuple(BoundarySide),) * 4, checkpoint)
    assert ambiguous.assignment_count == 2 and ambiguous.unique_assignment is None


def test_wrong_order_and_two_side_groups_cannot_supply_a_source_winding_certificate() -> None:
    """
    Finite bridges retain one source traversal and cannot replace a missing face with a two-group trace.
    """
    loop, _ = triangle(Fraction(1, 10**12))
    polygon = MaterialPolygon(loop.sides[0].frame, loop.sides[0].graph)
    for sides in (
        (BoundarySide.LOW, BoundarySide.HIGH),
        (BoundarySide.END0, BoundarySide.END1, BoundarySide.HIGH, BoundarySide.LOW),
    ):
        with pytest.raises(ValueError, match="cyclic"):
            BoundaryTransitionBounds(
                polygon,
                sides,
                ((Fraction(0), Fraction(0)),) * len(sides),
                BoundaryTraversalPolicy.FINITE_BRIDGES,
                checkpoint,
            )


def test_missing_junctions_foreign_owners_and_expired_allocations_are_rejected() -> None:
    """
    A bridge never waives exact native/source ownership, complete junction data or the shared checkpoint.
    """
    loop, domain = triangle(Fraction(1, 10**12))
    polygon = MaterialPolygon(loop.sides[0].frame, loop.sides[0].graph)
    names = tuple(side.side for side in loop.sides)
    with pytest.raises(ValueError, match="Complete exact"):
        BoundaryTransitionBounds(
            polygon, names, (), BoundaryTraversalPolicy.FINITE_BRIDGES, checkpoint
        )
    other, _ = triangle(Fraction(1, 10**12))
    with pytest.raises(ValueError, match="SAME actual native"):
        NativeSurfaceDegreeCoverage(
            loop,
            ProfileContinuity(other.sides[0].graph.conic, checkpoint),
            domain,
            checkpoint,
            BoundaryTraversalPolicy.FINITE_BRIDGES,
        )

    def stop() -> None:
        """
        Refuse further work after allocation expiry.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        BoundaryTransitionBounds(polygon, names, (), BoundaryTraversalPolicy.FINITE_BRIDGES, stop)
