"""
Check Cartesian transport conditioning and root convexity without equating them to physical isometry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

import pytest

from experiments.experiment_ribbon_complete import material_atlas
from experiments.experiment_ribbon_complete.material_atlas import audit
from experiments.experiment_ribbon_complete.profile_transition import TransitionEdge, build
from experiments.experiment_ribbon_complete.root_convexity import certify as convexity
from experiments.experiment_ribbon_complete.root_profiles import RootProfile, partition, seam
from experiments.experiment_ribbon_complete.section_domain import certify_domain
from experiments.experiment_ribbon_complete.transport_regularity import TransportRegularity, certify
from tests.test_ribbon_complete_branch_lengths import complete_plans
from tests.test_ribbon_complete_collared_transport import uniform_section
from tests.test_ribbon_complete_lengths import checkpoint


@pytest.mark.parametrize("scale", (1, 0.875))
def test_cartesian_ratio_matrices_bound_identity_and_moderate_contraction(scale: float) -> None:
    """
    Identity gives the exact matrixI; contraction remains conditioned away from a radial fold.
    """
    result = certify(uniform_section(scale), checkpoint)
    assert result.status == "certified"
    assert result.minimum_monotonicity is not None and result.minimum_monotonicity > Fraction(0)
    assert result.source_condition_upper is not None and result.source_condition_upper <= 1024
    if scale == 1:
        assert result.minimum_monotonicity == Fraction(1)
        assert all(row == ((1, 0), (0, 1)) for row in result.coefficient_ratios)


def test_folded_contraction_cannot_inherit_a_conditioned_global_material_chart() -> None:
    """
    Positive denominators cannot conceal an orientation-reversing Cartesian derivative.
    """
    result = certify(uniform_section(0.5), checkpoint)
    assert result.status == "unresolved" and result.source_condition_upper is None
    assert result.derivative_frobenius_squared_upper is None
    assert result.longitudinal_rate_squared_upper is None
    assert (
        len(result.coefficient_ratios)
        < result.coefficient_shape[0] * result.coefficient_shape[1] * result.coefficient_shape[2]
    )


def test_missing_source_denominator_has_no_partial_upper_bounds() -> None:
    """
    A collapsed original root cannot expose prefix norms as bounds for the full derivative.
    """
    section = uniform_section(1)
    collapsed = tuple((Fraction(0), Fraction(0), p[2]) for p in section.rows[0])
    source = replace(
        section.source,
        geometry=replace(section.source.geometry, controls=((0.0, 0.0),) * 3),
    )
    result = certify(
        replace(section, source=source, rows=(collapsed,) * 3 + section.rows[3:]), checkpoint
    )
    assert result.status == "unresolved" and result.coefficient_ratios == ()
    assert result.minimum_monotonicity is None and result.source_condition_upper is None
    assert result.derivative_frobenius_squared_upper is None
    assert result.longitudinal_rate_squared_upper is None


@pytest.mark.parametrize("failed_prerequisite", (False, True))
def test_atlas_stops_before_unattempted_edges(
    monkeypatch: pytest.MonkeyPatch, failed_prerequisite: bool
) -> None:
    """
    A failed world prerequisite launches no transport; a failed first edge retains only that receipt.
    """
    _complete, plans = complete_plans()
    geometry = material_atlas.audit_geometry(plans[0], checkpoint)
    if failed_prerequisite:
        geometry = replace(geometry, local_coordinate_status="unresolved")
    monkeypatch.setattr(material_atlas, "audit_geometry", lambda _plan, _guard: geometry)
    calls: list[TransitionEdge] = []
    failure = certify(uniform_section(0.5), checkpoint)

    def stopped(section: TransitionEdge, guard: Callable[[], None]) -> TransportRegularity:
        """
        Model an unresolved proof boundary while checking that later edges are never scheduled.
        """
        guard()
        calls.append(section)
        return replace(failure, section=section)

    monkeypatch.setattr(material_atlas, "certify_transport", stopped)
    result = audit(plans[0], checkpoint)
    assert len(calls) == len(result.transports) == (0 if failed_prerequisite else 1)
    assert result.status == "unresolved" and result.world_condition_upper is None


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_original_root_disks_are_convex_after_winding_validation(lines: int) -> None:
    """
    Include original curved arcs, explicit corners and interior partition seams.
    """
    for root in partition(lines, 0.75):
        center = (root.pin_number - (lines + 1) / 2) * 0.75
        domain = certify_domain(build(root, center, 0.375), checkpoint)
        result = convexity(domain, checkpoint)
        assert result.status == "certified"


def test_star_shaped_but_reentrant_root_cannot_use_a_convex_domain_argument() -> None:
    """
    A single winding and positive angular progress do not imply convexity.
    """
    points = ((-1.0, 1.0), (0.0, 0.2), (1.0, 1.0), (1.0, -1.0), (-1.0, -1.0))
    root = RootProfile(
        1,
        tuple(seam(a, b, str(i)) for i, (a, b) in enumerate(zip(points, points[1:] + points[:1]))),
    )
    domain = certify_domain(build(root, 0, 1), checkpoint)
    assert domain.status == "certified"
    assert convexity(domain, checkpoint).status == "unresolved"


def test_atlas_keeps_source_identity_and_unqualified_physical_metrics() -> None:
    """
    A coordinate certificate cannot clear physical material, contact or native requirements.
    """
    _complete, plans = complete_plans()
    result = audit(plans[0], checkpoint)
    assert result.plan is plans[0] and result.geometry.plan is plans[0]
    assert result.convexity.status == "certified"
    assert (
        "material_metrics" in result.plan.outstanding
        and "native_junctions" in result.plan.outstanding
    )
