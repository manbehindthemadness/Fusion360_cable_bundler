"""
Author complete analytical ending targets from a fresh gym scene before solving.

This fixture does not certify feasibility. Each terminal is one declared extension
outside its cap along the original inward direction; all roots/identities and both
ends are frozen before any route is calculated. No outcome-based authoring occurs.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid5

from cable_bundler.application.cable_group_routes import CableGroupRouteLeg
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
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.gym.scene import Scene
from experiments.experiment_ribbon_complete.branch_construction import BranchRoot
from experiments.experiment_ribbon_complete.branch_targets import BranchTargets
from experiments.experiment_ribbon_complete.contracts import CapPort, FixedTarget
from experiments.experiment_ribbon_complete.execution import RibbonTargets
from experiments.experiment_ribbon_complete.root_profiles import bind_frame, partition


def author(scene: Scene, namespace: UUID) -> RibbonTargets:
    """
    Fix one-diameter endings for every lane at both caps, with no supplied route.

    This is the precommitted fixture policy, not a solver decision or ending-length
    repair. Missing descendants are not omitted: this input declares none.
    Source cap frames are planned frames; native correspondence is still unmeasured.
    """
    trunk = scene.targets
    group_id = uuid5(namespace, "group")
    connection_ids = tuple(uuid5(namespace, f"connection-{side}") for side in range(2))
    group = CableGroupDefinition(
        group_id,
        connection_ids,
        diameter_mm=trunk.diameter_mm,
        group_type=CableGroupType.RIBBON,
        ribbon_lines=trunk.lines,
    )
    profiles = partition(trunk.lines, trunk.diameter_mm)
    caps, branches, roots, connections = [], [], [], []
    attached: dict[tuple[int, int], UUID] = {}
    for side, connection_id in enumerate(connection_ids):
        label: Literal["start", "end"] = "start" if side == 0 else "end"
        center = getattr(trunk, label)
        forward = getattr(trunk, label + "_tangent")
        inward = forward if side == 0 else Vector3(-forward.x, -forward.y, -forward.z)
        width = getattr(trunk, label + "_width")
        centers = tuple(
            center.translated(width, (pin - (trunk.lines + 1) / 2) * trunk.diameter_mm)
            for pin in range(1, trunk.lines + 1)
        )
        caps.append(
            CapPort(connection_id, FixedTarget(connection_id, center, inward), width, centers)
        )
        frame = bind_frame(trunk, label, center, inward)
        attachments = []
        for pin, arrival in enumerate(centers, 1):
            attachment_id = uuid5(namespace, f"attachment-{side}-{pin}")
            attached[side, pin] = attachment_id
            attachments.append(
                CableEndAttachment(
                    AttachmentTargetKind.CONSTRUCTION_POINT,
                    f"frozen-terminal-{side}-{pin}",
                    f"terminal-{side}-{pin}",
                    attachment_id=attachment_id,
                    pin_number=str(pin),
                )
            )
            route_id = uuid5(namespace, f"route-{side}-{pin}")
            leg = CableGroupRouteLeg(
                route_id,
                group_id,
                f"ending-{side}-{pin}",
                connection_id,
                None,
                (),
                (),
                is_connection_branch=True,
                attachment_id=attachment_id,
            )
            terminal = arrival.translated(inward, -trunk.diameter_mm)
            branches.append(
                BranchTargets(
                    leg,
                    FixedTarget(attachment_id, terminal, inward),
                    FixedTarget(connection_id, arrival, inward),
                )
            )
            roots.append(
                BranchRoot(
                    route_id,
                    profiles[pin - 1],
                    (pin - (trunk.lines + 1) / 2) * trunk.diameter_mm,
                    frame,
                )
            )
        connections.append(
            Connection(
                connection_id,
                f"cap-{side}",
                f"frozen-cap-{side}",
                attachment=attachments[0],
                additional_attachments=tuple(attachments[1:]),
            )
        )
    associations = tuple(
        AttachmentAssociationDefinition(
            uuid5(namespace, f"association-{pin}"), (attached[0, pin], attached[1, pin])
        )
        for pin in range(1, trunk.lines + 1)
    )
    definition = HarnessDefinition(
        40,
        namespace,
        "fresh complete diagnostic",
        RoutingMode.ROUTING_GATES,
        tuple(connections),
        (),
        (),
        cable_groups=(group,),
        attachment_associations=associations,
    )
    return RibbonTargets(definition, group_id, trunk, tuple(caps), tuple(branches), tuple(roots))
