"""
Exercise target-driven branch creation and its existing complete-input/allowance consumers.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application.cable_group_routes import CableGroupControlStep
from cable_bundler.routing.geometry import Vector3, difference, magnitude, unit
from experiments.experiment_ribbon_complete.branch_targets import (
    BranchControlPose,
    BranchTargets,
    UnresolvedBranchConstruction,
    capture_targets,
    initialize,
)
from experiments.experiment_ribbon_complete.contracts import FixedTarget, IncompleteRibbonInput
from experiments.experiment_ribbon_complete.curve_lengths import LengthWork, iter_branch_lengths
from experiments.experiment_ribbon_complete.lengths import AllowanceState, audit_end_allowance
from tests.test_ribbon_complete_capture import inputs
from tests.test_ribbon_complete_lengths import checkpoint, measurements


def boundaries(lines: int = 2, child: bool = False) -> tuple[BranchTargets, ...]:
    """
    Discard analytical fixture routes and supply explicit poses for its declared controls.
    """
    output = []
    for branch in inputs(lines, child)[-1]:
        delta = difference(branch.arrival.point, branch.terminal.point)
        controls = tuple(
            BranchControlPose(
                step,
                FixedTarget(
                    step.control_id,
                    branch.terminal.point.translated(delta, (i + 1) / 3),
                    branch.terminal.tangent,
                ),
            )
            for i, step in enumerate(branch.leg.control_steps)
        )
        output.append(BranchTargets(branch.leg, branch.terminal, branch.arrival, controls))
    return tuple(output)


@pytest.mark.parametrize("lines,child", ((1, False), (2, True), (5, False), (10, False)))
def test_targets_create_every_branch_with_existing_lineage_and_allowance_rejection(
    lines: int, child: bool
) -> None:
    """
    Both ends and descendants reach actual route measurements without receiving a physical pass.
    """
    definition, group, trunk, caps, _old_routes = inputs(lines, child)
    sources = boundaries(lines, child)
    result = capture_targets(definition, group, trunk, caps, sources, checkpoint)
    assert len(result.branches) == 2 * lines + int(child)
    for branch, source in zip(result.branches, sources):
        assert branch.source.leg is source.leg
        assert branch.source.terminal is source.terminal
        assert branch.source.arrival is source.arrival
        assert branch.source.route.cable_id == source.leg.route_id
        assert branch.source.route.points[1:-1] == tuple(c.pose.point for c in source.controls)
    assert result.associations is definition.attachment_associations
    work = LengthWork(3 * len(sources), checkpoint)
    measured = tuple(iter_branch_lengths(result, work, "analytical target initializer"))
    assert all(
        value.length.lower_mm <= 3 <= value.length.upper_mm
        and value.length.upper_mm - value.length.lower_mm <= 0.01
        for _, value in measured
    )
    trunks, _ = measurements(result, trunk=10)
    findings = audit_end_allowance(
        result, trunks, tuple(row for row, _ in measured), checkpoint=checkpoint
    )
    assert all(row.state is AllowanceState.FAIL for row in findings)
    if child:
        descendant = next(b for b in result.branches if b.attachment.parent_attachment_id)
        assert descendant.conductor.pin_number == 1
        assert descendant.root_attachment_id == UUID(int=101)


def test_spatial_poses_constrain_every_cubic_endpoint_and_directed_tangent() -> None:
    """
    A genuinely spatial multi-control route preserves each supplied pose and reversal metadata.
    """
    source = boundaries()[0]
    points = (Vector3(-4, 0, 1), Vector3(-3, 2, 0), Vector3(-1, 1, 3), Vector3(0, 0, 0))
    tangents = tuple(
        unit(v) for v in (Vector3(1, 1, 0), Vector3(1, 0, 1), Vector3(0, -1, 1), Vector3(1, 0, 0))
    )
    poses = tuple(
        FixedTarget(UUID(int=800 + i), p, t) for i, (p, t) in enumerate(zip(points, tangents))
    )
    steps = (
        CableGroupControlStep(poses[1].target_id),
        CableGroupControlStep(poses[2].target_id, True),
    )
    changed = BranchTargets(
        replace(source.leg, control_steps=steps),
        poses[0],
        poses[-1],
        tuple(BranchControlPose(step, pose) for step, pose in zip(steps, poses[1:-1])),
    )
    result = initialize(changed, checkpoint)
    assert result.leg.control_steps == steps and result.route.points == points
    for curve, first, following in zip(result.route.curves, poses, poses[1:]):
        assert curve.point(0) == first.point and curve.point(1) == following.point
        assert magnitude(difference(unit(curve.derivative(0)), first.tangent)) < 1e-12
        assert magnitude(difference(unit(curve.derivative(1)), following.tangent)) < 1e-12


def test_changed_fixed_terminal_changes_geometry_without_reusing_a_route() -> None:
    """
    Persistent identities cannot retrieve a previous answer when target geometry changes.
    """
    source = boundaries()[0]
    original = initialize(source, checkpoint)
    moved = replace(source.terminal, point=source.terminal.point.translated(Vector3(0, 0, 1), 0.5))
    changed = initialize(replace(source, terminal=moved), checkpoint)
    assert changed.route.cable_id == original.route.cable_id
    assert changed.route.curves[0].start == moved.point
    assert changed.route.curves != original.route.curves


@pytest.mark.parametrize("kind", ("missing", "order", "reversed", "identity"))
def test_missing_or_changed_control_provenance_is_never_silently_ignored(kind: str) -> None:
    """
    Equivalent positions cannot excuse missing poses, control reordering or changed direction/identity.
    """
    source = boundaries()[0]
    controls = source.controls
    if kind == "missing":
        controls = controls[:-1]
    elif kind == "order":
        controls = tuple(reversed(controls))
    elif kind == "reversed":
        controls = (
            replace(controls[0], step=replace(controls[0].step, reversed=True)),
            controls[1],
        )
    else:
        controls = (
            replace(controls[0], pose=replace(controls[0].pose, target_id=UUID(int=99))),
            controls[1],
        )
    with pytest.raises(IncompleteRibbonInput, match="control"):
        initialize(replace(source, controls=controls), checkpoint)


def test_coincident_poses_remain_unresolved_without_fabricating_a_loop() -> None:
    """
    Coincident endpoint positions do not establish either a zero-length branch or infeasibility.
    """
    source = boundaries()[0]
    changed = replace(
        source.controls[0], pose=replace(source.controls[0].pose, point=source.terminal.point)
    )
    with pytest.raises(UnresolvedBranchConstruction, match="Distinct"):
        initialize(replace(source, controls=(changed, source.controls[1])), checkpoint)


def test_complete_capture_still_rejects_a_missing_ending() -> None:
    """
    Target-based initialization cannot drop a branch to make complete input appear valid.
    """
    definition, group, trunk, caps, _ = inputs()
    with pytest.raises(IncompleteRibbonInput, match="Every root"):
        capture_targets(definition, group, trunk, caps, boundaries()[:-1], checkpoint)


def test_one_callers_stop_propagates_across_the_whole_branch_sequence() -> None:
    """
    A latched resource stop cannot be swallowed or replaced by a per-branch allocation.
    """
    definition, group, trunk, caps, _ = inputs()
    calls = 0

    def stop() -> None:
        """
        Allow the first branch, then refuse work without resetting the shared counter.
        """
        nonlocal calls
        calls += 1
        if calls >= 12:
            raise RuntimeError("shared resource stop")

    with pytest.raises(RuntimeError, match="shared resource stop"):
        capture_targets(definition, group, trunk, caps, boundaries(), stop)
    assert calls == 12


def test_subresolution_handles_are_unresolved_without_changing_fixed_targets() -> None:
    """
    The existing coordinate-direction floor is not a physical minimum ending length.
    """
    source = boundaries()[0]
    origin = replace(source.terminal, point=Vector3(0, 0, 0))
    arrival = replace(source.arrival, point=Vector3(1e-15, 0, 0))
    changed = BranchTargets(replace(source.leg, control_steps=()), origin, arrival)
    with pytest.raises(UnresolvedBranchConstruction, match="cannot be represented"):
        initialize(changed, checkpoint)
    assert changed.arrival.point == Vector3(1e-15, 0, 0)
