"""
Keep required mid-thickness identities distinct from through-thickness length diagnostics.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_complete.material_paths import enclose
from experiments.experiment_ribbon_complete.material_traces import audit, traces
from experiments.experiment_ribbon_complete.profile_transition import build
from experiments.experiment_ribbon_complete.root_profiles import partition
from tests.test_ribbon_complete_branch_plan import data, planned
from tests.test_ribbon_complete_lengths import checkpoint
from tests.test_ribbon_complete_material_paths import frame, patches


@pytest.mark.parametrize("lines", (1, 2, 5, 10))
def test_all_ordered_roots_have_preserved_midplane_traces(lines: int) -> None:
    """
    Include internal partition seams and exterior tips without a nearest-point or station search.
    """
    for root in partition(lines, 0.75):
        center = (root.pin_number - (lines + 1) / 2) * 0.75
        left, right = traces(build(root, center, 0.375))
        assert left.root_q_mm < Fraction(0) < right.root_q_mm
        if 1 < root.pin_number < lines:
            assert left.coordinate == right.coordinate == Fraction(1, 2)


def test_through_thickness_differences_do_not_become_a_midline_equality_requirement() -> None:
    """
    A changing thickness field affects boundary diagnostics while b=0 paths retain equal increments.
    """
    changed = replace(frame(), thickness=(Vector3(0, 0, 1), Vector3(1, 0, 1)))
    geometry = patches(changed)
    left, right = traces(tuple(patch.section for patch in geometry))
    for trace in (left, right):
        result = enclose(geometry[trace.edge_index], checkpoint, edge_coordinate=trace.coordinate)
        assert result.discrepancy_upper_mm is not None
        assert result.discrepancy_upper_mm <= Fraction(1, 200)
    diagnostic = enclose(geometry[0], checkpoint)
    assert diagnostic.discrepancy_upper_mm is not None
    assert diagnostic.discrepancy_upper_mm > Fraction(1, 100)


def test_actual_midline_audit_keeps_plan_identity_and_missing_material_checks() -> None:
    """
    A longitudinal measurement cannot waive transverse, interior or native qualifications.
    """
    plan = planned(data())
    result = audit(plan, checkpoint)
    assert result.plan is plan
    assert result.left.root_q_mm < Fraction(0) < result.right.root_q_mm
    assert all(proof.edge_coordinate is not None for span in result.spans for proof in span)
    assert result.status == "certified"
    assert result.pairwise_upper_mm is not None and result.pairwise_upper_mm <= Fraction(1, 100)
    assert "material_metrics" in result.plan.outstanding
    assert "native_junctions" in result.plan.outstanding
