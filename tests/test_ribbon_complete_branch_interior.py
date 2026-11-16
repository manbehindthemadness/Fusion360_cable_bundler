"""
Distinguish local regularity from one-winding domains and globally unique world coordinates.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.branch_interior import audit
from experiments.experiment_ribbon_complete.global_chart import certify
from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import partition
from experiments.experiment_ribbon_complete.section_domain import certify_domain
from experiments.experiment_ribbon_complete.spatial_certificate import certify as local_certificate
from experiments.experiment_ribbon_complete.spatial_frame import (
    ChartOrientation,
    FrameSpan,
    components,
    restrict,
)
from experiments.experiment_ribbon_complete.spatial_transition import compose
from tests.test_ribbon_complete_branch_lengths import complete_plans
from tests.test_ribbon_complete_lengths import checkpoint

BOUNDS = (Fraction(-1, 2), Fraction(1, 2))


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_original_root_domains_have_one_clockwise_winding(lines: int) -> None:
    """
    Include every exterior arc and internal seam in each conductor's complete root boundary.
    """
    for root in partition(lines, 0.75):
        center = (root.pin_number - (lines + 1) / 2) * 0.75
        sections = build(root, center, 0.375)
        result = certify_domain(sections, checkpoint)
        assert result.status == "certified" and result.winding_number == -1
        assert len(result.separators) == len(sections)


def test_duplicate_boundary_traversal_cannot_inherit_positive_local_orientation() -> None:
    """
    The same locally valid edges traversed twice do not define one owned disk chart.
    """
    sections = build(partition(2, 0.75)[0], -0.375, 0.375)
    result = certify_domain(sections + sections, checkpoint)
    assert result.winding_number == -2 and result.status == "unresolved"


def test_nonplanar_shear_chart_has_a_global_inverse_without_fixed_station_normals() -> None:
    """
    F=(3u,q,b+0.1u*q) has explicit inverse u=x/3,q=y,b=z-xy/30.
    """
    frame = FrameSpan(
        Fraction(0),
        Fraction(1),
        (Vector3(0, 0, 0), Vector3(3, 0, 0)),
        (Vector3(0, 1, 0), Vector3(0, 1, 0.1)),
        (Vector3(0, 0, 1),),
        ChartOrientation.POSITIVE,
    )
    result = certify((frame,), BOUNDS, BOUNDS, checkpoint)
    assert result.status == "certified"
    assert result.minimum_monotonicity is not None and result.minimum_monotonicity > Fraction(0)
    assert result.condition_upper is not None and result.condition_upper <= 1024


def test_singular_and_ill_conditioned_root_bases_are_not_accepted() -> None:
    """
    Global uniqueness needs a valid numerical chart, not a dimensional waiver of collapsed coordinates.
    """
    frame = FrameSpan(
        Fraction(0),
        Fraction(1),
        (Vector3(0, 0, 0), Vector3(3, 0, 0)),
        (Vector3(0, 1, 0),),
        (Vector3(0, 0, 1),),
        ChartOrientation.POSITIVE,
    )
    for normal in (Vector3(0, 1, 0), Vector3(0, 0, 1e-8)):
        assert (
            certify((replace(frame, thickness=(normal,)),), BOUNDS, BOUNDS, checkpoint).status
            == "unresolved"
        )


def loop_frames() -> tuple[FrameSpan, ...]:
    """
    Exactly restrict an integer-control regular closed center loop into sixteen dyadic source spans.
    """
    center = (Vector3(0, 0, 0), Vector3(3, -3, 0), Vector3(3, 3, 0), Vector3(0, 0, 0))
    width = (Vector3(1, 1, 0), Vector3(-2, 0, 0), Vector3(1, -1, 0))
    output = []
    for index in range(16):
        low, high = Fraction(index, 16), Fraction(index + 1, 16)
        fields = []
        for controls in (center, width):
            coordinates = tuple(restrict(field, low, high) for field in components(controls))
            fields.append(
                tuple(
                    Vector3(*(float(field[i]) for field in coordinates))
                    for i in range(len(controls))
                )
            )
        output.append(
            FrameSpan(
                low, high, fields[0], fields[1], (Vector3(0, 0, 1),), ChartOrientation.POSITIVE
            )
        )
    return tuple(output)


def test_locally_positive_returning_curve_cannot_prove_global_injectivity() -> None:
    """
    Distinct endpoint source coordinates map to the same world center despite positive local Jacobians.
    """
    frames = loop_frames()
    sections = build(partition(2, 0.75)[0], -0.375, 0.375)
    for frame in frames:
        assert all(
            local_certificate(compose(section, frame, checkpoint), checkpoint).status == "certified"
            for section in sections
        )
    assert frames[0].center[0] == frames[-1].center[-1]
    result = certify(frames, BOUNDS, BOUNDS, checkpoint)
    assert result.status == "unresolved"


def test_actual_interior_audit_preserves_identity_and_unqualified_material_transport() -> None:
    """
    A globally owned geometric domain cannot clear material, contact or native acceptance.
    """
    _complete, plans = complete_plans()
    result = audit(plans[0], checkpoint)
    assert result.plan is plans[0]
    assert (
        result.transverse.status
        == result.world_map.status
        == result.local_coordinate_status
        == "certified"
    )
    assert "material_metrics" in result.plan.outstanding and "contact" in result.plan.outstanding
