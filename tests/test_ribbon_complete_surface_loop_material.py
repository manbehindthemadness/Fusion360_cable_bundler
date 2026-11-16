"""
Challenge surface-patch lifting with endpoint gaps, hidden interior distortion and original world-frame units.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete.flat_cut_domain import FlatCutFrame
from experiments.experiment_ribbon_complete.native_material_chart import NativeSurfaceSnapshot
from experiments.experiment_ribbon_complete.native_planar_projection import NativePlanarProjection
from experiments.experiment_ribbon_complete.projected_filled_domain import (
    DirectedBoundaryTrace,
    ProjectedFilledDomain,
)
from experiments.experiment_ribbon_complete.surface_loop_material import SurfaceLoopMaterialCoverage
from tests.test_ribbon_complete_native_boundary_distance import bound
from tests.test_ribbon_complete_projected_filled_domain import boundary
from tests.test_ribbon_complete_volume_injectivity import checkpoint


def rebind(
    rows: tuple[DirectedBoundaryTrace, ...], surface: NativeSurfaceSnapshot, frame: FlatCutFrame
) -> tuple[DirectedBoundaryTrace, ...]:
    """
    Recompute complete finite boundaries on one changed surface without transferring old proof owners.
    """
    return tuple(
        replace(
            row,
            finite=bound(
                surface, frame, row.finite.graph, row.finite.side, row.finite.trace.curve.controls
            ),
        )
        for row in rows
    )


def coverage(rows: tuple[DirectedBoundaryTrace, ...]) -> SurfaceLoopMaterialCoverage:
    """
    Qualify the same owned projected loop and full natural-domain projection before lifting.
    """
    finite = rows[0].finite
    return SurfaceLoopMaterialCoverage(
        ProjectedFilledDomain(rows, checkpoint),
        NativePlanarProjection(finite.trace.surface, finite.frame, checkpoint),
        checkpoint,
    )


def bubble(
    rows: tuple[DirectedBoundaryTrace, ...], delta: Fraction
) -> tuple[DirectedBoundaryTrace, ...]:
    """
    Change only the surface interior while retaining every original outer boundary curve.
    """
    base = rows[0].finite.trace.surface
    middle = tuple(
        (Fraction(1), q, b + (delta if j == 1 else 0)) for j, (_, q, b) in enumerate(base.rows[0])
    )
    bowed = replace(
        base,
        degree_u=2,
        knots_u=(Fraction(0),) * 3 + (Fraction(2),) * 3,
        rows=(base.rows[0], middle, base.rows[1]),
        weights=(base.weights[0],) * 3,
    )
    return rebind(rows, bowed, rows[0].finite.frame)


def test_exact_patch_and_both_loop_orientations_have_zero_joint_error() -> None:
    """
    An exact original elliptic strip lifts without adding a synthetic dimensional discrepancy.
    """
    rows = boundary()
    opposite = tuple(
        replace(row, start_vertex=row.end_vertex, end_vertex=row.start_vertex, reversed=True)
        for row in reversed(rows)
    )
    for directed in (rows, opposite):
        proof = coverage(directed)
        assert proof.status == "within_comparison_surface_material_coverage"
        assert proof.profile_graph_error_mm == Fraction(0)
        assert proof.forward_upper_mm == proof.reverse_upper_mm == Fraction(0)
        assert sum(proof.bridge_world_lengths_mm) == 0


def test_uv_closure_bridge_is_bounded_on_the_surface_without_changing_the_trace() -> None:
    """
    A shortened native trace retains its endpoint; a positive surface-metric bridge budget is explicitly included.
    """
    rows = boundary()
    first = rows[0].finite
    gap = Fraction(1, 1000000)
    shortened = bound(
        first.trace.surface,
        first.frame,
        first.graph,
        first.side,
        ((gap, Fraction(0)), (Fraction(2), Fraction(0))),
    )
    proof = coverage((replace(rows[0], finite=shortened), *rows[1:]))
    assert proof.status == "within_comparison_surface_material_coverage"
    assert sum(proof.bridge_label_lengths_mm) > 0
    assert proof.collar_upper_mm > proof.projected.collar_upper_mm
    assert shortened.trace.curve.controls[0][0] == gap


def test_interior_material_bubble_cannot_hide_behind_exact_boundary_coverage() -> None:
    """
    A b displacement vanishing on all four sides still violates material coverage inside the surface.
    """
    rows = boundary()
    delta = Fraction(1, 5)
    proof = coverage(bubble(rows, delta))
    assert proof.projected.forward_upper_mm == proof.projected.reverse_upper_mm == Fraction(0)
    weights = rows[0].finite.trace.surface.weights[0]
    # Exact rational tensor evaluation at the center, using the original binary weights.
    center_displacement = delta * weights[1] / (weights[0] + 2 * weights[1] + weights[2])
    assert center_displacement > Fraction(1, 100)
    assert proof.profile_graph_error_mm >= center_displacement
    assert proof.status == "unresolved_comparison_surface_material_coverage"


def test_world_frame_scaling_is_included_in_the_joint_material_allowance() -> None:
    """
    A small b-coordinate displacement can be a much larger world distance under the unchanged original frame.
    """
    rows = boundary()
    first = rows[0].finite
    delta = Fraction(1, 100000)
    scaled = replace(
        first.trace.surface,
        rows=tuple(
            tuple((s, q, 100 * (b + delta)) for s, q, b in row) for row in first.trace.surface.rows
        ),
    )
    frame = replace(
        first.frame,
        columns=(
            first.frame.columns[0],
            first.frame.columns[1],
            tuple(100 * x for x in first.frame.columns[2]),
        ),
    )
    proof = coverage(rebind(rows, scaled, frame))
    assert proof.profile_graph_error_mm >= delta
    assert proof.forward_upper_mm >= 100 * delta
    assert proof.lift_factor >= 100 * first.graph.slope_upper


def test_foreign_projection_and_unresolved_physical_projection_cannot_lift_a_loop() -> None:
    """
    Equivalent values cannot replace owned frames, and a failed global projection never grants a surface inverse.
    """
    rows = boundary()
    finite = rows[0].finite
    projected = ProjectedFilledDomain(rows, checkpoint)
    foreign = NativePlanarProjection(finite.trace.surface, replace(finite.frame), checkpoint)
    with pytest.raises(ValueError, match="SAME globally injective"):
        SurfaceLoopMaterialCoverage(projected, foreign, checkpoint)
    slender = replace(
        finite.trace.surface,
        rows=tuple(
            tuple((s, q / 1000000, b) for s, q, b in row) for row in finite.trace.surface.rows
        ),
    )
    changed = rebind(rows, slender, finite.frame)
    unresolved = NativePlanarProjection(slender, finite.frame, checkpoint)
    assert unresolved.status == "unresolved_global_native_sq_projection"
    with pytest.raises(ValueError, match="SAME globally injective"):
        SurfaceLoopMaterialCoverage(
            ProjectedFilledDomain(changed, checkpoint), unresolved, checkpoint
        )


def test_interior_wrong_profile_branch_cannot_inherit_exact_boundary_evidence() -> None:
    """
    Boundary coincidence cannot select the correct b graph when interior control hulls cross its separated branch.
    """
    changed = bubble(boundary(), Fraction(-10))
    projected = ProjectedFilledDomain(changed, checkpoint)
    assert projected.forward_upper_mm == Fraction(0)
    with pytest.raises(ValueError, match="separated original profile graph branch"):
        coverage(changed)


def test_surface_lift_observes_the_shared_resource_stop() -> None:
    """
    No profile, bridge or winding work occurs after the caller's allocation expires.
    """
    proof = coverage(boundary())

    def stop() -> None:
        """
        Reject further work under an exhausted fixed allocation.
        """
        raise RuntimeError("allocation stopped")

    with pytest.raises(RuntimeError, match="allocation stopped"):
        SurfaceLoopMaterialCoverage(proof.projected, proof.projection, stop)
