"""
Verify spatial fixtures and orientation-independent native seam correspondence.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_diagnosis.end_sections import CappedConnectionTurns
from experiments.experiment_ribbon_diagnosis.inputs import analytic_guide_frame
from experiments.experiment_ribbon_diagnosis.spatial import spatial_cases, spatial_evidence
from experiments.experiment_secure_discrete_ribbon.cases import (
    Expectation,
    RibbonStressCase,
    audit_end_boundary,
)
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)
from tests.fusion_ui_support import _PaletteLifecycleModule


@pytest.mark.parametrize("case", spatial_cases(), ids=lambda case: case.name)
def test_spatial_inputs_and_short_connections_are_certified(case: RibbonStressCase) -> None:
    """
    Verify input regularity, full end containment, and capped curved branches.
    """
    assert audit_end_boundary(case, diameter_widths=4)["status"] == "contained"
    if case.expectation is Expectation.CURVATURE_REJECTION:
        with pytest.raises(UnsafeRibbon):
            certify_curvature(case.route, discrete_profile_reach(case.lines, case.diameter_mm))
    else:
        assert (
            certify_curvature(
                case.route, discrete_profile_reach(case.lines, case.diameter_mm)
            ).maximum_ratio
            <= 0.8
        )
    for at_start in (True, False):
        frame = analytic_guide_frame(case, at_start)
        policy = CappedConnectionTurns(case, turn_degrees=15)
        branch = policy(frame.origin, frame.tangent, frame.thickness, 8 * 28.5, "test")
        assert certify_curvature(branch, case.diameter_mm).maximum_ratio <= 0.8
        assert (
            policy.observations[0]["length_upper_mm"]
            <= policy.observations[0]["maximum_length_mm"] + 1e-9
        )
    assert spatial_evidence(case)["exact_shortest_proven"] is False
    assert case == next(other for other in spatial_cases() if other.name == case.name)


def test_sphere_compression_preserves_material_dimensions_and_scales_all_routes() -> None:
    """
    Apply the same geometric compression to every case without shrinking the ribbon.
    """
    for old, new in zip(spatial_cases(5), spatial_cases(4)):
        assert old.lines == new.lines == 19
        assert old.diameter_mm == new.diameter_mm == 1.5
        assert old.start_width == new.start_width
        assert old.end_width == new.end_width
        assert new.end_boundary.diameter_mm == 114.0
        for before, after in zip(old.route.curves, new.route.curves):
            for a, b in zip(
                (before.start, before.control_a, before.control_b, before.end),
                (after.start, after.control_a, after.control_b, after.end),
            ):
                assert (b.x, b.y, b.z) == pytest.approx((0.8 * a.x, 0.8 * a.y, 0.8 * a.z))


@pytest.mark.parametrize(
    "mode,expected",
    (
        ("equal", "passed"),
        ("unequal", "failed"),
        ("missing", "unmeasured"),
        ("duplicate", "unmeasured"),
    ),
)
def test_native_rail_correspondence_ignores_global_orientation(
    addin_module: _PaletteLifecycleModule, mode: str, expected: str
) -> None:
    """
    Use cap identity across a twisted 3D arrangement; missing evidence cannot pass.
    """
    del addin_module
    from experiments.experiment_ribbon_diagnosis.observations import SectionRecord
    from experiments.experiment_ribbon_diagnosis.rail_audit import audit_rails

    first = SectionRecord(1, Mock(), points_mm=[(0.0, 0.0, 0.0)] * 24)
    last = SectionRecord(2, Mock(), points_mm=[(0.0, 0.0, 0.0)] * 24)
    edges = []
    for slot, index in enumerate((-4, -6, -3, -1)):
        a = (1.0 + slot, 2.0 - slot, 3.0 + slot)
        b = (12.0 - slot, 23.0 + slot, 34.0 - slot)
        first.points_mm[index], last.points_mm[index] = a, b
        start = Mock(geometry=Vector3(*(v / 10 for v in a)), tempId=2 * slot)
        end = Mock(geometry=Vector3(*(v / 10 for v in b)), tempId=2 * slot + 1)
        length = 1.02 if mode == "unequal" and slot == 2 else 1.0
        edges.append(
            Mock(
                startVertex=end,
                endVertex=start,
                length=length,
                faces=(Mock(tempId=20 + slot), Mock(tempId=40 + slot)),
            )
        )
    if mode == "missing":
        edges.pop()
    if mode == "duplicate":
        edges.append(edges[0])
    result = audit_rails(Mock(edges=edges), [first, last], 3)
    assert result["status"] == expected
