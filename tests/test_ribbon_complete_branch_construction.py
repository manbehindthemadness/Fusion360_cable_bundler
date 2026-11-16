"""
Connect fixed branch targets to actual spatial boundaries and their physical measurements.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Literal
from uuid import UUID

import pytest

from cable_bundler.routing.geometry import Vector3, dot, magnitude
from experiments.experiment_ribbon_complete.branch_bends import audit as audit_bends
from experiments.experiment_ribbon_complete.branch_construction import (
    BranchRoot,
    construct,
    frames,
    transport,
)
from experiments.experiment_ribbon_complete.branch_lengths import iter_lengths
from experiments.experiment_ribbon_complete.branch_targets import capture_targets
from experiments.experiment_ribbon_complete.contracts import (
    CompleteRibbonInput,
    IncompleteRibbonInput,
)
from experiments.experiment_ribbon_complete.curve_lengths import LengthWork
from experiments.experiment_ribbon_complete.root_profiles import CapFrame, bind_frame, partition
from tests.test_ribbon_complete_branch_targets import boundaries
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint


def data(lines: int = 2, child: bool = False) -> tuple[CompleteRibbonInput, tuple[BranchRoot, ...]]:
    """
    Bind analytical roots explicitly; no native provenance or solved frames are supplied.
    """
    definition, group, trunk, caps, _ = inputs(lines, child)
    complete = capture_targets(definition, group, trunk, caps, boundaries(lines, child), checkpoint)
    profiles = partition(lines, trunk.diameter_mm)
    roots = []
    for branch in complete.branches:
        if branch.attachment.parent_attachment_id is not None:
            roots.append(
                BranchRoot(
                    branch.source.leg.route_id,
                    partition(1, trunk.diameter_mm)[0],
                    0,
                    CapFrame(
                        branch.source.arrival.point,
                        Vector3(0, 1, 0),
                        Vector3(0, 0, 1),
                        branch.source.arrival.tangent,
                        0,
                    ),
                )
            )
            continue
        index = complete.group.connection_ids.index(branch.source.leg.start_connection_id)
        side: Literal["start", "end"] = "start" if index == 0 else "end"
        port = caps[index]
        roots.append(
            BranchRoot(
                branch.source.leg.route_id,
                profiles[branch.conductor.pin_number - 1],
                (branch.conductor.pin_number - (lines + 1) / 2) * trunk.diameter_mm,
                bind_frame(trunk, side, port.target.point, port.target.tangent),
            )
        )
    return complete, tuple(roots)


def test_descendant_uses_its_own_parent_terminal_root_and_remains_in_the_sequence() -> None:
    """
    A descendant cannot reuse a trunk cap binding or disappear behind its root conductor.
    """
    complete, roots = data(child=True)
    plans = tuple(construct(complete, roots, checkpoint))
    descendant = next(plan for plan in plans if plan.source.attachment.parent_attachment_id)
    binding = next(root for root in roots if root.route_id == descendant.source.source.leg.route_id)
    assert len(plans) == 5
    assert descendant.source.conductor.pin_number == 1
    assert binding.cap.origin == descendant.source.source.arrival.point
    assert binding.cap.origin != complete.caps[0].target.point
    assert all(proof.status == "certified" for proof in descendant.terminations)
    incomplete = tuple(root for root in roots if root is not binding)
    with pytest.raises(IncompleteRibbonInput, match="Every branch"):
        next(construct(complete, incomplete, checkpoint))


@pytest.mark.parametrize("lines", (1, 2, 5))
def test_fixed_targets_reach_complete_boundary_geometry_without_supplied_frames(lines: int) -> None:
    """
    Actual patches keep both cap signs, original roots, source curves and missing native gates.
    """
    complete, roots = data(lines)
    plans = tuple(construct(complete, tuple(reversed(roots)), checkpoint))
    assert tuple(plan.source for plan in plans) == complete.branches
    for plan, root in zip(plans, roots):
        assert len(plan.patches) == 3
        assert len(plan.patches[0]) == len(root.profile.edges)
        assert plan.center_error_squared_mm2 == Fraction(0)
        assert all(proof.status == "certified" for proof in plan.coordinates + plan.terminations)
        assert "native_fidelity" in plan.outstanding and "native_junctions" in plan.outstanding
        for patch, edge in zip(plan.patches[0], root.profile.edges):
            q, b = edge.geometry.controls[0]
            assert patch.jet(0, 0).point == root.cap.point(q, b)
        needs_jet_check = any(
            not seam.first_jets_equal or not seam.second_jets_equal for seam in plan.seams
        )
        assert ("span_jet_continuity" in plan.outstanding) == needs_jet_check
    work = LengthWork(3 * len(plans), checkpoint)
    lengths = tuple(iter_lengths(plans, work, "analytical target-driven spatial boundaries"))
    assert all(row.midline.status == "certified" for row in lengths)
    assert all(row.center.length.lower_mm <= 3 <= row.center.length.upper_mm for row in lengths)


@pytest.mark.parametrize("following", (Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(-1, 0, 0)))
def test_transport_preserves_material_axes_for_parallel_spatial_and_antiparallel_turns(
    following: Vector3,
) -> None:
    """
    A proper endpoint rotation preserves scale, orthogonality and directed tangent correspondence.
    """
    first, width, thickness = Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(0, -1, 0)
    actual = transport(first, first, following, width)
    transverse = transport(width, first, following, width)
    normal = transport(thickness, first, following, width)
    assert (actual.x, actual.y, actual.z) == pytest.approx((following.x, following.y, following.z))
    assert magnitude(transverse) == pytest.approx(1)
    assert magnitude(normal) == pytest.approx(1)
    assert dot(transverse, following) == pytest.approx(0, abs=1e-12)
    assert dot(normal, following) == pytest.approx(0, abs=1e-12)
    assert dot(transverse, normal) == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("kind", ("missing", "duplicate", "foreign"))
def test_incomplete_or_ambiguous_root_coverage_rejects_before_any_branch(kind: str) -> None:
    """
    Construction cannot silently omit or substitute a conductor root.
    """
    complete, roots = data()
    if kind == "missing":
        roots = roots[:-1]
    elif kind == "duplicate":
        roots += (roots[0],)
    else:
        roots = (replace(roots[0], route_id=UUID(int=999999)),) + roots[1:]
    with pytest.raises(IncompleteRibbonInput, match="exactly one"):
        next(construct(complete, roots, checkpoint))


def test_same_route_uuid_cannot_bind_a_foreign_conductor_profile() -> None:
    """
    Root profile identity remains authoritative even when endpoint frames coincide.
    """
    complete, roots = data()
    changed = (replace(roots[0], profile=roots[1].profile),) + roots[1:]
    with pytest.raises(ValueError, match="original conductor root"):
        next(construct(complete, changed, checkpoint))


def test_caller_stop_preserves_yielded_prefix_without_starting_a_new_allocation() -> None:
    """
    A complete first candidate remains available when the same caller stops later branches.
    """
    complete, roots = data()
    stopped = False

    def check() -> None:
        """
        Retain one shared latched stop across the lazy construction sequence.
        """
        if stopped:
            raise RuntimeError("latched branch construction stop")

    stream = construct(complete, roots, check)
    first = next(stream)
    stopped = True
    with pytest.raises(RuntimeError, match="latched"):
        next(stream)
    assert first.source is complete.branches[0]


def test_root_frames_reject_foreign_routes_and_preserve_explicit_material_handedness() -> None:
    """
    A foreign route rejects; an explicitly different root retains its own orientation without repair.
    """
    complete, roots = data()
    with pytest.raises(IncompleteRibbonInput, match="matching"):
        frames(complete.branches[0].source, roots[1], checkpoint)
    root = roots[0]
    changed = replace(root, cap=replace(root.cap, thickness=Vector3(0, 0, -1)))
    result = next(construct(complete, (changed,) + roots[1:], checkpoint))
    assert (
        result.patches[0][0].frame.orientation
        != next(construct(complete, roots, checkpoint)).patches[0][0].frame.orientation
    )
    # The explicit alternate root owns its orientation; no automatic sign repair occurs.
    assert result.patches[0][0].frame.thickness[0] == changed.cap.thickness


def test_boundary_construction_keeps_bend_and_native_checks_separate() -> None:
    """
    A straight analytical support can certify bending while native/volume/contact remain outstanding.
    """
    complete, roots = data()
    plan = next(construct(complete, roots, checkpoint))
    finding = audit_bends(plan, checkpoint)
    assert finding.coordinate_status == "certified"
    assert finding.principal_reach_status == "certified"
    expected_lateral = "certified" if all(s.first_jets_equal for s in plan.seams) else "unresolved"
    assert finding.lateral_status == expected_lateral
    assert {"contact", "interior_ownership", "native_fidelity"}.issubset(plan.outstanding)


def test_target_driven_spatial_curve_reaches_patches_without_inheriting_material_acceptance() -> (
    None
):
    """
    Transported endpoint frames bind a spatial candidate while actual material discrepancy stays unresolved.
    """
    from experiments.experiment_ribbon_complete.material_traces import audit

    definition, group, trunk, caps, _ = inputs()
    targets = boundaries()
    first = targets[0]
    moved = replace(first, terminal=replace(first.terminal, tangent=Vector3(0, 0, 1)))
    complete = capture_targets(definition, group, trunk, caps, (moved,) + targets[1:], checkpoint)
    _, roots = data()
    plan = next(construct(complete, roots, checkpoint))
    assert plan.source is complete.branches[0]
    assert plan.center_error_squared_mm2 == Fraction(0)
    assert all(proof.status == "certified" for proof in plan.terminations)
    assert any(
        frame.width[0] != frame.width[-1] or frame.thickness[0] != frame.thickness[-1]
        for frame in (span[0].frame for span in plan.patches)
    )
    assert audit(plan, checkpoint).status == "unresolved"
    assert "material_metrics" in plan.outstanding and "native_fidelity" in plan.outstanding
