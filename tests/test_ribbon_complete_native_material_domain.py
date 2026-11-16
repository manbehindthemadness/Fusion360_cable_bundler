"""
Check direct native filled coverage against incomplete topology, shared error allowances and foreign proofs.
"""

from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from experiments.experiment_ribbon_complete.cylinder_enclosure import NativeFaceBox
from experiments.experiment_ribbon_complete.flat_chart import MaterialCut
from experiments.experiment_ribbon_complete.flat_cut_domain import certify_frame_domain
from experiments.experiment_ribbon_complete.material_polygon import MaterialPolygon
from experiments.experiment_ribbon_complete.native_boundary_distance import (
    BoundarySide,
    ProfileGraph,
)
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
from experiments.experiment_ribbon_complete.profile_conic import EllipseArc
from experiments.experiment_ribbon_fold_route.material_profile import MaterialArc
from tests.test_ribbon_complete_native_profile_accuracy import fixture
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def example(
    radius: Fraction = Fraction(1),
) -> tuple[NativeOuterLoop, ActualCylinderProjection, NativeFlatDomainAccuracy]:
    """
    Enclose an exact native circular strip and its four original finite source sides.
    """
    _, frame, old_box = fixture()
    zero, one, two = Fraction(0), Fraction(1), Fraction(2)
    data: Any = (
        (
            (Fraction(-3, 5), Fraction(4, 5)),
            (zero, Fraction(5, 4)),
            (Fraction(3, 5), Fraction(4, 5)),
        ),
        (one, Fraction(4, 5), one),
        "circle",
    )
    graph = ProfileGraph(EllipseArc(MaterialArc(*data)), checkpoint)
    native = replace(old_box.native, radius_mm=radius)
    face_box = NativeFaceBox(
        native,
        old_box.face_token,
        (one, zero, radius * Fraction(9, 10)),
        (
            (one, zero, zero),
            (zero, radius * Fraction(3, 5), zero),
            (zero, zero, radius * Fraction(1, 10)),
        ),
    )
    points = (
        (zero, -radius * Fraction(3, 5), radius * Fraction(4, 5)),
        (two, -radius * Fraction(3, 5), radius * Fraction(4, 5)),
        (two, radius * Fraction(3, 5), radius * Fraction(4, 5)),
        (zero, radius * Fraction(3, 5), radius * Fraction(4, 5)),
    )
    side_names = (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
    sides = []
    for i, name in enumerate(side_names):
        if name in (BoundarySide.LOW, BoundarySide.HIGH):
            center = (zero if name is BoundarySide.LOW else two, zero, radius * Fraction(9, 10))
            axes = (
                (zero, radius * Fraction(3, 5), zero),
                (zero, zero, radius * Fraction(1, 10)),
                (zero,) * 3,
            )
        else:
            center = (one, points[i][1], radius * Fraction(4, 5))
            axes = ((one, zero, zero), (zero,) * 3, (zero,) * 3)
        box = NativeEdgeBox(
            native,
            face_box.face_token,
            i,
            (i, (i + 1) % 4),
            (points[i], points[(i + 1) % 4]),
            center,
            axes,
        )
        sides.append(FiniteNativeBoundarySide(box, frame, graph, name, checkpoint))
    loop = NativeOuterLoop(tuple(sides), 4, checkpoint)
    projection = ActualCylinderProjection(frame, (face_box,), checkpoint)
    profile = NativeProfileAccuracy(graph.conic, frame, (face_box,), checkpoint)
    domain = NativeFlatDomainAccuracy(
        profile, certify_frame_domain(frame, face_box, face_box, checkpoint), checkpoint
    )
    return loop, projection, domain


def test_exact_actual_native_domain_has_zero_bidirectional_material_error() -> None:
    """
    The complete original native loop and qualified coordinate/domain components produce actual filled coverage.
    """
    loop, projection, domain = example()
    proof = NativeMaterialDomainCoverage(loop, projection, domain, checkpoint)
    assert proof.status == "qualified_actual_native_material_domain"
    assert proof.collar_upper_mm == proof.forward_upper_mm == proof.reverse_upper_mm == Fraction(0)


def test_exact_zero_tip_can_omit_its_degenerate_side_without_omitting_a_finite_side() -> None:
    """
    A triangular source retains its corner and side order whether the SDK emits a point edge at that tip or not.
    """
    loop, _, _ = example()
    first = loop.sides[0]
    frame = replace(first.frame, high=MaterialCut(-first.graph.interval[0], Fraction(1)))
    polygon = MaterialPolygon(frame, first.graph)
    polygon.validate_sides((BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW))
    polygon.validate_sides(
        (BoundarySide.END0, BoundarySide.HIGH, BoundarySide.END1, BoundarySide.LOW)
    )
    assert polygon.corner(BoundarySide.LOW, BoundarySide.HIGH) == (
        Fraction(0),
        first.graph.interval[0],
    )
    with pytest.raises(ValueError, match="exactly once cyclically"):
        polygon.validate_sides((BoundarySide.HIGH, BoundarySide.LOW))


def test_positive_native_to_source_error_is_charged_in_the_reverse_bound() -> None:
    """
    A slightly larger real cylinder retains both its source-witness error and its planar coverage discrepancy.
    """
    loop, projection, domain = example(Fraction(1000001, 1000000))
    proof = NativeMaterialDomainCoverage(loop, projection, domain, checkpoint)
    assert proof.status == "qualified_actual_native_material_domain"
    assert proof.forward_upper_mm > 0 and proof.planar_reverse_upper_mm > 0
    assert proof.reverse_upper_mm > proof.forward_upper_mm
    assert proof.reverse_upper_mm == proof.forward_upper_mm + proof.source_lipschitz * (
        proof.planar_reverse_upper_mm + proof.forward_upper_mm
    )


def test_individual_side_accuracy_cannot_replace_the_filled_reverse_allowance() -> None:
    """
    A loose but valid enclosure can leave every side below0.01 while the combined reverse proof remains unresolved.
    """
    loop, projection, domain = example()
    side = loop.sides[-1]
    extra = (Fraction(3, 1000), Fraction(0), Fraction(0))
    changed_box = replace(side.box, half_axes_mm=(*side.box.half_axes_mm[:2], extra))
    changed = replace(side, box=changed_box, checkpoint=checkpoint)
    assert changed.status == "within_actual_native_finite_side"
    updated = NativeOuterLoop((*loop.sides[:-1], changed), 4, checkpoint)
    proof = NativeMaterialDomainCoverage(updated, projection, domain, checkpoint)
    assert proof.reverse_upper_mm > Fraction(1, 100)
    assert proof.status == "unresolved_actual_native_material_domain"


def test_missing_repeated_and_broken_native_boundaries_do_not_gain_coverage() -> None:
    """
    Completeness, directed continuity and one cyclic side traversal remain independent of small distances.
    """
    loop, projection, domain = example()
    with pytest.raises(ValueError, match="complete nonempty"):
        NativeOuterLoop(loop.sides[:-1], 4, checkpoint)
    repeated = NativeOuterLoop(loop.sides * 2, 8, checkpoint)
    with pytest.raises(ValueError, match="exactly once cyclically"):
        NativeMaterialDomainCoverage(repeated, projection, domain, checkpoint)
    first = loop.sides[0]
    broken = replace(
        first, box=replace(first.box, directed_vertices=(99, 98)), checkpoint=checkpoint
    )
    with pytest.raises(ValueError, match="closed directed vertex cycle"):
        NativeOuterLoop((broken, *loop.sides[1:]), 4, checkpoint)


def test_foreign_proofs_and_stopped_allocations_do_not_transfer_native_acceptance() -> None:
    """
    Numeric equivalence cannot waive owner identity or the shared resource stop.
    """
    loop, projection, domain = example()
    other_loop, other_projection, other_domain = example()
    with pytest.raises(ValueError, match="SAME qualified actual native"):
        NativeMaterialDomainCoverage(loop, other_projection, domain, checkpoint)
    with pytest.raises(ValueError, match="SAME qualified actual native"):
        NativeMaterialDomainCoverage(loop, projection, other_domain, checkpoint)
    with pytest.raises(ValueError, match="SAME original native owners"):
        NativeOuterLoop((other_loop.sides[0], *loop.sides[1:]), 4, checkpoint)

    def stop() -> None:
        """
        Refuse work under an exhausted allocation.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        NativeMaterialDomainCoverage(loop, projection, domain, stop)
