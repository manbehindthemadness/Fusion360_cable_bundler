"""
Retain immutable complete-ribbon inputs without inventing final connection targets.

Structural input completeness is not geometry construction or mechanical acceptance.
The initial supported topology is one joined trunk between two declared ends,
including all root and descendant attachment branches at those ends.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cable_bundler.application.cable_group_routes import CableGroupRouteLeg
from cable_bundler.domain import (
    AttachmentAssociationDefinition,
    CableEndAttachment,
    CableGroupDefinition,
)
from cable_bundler.routing import RoutePreview
from cable_bundler.routing.geometry import Vector3
from devtools.ribbon_analysis.contracts import Targets


class IncompleteRibbonInput(ValueError):
    """
    Report missing or ambiguous complete-output data, never geometric infeasibility.
    """


@dataclass(frozen=True)
class FixedTarget:
    """
    Preserve an explicitly resolved endpoint and its increasing-route tangent.
    """

    target_id: UUID
    point: Vector3
    tangent: Vector3


@dataclass(frozen=True)
class CapPort:
    """
    Associate one ordered harness connection with its authoritative joined-cap frame.

    Tangent points into the trunk. Width retains increasing conductor order.
    Lane centers are explicit captured inputs, not fitted during native lofting.
    """

    connection_id: UUID
    target: FixedTarget
    width: Vector3
    lane_centers: tuple[Vector3, ...]


@dataclass(frozen=True)
class ResolvedBranch:
    """
    Retain the caller's existing routed leg and both independently resolved targets.

    Routes traverse terminal to ribbon/parent. A root arrives at its joined-cap
    lane center; a descendant arrives at its saved parent attachment target.
    """

    leg: CableGroupRouteLeg
    route: RoutePreview
    terminal: FixedTarget
    arrival: FixedTarget


@dataclass(frozen=True)
class ConductorKey:
    """
    Preserve the existing group's numbered root identity without creating replacement UUIDs.
    """

    cable_group_id: UUID
    pin_number: int


@dataclass(frozen=True)
class BranchPlan:
    """
    Bind one unchanged branch to its complete lineage and material conductor identity.
    """

    source: ResolvedBranch
    attachment: CableEndAttachment
    root_attachment_id: UUID
    conductor: ConductorKey
    association_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class CompleteRibbonInput:
    """
    Freeze complete two-end input coverage while leaving physical audits explicitly outstanding.

    Branch order, controls, route objects, terminal poses and association order
    remain caller-owned input values. No solver, native authoring, target repair,
    length allowance or mechanical-success flag is introduced by capture.
    """

    harness_id: UUID
    group: CableGroupDefinition
    trunk: Targets
    caps: tuple[CapPort, ...]
    conductors: tuple[ConductorKey, ...]
    branches: tuple[BranchPlan, ...]
    associations: tuple[AttachmentAssociationDefinition, ...]
