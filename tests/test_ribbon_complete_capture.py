"""
Verify complete-input coverage and preservation without solver or native construction.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application.cable_group_routes import CableGroupControlStep, CableGroupRouteLeg
from cable_bundler.domain import (
    AttachmentAssociationDefinition,
    AttachmentTargetKind,
    CableEndAttachment,
    CableGroupDefinition,
    CableGroupType,
    Connection,
    HarnessDefinition,
    RoutingMode,
)
from cable_bundler.routing import RoutePreview
from cable_bundler.routing.geometry import CubicBezier, Vector3, difference, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_complete.capture import capture, root
from experiments.experiment_ribbon_complete.contracts import (
    CapPort,
    FixedTarget,
    IncompleteRibbonInput,
    ResolvedBranch,
)

Inputs = tuple[HarnessDefinition, UUID, Targets, tuple[CapPort, ...], tuple[ResolvedBranch, ...]]


def branch(
    connection: UUID, attachment: UUID, pin: int, side: int, destination: Vector3, target_id: UUID
) -> ResolvedBranch:
    """
    Supply a fixed linear route with explicit external and arrival target identities.
    """
    start = destination.translated(Vector3(-1 if side == 0 else 1, 0, 0), 3)
    tangent = unit(difference(destination, start))
    curve = CubicBezier(
        start, start.translated(tangent, 1), start.translated(tangent, 2), destination
    )
    route_id = UUID(int=10000 + side * 1000 + pin)
    steps = (
        CableGroupControlStep(UUID(int=20000 + pin)),
        CableGroupControlStep(UUID(int=30000 + pin), True),
    )
    leg = CableGroupRouteLeg(
        route_id,
        UUID(int=1),
        "branch",
        connection,
        None,
        steps,
        (UUID(int=40000 + pin),),
        is_connection_branch=True,
        attachment_id=attachment,
    )
    route = RoutePreview(route_id, "branch", (start, destination), (curve,))
    return ResolvedBranch(
        leg,
        route,
        FixedTarget(attachment, start, tangent),
        FixedTarget(target_id, destination, tangent),
    )


def inputs(lines: int = 2, child: bool = False) -> Inputs:
    """
    Build complete two-end domain inputs with persistent pin associations and optional descendant.
    """
    group_id = UUID(int=1)
    connection_ids = (UUID(int=10), UUID(int=20))
    group = CableGroupDefinition(
        group_id,
        connection_ids,
        diameter_mm=0.75,
        group_type=CableGroupType.RIBBON,
        ribbon_lines=lines,
    )
    trunk = Targets(
        "complete input",
        Vector3(0, 0, 0),
        Vector3(10, 0, 0),
        Vector3(1, 0, 0),
        Vector3(1, 0, 0),
        Vector3(0, 1, 0),
        Vector3(0, 1, 0),
        lines,
        0.75,
    )
    connections = []
    caps = []
    resolved = []
    for side, connection_id in enumerate(connection_ids):
        center = trunk.start if side == 0 else trunk.end
        tangent = Vector3(1 if side == 0 else -1, 0, 0)
        centers = tuple(
            center.translated(Vector3(0, 1, 0), (i - (lines - 1) / 2) * 0.75) for i in range(lines)
        )
        attachments = []
        for pin, point in enumerate(centers, 1):
            identity = UUID(int=100 + side * 1000 + pin)
            attachments.append(
                CableEndAttachment(
                    AttachmentTargetKind.PROFILE
                    if child and side == 0 and pin == 1
                    else AttachmentTargetKind.CONSTRUCTION_POINT,
                    f"point-{identity}",
                    "terminal",
                    attachment_id=identity,
                    pin_number=str(pin),
                )
            )
            resolved.append(branch(connection_id, identity, pin, side, point, connection_id))
        if child and side == 0:
            identity = UUID(int=90000)
            parent = attachments[0].attachment_id
            attachments.append(
                CableEndAttachment(
                    AttachmentTargetKind.CONSTRUCTION_POINT,
                    "child-point",
                    "child",
                    attachment_id=identity,
                    parent_attachment_id=parent,
                )
            )
            resolved.append(
                branch(connection_id, identity, 99, side, resolved[0].terminal.point, parent)
            )
        connections.append(
            Connection(
                connection_id,
                "cap",
                f"cap-{side}",
                attachment=attachments[0],
                additional_attachments=tuple(attachments[1:]),
            )
        )
        caps.append(
            CapPort(
                connection_id,
                FixedTarget(connection_id, center, tangent),
                Vector3(0, 1, 0),
                centers,
            )
        )
    associations = tuple(
        AttachmentAssociationDefinition(
            UUID(int=50000 + pin), (UUID(int=100 + pin), UUID(int=1100 + pin))
        )
        for pin in range(1, lines + 1)
    )
    definition = HarnessDefinition(
        40,
        UUID(int=2),
        "complete",
        RoutingMode.ROUTING_GATES,
        tuple(connections),
        (),
        (),
        cable_groups=(group,),
        attachment_associations=associations,
    )
    return definition, group_id, trunk, tuple(caps), tuple(reversed(resolved))


@pytest.mark.parametrize("lines", (2, 5, 10))
def test_capture_keeps_routes_control_order_and_associations_without_regeneration(
    lines: int,
) -> None:
    """
    Preserve exact caller values and root identities across different conductor counts.
    """
    source = inputs(lines)
    plan = capture(*source)
    assert plan.group is source[0].cable_groups[0]
    assert plan.trunk == source[2] and plan.caps is source[3]
    assert tuple(p.source for p in plan.branches) == source[4]
    assert all(p.source is original for p, original in zip(plan.branches, source[4]))
    assert [c.pin_number for c in plan.conductors] == list(range(1, lines + 1))
    assert plan.associations is source[0].attachment_associations
    for item in plan.branches:
        assert item.root_attachment_id == item.attachment.attachment_id
        assert item.association_ids == (UUID(int=50000 + item.conductor.pin_number),)
        assert item.source.leg.control_steps[1].reversed


def test_descendant_keeps_parent_line_identity_and_explicit_junction() -> None:
    """
    A child inherits its actual root pin while retaining its own branch/attachment identity.
    """
    plan = capture(*inputs(child=True))
    child = next(b for b in plan.branches if b.attachment.parent_attachment_id is not None)
    assert child.conductor.pin_number == 1
    assert child.root_attachment_id == child.attachment.parent_attachment_id
    assert child.source.arrival.target_id == child.attachment.parent_attachment_id


def test_missing_branch_cannot_be_reported_as_complete_input() -> None:
    """
    Joined caps and a subset of branches never count as complete ribbon coverage.
    """
    definition, group_id, trunk, caps, branches = inputs()
    with pytest.raises(IncompleteRibbonInput, match="Every root"):
        capture(definition, group_id, trunk, caps, branches[:-1])


def test_reordered_lane_centers_do_not_change_conductor_mapping_to_obtain_a_pass() -> None:
    """
    Geometrically permuted cap lanes fail instead of reassigning persistent identities.
    """
    definition, group_id, trunk, caps, branches = inputs()
    altered = replace(caps[0], lane_centers=tuple(reversed(caps[0].lane_centers)))
    with pytest.raises(IncompleteRibbonInput, match="lane center"):
        capture(definition, group_id, trunk, (altered, caps[1]), branches)


@pytest.mark.parametrize("delta,accepted", ((0.009, True), (0.0101, False)))
def test_dimensional_policy_preserves_captured_targets_instead_of_snapping(
    delta: float, accepted: bool
) -> None:
    """
    Apply 0.01mm endpoint comparison and retain every accepted source coordinate verbatim.
    """
    definition, group_id, trunk, caps, branches = inputs()
    original = branches[0]
    target = replace(
        original.terminal, point=original.terminal.point.translated(Vector3(0, 1, 0), delta)
    )
    changed = replace(original, terminal=target)
    supplied = (changed,) + branches[1:]
    if accepted:
        plan = capture(definition, group_id, trunk, caps, supplied)
        assert plan.branches[0].source.terminal is target
        assert plan.branches[0].source.route is original.route
    else:
        with pytest.raises(IncompleteRibbonInput, match="Branch terminal"):
            capture(definition, group_id, trunk, caps, supplied)


def test_route_identity_mismatch_is_not_a_dimensional_tolerance_case() -> None:
    """
    Refuse a route belonging to another branch even when all geometric coordinates coincide.
    """
    definition, group_id, trunk, caps, branches = inputs()
    changed = replace(branches[0], route=replace(branches[0].route, cable_id=UUID(int=99999)))
    with pytest.raises(IncompleteRibbonInput, match="provenance"):
        capture(definition, group_id, trunk, caps, (changed,) + branches[1:])


def test_lineage_cycles_are_incomplete_data_not_infeasible_geometry() -> None:
    """
    Stop a corrupt parent graph before any route or native work.
    """
    first = CableEndAttachment(None, attachment_id=UUID(int=1), parent_attachment_id=UUID(int=2))
    second = CableEndAttachment(None, attachment_id=UUID(int=2), parent_attachment_id=UUID(int=1))
    with pytest.raises(IncompleteRibbonInput, match="cyclic"):
        root(first, {first.attachment_id: first, second.attachment_id: second})
