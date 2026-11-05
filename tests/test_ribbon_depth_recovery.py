"""
Use undecided material boxes as recovery evidence without treating depth exhaustion as clearance.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cable_bundler.routing.geometry import cross, difference, magnitude, unit
from devtools.ribbon_analysis.gym.scene import Config, Goal, Scene
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_contraction.contract import cap_error
from experiments.experiment_ribbon_contraction.runner import material_error
from experiments.experiment_ribbon_feature_insertion.contact_measurement import ContactPolicy
from experiments.experiment_ribbon_feature_insertion.guide_frames import Frames
from experiments.experiment_ribbon_feature_insertion.selection import Branch
from experiments.experiment_ribbon_feature_insertion.separation import Separation
from experiments.experiment_ribbon_feature_insertion.solve import construct
from experiments.experiment_ribbon_fold_route.contact import ContactResult
from experiments.experiment_ribbon_fold_route.contact_bounds import Span
from experiments.experiment_ribbon_joint_route.boundary import Boundary
from experiments.experiment_ribbon_locked_solver import solver_v2
from experiments.experiment_ribbon_locked_solver.settings import Settings


@pytest.fixture(scope="module")
def undecided() -> tuple[Branch, ContactResult]:
    """
    Recreate the fixed two-conductor gym with a genuine depth-limited curved pair.
    """
    scene = Scene(Config(1689995010, 2, 0.75, 300, 300), Goal(3, 9, 1), Goal(9, 6, 1))
    frames = Frames.create(scene.targets)
    radius = scene.targets.diameter_mm / 2 / PinchLimit().fraction * (1 + 1e-9)
    result = construct(
        Boundary(frames.targets, radius), frames, (0.5,), 1e-5, lambda: None, lambda e: None
    )
    assert result.route is None and len(result.rejected) == 1
    return result.rejected[0]


def test_depth_boxes_are_evidence_and_never_a_contact_permission(
    undecided: tuple[Branch, ContactResult],
) -> None:
    """
    Retain exact undecided material identities while both contact policies still reject depth exhaustion.
    """
    branch, contact = undecided
    assert contact.status == "unresolved" and contact.limit == "depth"
    assert contact.witness is None and contact.pairs_checked == 637
    assert contact.unresolved_regions is not None
    assert tuple(c.piece for c in contact.unresolved_regions) == contact.unresolved_pieces == (2, 5)
    assert all(isinstance(branch.route.pieces[i].geometry, CylindricalFold) for i in (2, 5))
    assert all(0 <= c.u.low <= c.u.high <= 1 for c in contact.unresolved_regions)
    assert not any(policy.permits_geometry(contact) for policy in ContactPolicy)
    model = MovableBends(branch.route)
    bound = Separation.from_measurement(model, branch.route, contact)
    assert bound is not None
    cell = contact.unresolved_regions[0]
    _, velocity, width, _ = branch.route.pieces[cell.piece].surface(
        (cell.u.low + cell.u.high) / 2, (cell.q.low + cell.q.high) / 2
    )
    assert magnitude(difference(bound.axis, unit(cross(velocity, width)))) < 1e-12


@pytest.mark.parametrize("fault", ("missing", "identity", "index", "nonfinite", "pair_limit"))
def test_unsupported_region_data_does_not_invent_a_recovery_normal(
    undecided: tuple[Branch, ContactResult], fault: str
) -> None:
    """
    Reject absent, mismatched or malformed interval evidence and preserve the declared depth-only scope.
    """
    branch, contact = undecided
    cells = contact.unresolved_regions
    assert cells is not None
    altered = {
        "missing": replace(contact, unresolved_regions=None),
        "identity": replace(contact, unresolved_regions=(replace(cells[0], piece=99), cells[1])),
        "index": replace(contact, unresolved_pieces=(-1, 5)),
        "nonfinite": replace(
            contact, unresolved_regions=(replace(cells[0], u=Span(math.nan, 1)), cells[1])
        ),
        "pair_limit": replace(contact, limit="pairs"),
    }[fault]
    assert Separation.from_measurement(MovableBends(branch.route), branch.route, altered) is None


def test_depth_case_finishes_only_after_new_strict_contact_certificate(
    undecided: tuple[Branch, ContactResult],
) -> None:
    """
    Preserve profiles, radii and cap/material rules while recovering the unresolved source.
    """
    branch, contact = undecided
    result = solver_v2.solve(
        branch.route.targets, Settings(0, False, False), lambda: None, lambda e: None
    )
    assert result.route is not None and result.detail["contact"] == "separated"
    detail = result.detail["construction"]
    assert 0 < detail["contact_pairs"] <= 1229
    assert detail["cap_support_policy"] == "analytic_support"
    assert detail["recovery"]["iterations"] == 3 and detail["recovery"]["contacts"] == 2
    assert contact.status == "unresolved" and contact.witness is None
    before = [p.geometry for p in branch.route.pieces if isinstance(p.geometry, CylindricalFold)]
    after = [p.geometry for p in result.route.pieces if isinstance(p.geometry, CylindricalFold)]
    assert len(before) == len(after) == 4
    assert all(
        original.radius_mm == restored.radius_mm and original.width_mm == restored.width_mm
        for original, restored in zip(before, after)
    )
    assert result.route.radius_mm == branch.route.radius_mm
    assert result.route.targets == branch.route.targets
    assert cap_error(result.route) < 1e-7 and material_error(result.route) < 1e-10
