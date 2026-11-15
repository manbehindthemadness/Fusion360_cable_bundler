"""
Check actual support bending against independent plane, parabolic-cylinder and saddle examples.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_bends import audit, lateral
from experiments.experiment_ribbon_complete.ruled_support import enclose
from experiments.experiment_ribbon_complete.spatial_frame import ChartOrientation, FrameSpan
from experiments.experiment_ribbon_complete.spatial_transition import compose
from tests.test_ribbon_complete_branch_lengths import complete_plans
from tests.test_ribbon_complete_lengths import checkpoint


def plane() -> FrameSpan:
    """
    Define the exact ruled plane X=(3u,q,0), including its unchanged thickness vector.
    """
    return FrameSpan(
        Fraction(0),
        Fraction(1),
        (Vector3(0, 0, 0), Vector3(3, 0, 0)),
        (Vector3(0, 1, 0),),
        (Vector3(0, 0, 1),),
        ChartOrientation.POSITIVE,
    )


def test_plane_has_zero_principal_curvature_and_exact_normal_correspondence() -> None:
    """
    Verify the complete width envelope rather than a center-only sample.
    """
    result = enclose(plane(), (Fraction(-1), Fraction(1)), Fraction(1, 2))
    assert result.principal_upper_per_mm == Fraction(0)
    assert result.normal_distance_upper_mm == Fraction(0)
    assert result.physical_half_thickness_upper_mm == Fraction(1, 2)


@pytest.mark.parametrize("scale", (1, 0.5, 0.25))
def test_parabolic_cylinder_curvature_is_invariant_under_parameter_scaling(scale: float) -> None:
    """
    C=(s,0,s²/2), s=scale*u, has maximum curvature1/mm at its origin for every scale.
    """
    frame = replace(
        plane(),
        center=(Vector3(0, 0, 0), Vector3(scale / 2, 0, 0), Vector3(scale, 0, scale**2 / 2)),
    )
    result = enclose(frame, (Fraction(-1), Fraction(1)), Fraction(1, 2))
    assert result.principal_upper_per_mm is not None
    assert Fraction(1) <= result.principal_upper_per_mm < Fraction(1001, 1000)
    assert lateral(frame).exact_zero
    # The fixed Z field is not the curve's rotating unit normal.
    assert (
        result.normal_distance_upper_mm is not None
        and result.normal_distance_upper_mm > Fraction(1, 100)
    )


def test_straight_center_does_not_hide_ruled_surface_saddle_curvature() -> None:
    """
    X=(3u,q,u*q) has principal curvatures +/-1/3 at u=q=0 despite a straight center.
    """
    frame = replace(plane(), width=(Vector3(0, 1, 0), Vector3(0, 1, 1)))
    result = enclose(frame, (Fraction(-1, 2), Fraction(1, 2)), Fraction(1, 2))
    assert lateral(frame).exact_zero
    assert result.principal_upper_per_mm is not None and result.principal_upper_per_mm >= Fraction(
        1, 3
    )


def test_scaled_thickness_is_measured_without_normalizing_it_away() -> None:
    """
    Doubling N doubles physical reach and differs from the unit normal by the original half-thickness.
    """
    result = enclose(
        replace(plane(), thickness=(Vector3(0, 0, 2),)), (Fraction(-1), Fraction(1)), Fraction(1, 2)
    )
    assert result.physical_half_thickness_upper_mm == Fraction(1)
    assert result.normal_distance_upper_mm == Fraction(1, 2)


def test_collapsed_support_and_stationary_progress_remain_unresolved() -> None:
    """
    No curvature denominator is invented when width or longitudinal progress degenerates.
    """
    for frame in (
        replace(plane(), width=(Vector3(1, 0, 0),)),
        replace(plane(), center=(Vector3(0, 0, 0),)),
    ):
        assert (
            enclose(frame, (Fraction(-1), Fraction(1)), Fraction(1, 2)).principal_upper_per_mm
            is None
        )
        assert lateral(frame).curvature_upper_per_mm is None


@pytest.mark.parametrize("height,expected", ((0.001, "certified"), (0.1, "unresolved")))
def test_lateral_comparison_uses_one_dimensional_bound_instead_of_exact_zero(
    height: float,
    expected: str,
) -> None:
    """
    A flat support can have in-plane bending; tiny physical departures do not become angular failures.
    """
    _complete, plans = complete_plans()
    source = plans[0]
    original = source.patches[0][0].frame
    a, b = original.center[0], original.center[-1]
    middle = Vector3((a.x + b.x) / 2, a.y, a.z)
    changed = replace(original, center=(a, middle, b.translated(Vector3(0, 1, 0), height)))
    geometry = replace(
        source, patches=(tuple(compose(p.section, changed, checkpoint) for p in source.patches[0]),)
    )
    result = audit(geometry, checkpoint)
    assert result.principal_reach_status == "certified"  # The geometric midplane stays flat.
    assert not result.lateral_bounds[0].exact_zero
    assert result.lateral_status == expected


def test_actual_plan_audit_retains_identity_and_other_missing_qualifications() -> None:
    """
    Named bend results cannot clear interior/contact/native acceptance from the same plan.
    """
    _complete, plans = complete_plans()
    result = audit(plans[0], checkpoint)
    assert result.plan is plans[0]
    assert (
        result.principal_reach_status
        == result.normal_field_status
        == result.coordinate_status
        == result.lateral_status
        == "certified"
    )
    assert result.lateral_excursion_upper_mm == Fraction(0)
    assert "contact" in result.plan.outstanding and "native_junctions" in result.plan.outstanding


def test_lateral_effect_includes_section_reach_not_only_center_displacement() -> None:
    """
    Small center departure does not hide a larger rotation-induced displacement of a wide section.
    """
    _complete, plans = complete_plans()
    source = plans[0]
    original = source.patches[0][0].frame
    a, b = original.center[0], original.center[-1]
    changed = replace(
        original,
        center=(a, Vector3((a.x + b.x) / 2, a.y, a.z), b.translated(Vector3(0, 1, 0), 0.001)),
        width=(Vector3(0, 100, 0),),
    )
    geometry = replace(
        source, patches=(tuple(compose(p.section, changed, checkpoint) for p in source.patches[0]),)
    )
    result = audit(geometry, checkpoint)
    row = result.lateral_bounds[0]
    assert row.curvature_upper_per_mm is not None
    assert row.center_length_upper_mm**2 * row.curvature_upper_per_mm / 2 < Fraction(1, 100)
    assert result.lateral_status == "unresolved"
    assert (
        result.lateral_excursion_upper_mm is not None
        and result.lateral_excursion_upper_mm > Fraction(1, 100)
    )


def test_rounded_orthogonal_axes_do_not_require_exact_unit_norm() -> None:
    """
    Tiny binary norm residuals are assessed through physical normal displacement, not exact equality.
    """
    frame = replace(
        plane(), center=(Vector3(0, 0, 0), Vector3(1.8, 2.4, 0)), width=(Vector3(-0.8, 0.6, 0),)
    )
    result = enclose(frame, (Fraction(-1), Fraction(1)), Fraction(1, 2))
    assert result.principal_upper_per_mm == Fraction(0)
    assert (
        result.normal_distance_upper_mm is not None
        and result.normal_distance_upper_mm <= Fraction(1, 100)
    )
