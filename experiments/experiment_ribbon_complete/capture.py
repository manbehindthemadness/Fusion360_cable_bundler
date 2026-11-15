"""
Validate complete input correspondence without solving, fitting or importing Fusion.
"""

from __future__ import annotations

import math
from uuid import UUID

from cable_bundler.domain import CableEndAttachment, CableGroupType, HarnessDefinition
from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets

from .contracts import (
    BranchPlan,
    CapPort,
    CompleteRibbonInput,
    ConductorKey,
    FixedTarget,
    IncompleteRibbonInput,
    ResolvedBranch,
)

ACCURACY_MM = 0.01
# Unit-frame correspondence protects route/cap coordinate identity, not distance accuracy.
FRAME_IDENTITY = 1e-8


def finite(point: Vector3) -> bool:
    """
    Reject nonfinite coordinates before downstream vector arithmetic.
    """
    return all(math.isfinite(value) for value in (point.x, point.y, point.z))


def target(value: FixedTarget) -> None:
    """
    Require a persistent identity, finite point and usable unit material direction.
    """
    if (
        not isinstance(value.target_id, UUID)
        or not finite(value.point)
        or not finite(value.tangent)
        or abs(magnitude(value.tangent) - 1) > FRAME_IDENTITY
    ):
        raise IncompleteRibbonInput(
            "A resolved fixed target needs finite geometry and a unit direction"
        )


def same_point(actual: Vector3, expected: Vector3, context: str) -> None:
    """
    Apply the user dimensional accuracy without snapping or repairing an endpoint.
    """
    if (
        not finite(actual)
        or not finite(expected)
        or magnitude(difference(actual, expected)) > ACCURACY_MM
    ):
        raise IncompleteRibbonInput(f"{context} differs from its fixed target")


def same_direction(actual: Vector3, expected: Vector3, context: str) -> None:
    """
    Verify the direction identity needed to seed the same cap/route material frame.
    """
    if (
        not finite(actual)
        or magnitude(actual) <= 0
        or magnitude(difference(unit(actual), expected)) > FRAME_IDENTITY
    ):
        raise IncompleteRibbonInput(
            f"{context} does not preserve the authoritative material direction"
        )


def cap(port: CapPort, trunk: Targets, index: int) -> None:
    """
    Validate the supplied cap and every ordered center against the fixed trunk section.
    """
    target(port.target)
    center = trunk.start if index == 0 else trunk.end
    tangent = trunk.start_tangent if index == 0 else difference(Vector3(0, 0, 0), trunk.end_tangent)
    width = trunk.start_width if index == 0 else trunk.end_width
    same_point(port.target.point, center, "Joined cap center")
    same_direction(port.target.tangent, tangent, "Joined cap inward tangent")
    same_direction(port.width, width, "Ordered cap width")
    if port.target.target_id != port.connection_id or len(port.lane_centers) != trunk.lines:
        raise IncompleteRibbonInput(
            "A joined cap needs its connection identity and every ordered lane"
        )
    if (
        abs(magnitude(port.width) - 1) > FRAME_IDENTITY
        or abs(dot(port.width, port.target.tangent)) > FRAME_IDENTITY
    ):
        raise IncompleteRibbonInput("A joined cap material frame must be perpendicular")
    for lane, point in enumerate(port.lane_centers):
        expected = center.translated(width, (lane - (trunk.lines - 1) / 2) * trunk.diameter_mm)
        same_point(point, expected, "Ordered cap lane center")


def root(
    attachment: CableEndAttachment, nodes: dict[UUID, CableEndAttachment]
) -> CableEndAttachment:
    """
    Follow explicit parent identities, rejecting missing nodes and cycles rather than guessing a pin.
    """
    seen: set[UUID] = set()
    current = attachment
    while current.parent_attachment_id is not None:
        if current.attachment_id in seen or current.parent_attachment_id not in nodes:
            raise IncompleteRibbonInput("Attachment lineage is cyclic or missing its parent")
        seen.add(current.attachment_id)
        current = nodes[current.parent_attachment_id]
    return current


def branch_geometry(branch: ResolvedBranch) -> None:
    """
    Preserve usable complete cubic routes and their separately captured endpoint poses.
    """
    target(branch.terminal)
    target(branch.arrival)
    curves = branch.route.curves
    if not curves:
        raise IncompleteRibbonInput(
            "A complete reverse-loft branch requires its frozen cubic route"
        )
    for curve in curves:
        if not all(finite(p) for p in (curve.start, curve.control_a, curve.control_b, curve.end)):
            raise IncompleteRibbonInput("Frozen branch controls must be finite")
    same_point(curves[0].start, branch.terminal.point, "Branch terminal")
    same_point(curves[-1].end, branch.arrival.point, "Branch arrival")
    same_direction(curves[0].derivative(0), branch.terminal.tangent, "Branch terminal tangent")
    same_direction(curves[-1].derivative(1), branch.arrival.tangent, "Branch arrival tangent")
    for first, second in zip(curves, curves[1:]):
        same_point(first.end, second.start, "Consecutive branch curves")


def capture(
    definition: HarnessDefinition,
    group_id: UUID,
    trunk: Targets,
    caps: tuple[CapPort, ...],
    branches: tuple[ResolvedBranch, ...],
) -> CompleteRibbonInput:
    """
    Freeze every attachment branch in a two-end ribbon, preserving identities and input order.

    Missing targets/routes are incomplete input, never solver infeasibility.
    Multi-end trunk topologies need an explicit future assembly adapter; this
    entry refuses them rather than silently dropping their extra ends. Mechanical,
    native/contact, complete-length and six-percent-ending audits remain required.
    """
    matches = [g for g in definition.cable_groups if g.cable_group_id == group_id]
    if len(matches) != 1 or matches[0].group_type is not CableGroupType.RIBBON:
        raise IncompleteRibbonInput("One persistent ribbon group is required")
    group = matches[0]
    trunk = Targets.capture(trunk)
    if (
        len(group.connection_ids) != 2
        or tuple(p.connection_id for p in caps) != group.connection_ids
    ):
        raise IncompleteRibbonInput(
            "The two explicit caps must preserve the group's connection order"
        )
    # These are duplicate nominal inputs, not independently measured dimensions.
    if trunk.lines != group.ribbon_lines or trunk.diameter_mm != group.diameter_mm:
        raise IncompleteRibbonInput("Complete input dimensions differ from the fixed trunk")
    for index, port in enumerate(caps):
        cap(port, trunk, index)
    connections = {c.connection_id: c for c in definition.connections}
    if any(c not in connections for c in group.connection_ids):
        raise IncompleteRibbonInput("A declared ribbon connection is missing")
    nodes = {
        c: {a.attachment_id: a for a in connections[c].attachments} for c in group.connection_ids
    }
    expected = {(c, a) for c, attachments in nodes.items() for a in attachments}
    actual = [(b.leg.start_connection_id, b.leg.attachment_id) for b in branches]
    if set(actual) != expected or len(actual) != len(expected):
        raise IncompleteRibbonInput(
            "Every root and descendant attachment needs exactly one resolved branch"
        )
    if len({b.leg.route_id for b in branches}) != len(branches):
        raise IncompleteRibbonInput("Complete branch route identities must be unique")
    by_attachment = {b.leg.attachment_id: b for b in branches}
    if len(by_attachment) != len(branches):
        raise IncompleteRibbonInput("Attachment identities must be unambiguous across both ends")
    for attachments in nodes.values():
        roots = [a for a in attachments.values() if a.parent_attachment_id is None]
        pins = [int(a.pin_number) for a in roots if a.pin_number is not None]
        if len(roots) != group.ribbon_lines or sorted(pins) != list(
            range(1, group.ribbon_lines + 1)
        ):
            raise IncompleteRibbonInput(
                "Each end needs exactly one declared root for every ordered conductor"
            )
    planned = []
    for branch in branches:
        leg = branch.leg
        connection_id, attachment_id = leg.start_connection_id, leg.attachment_id
        if (
            leg.cable_group_id != group_id
            or not leg.is_connection_branch
            or leg.end_connection_id is not None
            or branch.route.cable_id != leg.route_id
        ):
            raise IncompleteRibbonInput(
                "Resolved branch provenance differs from its declared route leg"
            )
        assert connection_id is not None and attachment_id is not None
        attachment = nodes[connection_id][attachment_id]
        if attachment.target_kind is None:
            raise IncompleteRibbonInput(
                "An unresolved attachment cannot acquire an invented terminal target"
            )
        ancestor = root(attachment, nodes[connection_id])
        assert ancestor.pin_number is not None
        pin = int(ancestor.pin_number)
        if attachment.pin_number is not None and int(attachment.pin_number) != pin:
            raise IncompleteRibbonInput("A descendant cannot change its root conductor identity")
        if branch.terminal.target_id != attachment_id:
            raise IncompleteRibbonInput("A branch terminal must retain its attachment identity")
        if attachment.parent_attachment_id is None:
            port = caps[group.connection_ids.index(connection_id)]
            if branch.arrival.target_id != connection_id:
                raise IncompleteRibbonInput("A root must arrive at its own joined cap")
            same_point(branch.arrival.point, port.lane_centers[pin - 1], "Root conductor arrival")
            same_direction(branch.arrival.tangent, port.target.tangent, "Root cap direction")
        else:
            parent = by_attachment[attachment.parent_attachment_id]
            if branch.arrival.target_id != attachment.parent_attachment_id:
                raise IncompleteRibbonInput("A child must retain its explicit parent junction")
            same_point(branch.arrival.point, parent.terminal.point, "Child attachment junction")
        branch_geometry(branch)
        associations = tuple(
            a.association_id
            for a in definition.attachment_associations
            if attachment_id in a.attachment_ids
        )
        planned.append(
            BranchPlan(
                branch,
                attachment,
                ancestor.attachment_id,
                ConductorKey(group_id, pin),
                associations,
            )
        )
    conductors = tuple(ConductorKey(group_id, i) for i in range(1, group.ribbon_lines + 1))
    return CompleteRibbonInput(
        definition.harness_id,
        group,
        trunk,
        caps,
        conductors,
        tuple(planned),
        definition.attachment_associations,
    )
