"""
Check continuous material-path bounds against independent affine and cancellation counterexamples.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.material_paths import audit, certify, enclose, witness
from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import RootEdge, RootProfile, partition
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from experiments.experiment_ribbon_complete.spatial_transition import SpatialPatch, compose
from tests.test_ribbon_complete_branch_plan import data, planned
from tests.test_ribbon_complete_lengths import checkpoint


def patches(span: FrameSpan) -> tuple[SpatialPatch, ...]:
    """
    Use an unchanged single-conductor round profile to isolate longitudinal geometry.
    """
    arcs = tuple(section.terminal for section in build(partition(1, 1)[0], 0, 0.5))
    circle = RootProfile(1, tuple(RootEdge(arc, None) for arc in arcs))
    return tuple(compose(section, span, checkpoint) for section in build(circle, 0, 0.5))


def frame() -> FrameSpan:
    """
    Define a ten-millimeter straight branch with unit transverse axes.
    """
    return FrameSpan(
        Fraction(0),
        Fraction(1),
        (Vector3(0, 0, 0), Vector3(10, 0, 0)),
        (Vector3(0, 1, 0),),
        (Vector3(0, 0, 1),),
        ChartOrientation.POSITIVE,
    )


def test_rigid_transverse_offsets_preserve_all_longitudinal_increments() -> None:
    """
    A translated round section has the same speed at every boundary coordinate, not only landmarks.
    """
    result = certify((patches(frame()),), checkpoint)
    assert result.status == "certified"
    assert result.pairwise_upper_mm is not None and result.pairwise_upper_mm <= Fraction(1, 100)


def test_nonuniform_parameter_speed_does_not_imply_material_stretch() -> None:
    """
    Compare paths at corresponding coordinates without assuming unit or constant center speed.
    """
    varying = replace(frame(), center=(Vector3(0, 0, 0), Vector3(3, 0, 0), Vector3(10, 0, 0)))
    result = enclose(patches(varying)[0], checkpoint)
    assert result.discrepancy_upper_mm is not None
    assert result.discrepancy_upper_mm <= Fraction(1, 200)


def test_local_stretch_and_compression_cannot_cancel_into_a_pass() -> None:
    """
    For offset q the speed is10+2q(1-2t), giving equal totals but nonzero local mismatch.
    """
    varying = replace(frame(), width=(Vector3(0, 1, 0), Vector3(1, 1, 0), Vector3(0, 1, 0)))
    result = enclose(patches(varying)[0], checkpoint)
    # Both endpoint offsets agree, so every boundary path still has total length10.
    # Its half-interval discrepancy is q/2, up to0.25mm on the original circle.
    assert result.discrepancy_upper_mm is not None
    assert result.discrepancy_upper_mm >= Fraction(1, 4)
    measured = witness(result.patch, Fraction(0), Fraction(1, 2), Fraction(1), checkpoint)
    assert measured.violation and measured.excess_lower_mm > Fraction(1, 100)
    whole = witness(result.patch, Fraction(0), Fraction(1), Fraction(1), checkpoint)
    assert not whole.violation  # The complete total conceals the witnessed half-interval extension.


def test_zero_reference_speed_remains_unresolved_without_division_or_reparameterization() -> None:
    """
    A positive speed denominator is a numerical dependency, not a smaller dimensional tolerance.
    """
    stopped = replace(frame(), center=(Vector3(0, 0, 0),))
    result = enclose(patches(stopped)[0], checkpoint)
    assert result.discrepancy_upper_mm is None


def test_changed_world_controls_cannot_inherit_the_material_proof() -> None:
    """
    Retained source fields do not validate a different native-authoring control net.
    """
    original = patches(frame())[0]
    row = original.rows[2]
    changed = (row[0][0] + 1,) + row[0][1:]
    rows = original.rows[:2] + ((changed,) + row[1:],) + original.rows[3:]
    with pytest.raises(ValueError, match="changed world controls"):
        enclose(replace(original, rows=rows), checkpoint)


def test_missing_span_cannot_inherit_a_whole_branch_length_bound() -> None:
    """
    Refuse incomplete coverage instead of measuring the supplied prefix as the whole material path.
    """
    partial = replace(frame(), high=Fraction(1, 2))
    with pytest.raises(ValueError, match="complete unit interval"):
        certify((patches(partial),), checkpoint)


def test_actual_branch_audit_preserves_geometry_and_other_missing_checks() -> None:
    """
    Measure the assembled joined-profile transition without replacing it with an analytical round control.
    """
    plan = planned(data())
    result = audit(plan, checkpoint)
    assert result.plan is plan
    assert result.plan.source.source.route is plan.source.source.route
    assert all(
        proof.patch is patch
        for proofs, span in zip(result.boundary_paths.spans, plan.patches)
        for proof, patch in zip(proofs, span)
    )
    assert "material_metrics" in plan.outstanding and "native_junctions" in plan.outstanding


def test_missing_edges_are_not_a_complete_boundary_certificate() -> None:
    """
    A valid isolated patch cannot substitute for the whole closed conductor boundary.
    """
    with pytest.raises(ValueError, match="closed source"):
        certify(((patches(frame())[0],),), checkpoint)


def test_local_interval_scaling_preserves_integrated_material_units() -> None:
    """
    A half-span integral is not accidentally scaled twice or reported as a full global-u derivative.
    """
    varying = replace(frame(), width=(Vector3(0, 1, 0), Vector3(0.1, 1, 0)))
    whole = enclose(patches(varying)[0], checkpoint)
    half_frame = replace(
        varying,
        high=Fraction(1, 2),
        center=(Vector3(0, 0, 0), Vector3(5, 0, 0)),
        width=(Vector3(0, 1, 0), Vector3(0.05, 1, 0)),
    )
    half = enclose(patches(half_frame)[0], checkpoint)
    assert whole.discrepancy_upper_mm is not None and half.discrepancy_upper_mm is not None
    assert abs(whole.discrepancy_upper_mm - 2 * half.discrepancy_upper_mm) < Fraction(1, 100)
