"""
Check the private four-width sphere binding without solves or Fusion imports.
"""

from __future__ import annotations

from dataclasses import replace
from types import ModuleType

import pytest

from cable_bundler.routing.geometry import Vector3
from experiments.experiment_ribbon_cap_transition.fixtures import reversal_case
from experiments.experiment_ribbon_cap_transition.native_policy import bind_sphere_policy
from experiments.experiment_secure_discrete_ribbon.cases import audit_end_boundary
from experiments.experiment_secure_discrete_ribbon.end_boundary import EndBoundary


def test_private_sphere_binding_accepts_four_widths_without_changing_shared_default() -> None:
    """
    Bind the real auditor to the private harness, preserving its original default.
    """
    case = reversal_case()
    harness = ModuleType("private native policy test")
    untouched = ModuleType("unrelated native policy test")
    untouched.audit_end_boundary = audit_end_boundary
    bind_sphere_policy(harness, 4.0)
    result = harness.audit_end_boundary(case)
    assert result["diameter_widths"] == 4 and result["status"] == "contained"
    assert untouched.audit_end_boundary is audit_end_boundary
    with pytest.raises(ValueError, match="five cable widths"):
        untouched.audit_end_boundary(case)


@pytest.mark.parametrize("moved_guides", (False, True))
def test_private_binding_retains_sphere_size_and_full_guide_containment(moved_guides: bool) -> None:
    """
    Reject both a wrong-size sphere and displaced guides under the explicit policy.
    """
    case = reversal_case()
    boundary = (
        EndBoundary(Vector3(500, 0, 0), 114)
        if moved_guides
        else EndBoundary(Vector3(0, 0, 0), 142.5)
    )
    harness = ModuleType("private native policy rejection test")
    bind_sphere_policy(harness, 4.0)
    with pytest.raises(ValueError):
        harness.audit_end_boundary(replace(case, end_boundary=boundary))
