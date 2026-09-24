"""
Shared definition lookup, topology, and persistence helpers for harness edits.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from ...domain import (
    AttachmentAssociationDefinition,
    CableGroupDefinition,
    HarnessDefinition,
    JunctionDefinition,
    PathwayDefinition,
    PathwayEndpoint,
    dumps,
    loads,
)
from .types import HarnessEditError, HarnessEditGateway


def _validate_offset(offset: int) -> None:
    """
    Require a single-position ordered move.
    """
    if offset not in {-1, 1}:
        raise ValueError("Ordered moves must use an offset of -1 or 1.")


def read_definition(
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> tuple[str, HarnessDefinition]:
    """
    Read both the exact serialized value and its parsed definition.
    """
    original = gateway.read_harness_definition(harness_id)
    return original, loads(original)


def require_pathway(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> PathwayDefinition:
    """
    Return an existing pathway or reject a stale palette identity.
    """
    pathway = next(
        (item for item in definition.pathways if item.pathway_id == pathway_id),
        None,
    )
    if pathway is None:
        raise ValueError("Selected pathway does not exist in this harness.")
    return pathway


def require_junction(
    definition: HarnessDefinition,
    junction_id: UUID,
) -> JunctionDefinition:
    """
    Return an existing junction or reject a stale palette identity.
    """
    junction = next(
        (item for item in definition.junctions if item.junction_id == junction_id),
        None,
    )
    if junction is None:
        raise ValueError("Selected junction does not exist in this harness.")
    return junction


def pathway_deletion_ids(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> set[UUID]:
    """
    Return a pathway and its downstream branch when every junction input is removed.

    A junction always remains. Its following pathways join the cascade only after every
    pathway entering that junction is already scheduled for deletion.
    """
    return _pathway_branch_deletion_ids(definition, {pathway_id})


def _pathway_branch_deletion_ids(
    definition: HarnessDefinition,
    root_pathway_ids: set[UUID],
) -> set[UUID]:
    """
    Return exclusively downstream pathways reached from one or more root pathways.
    """
    deleted_pathway_ids = set(root_pathway_ids)
    changed = True
    while changed:
        changed = False
        for junction in definition.junctions:
            incoming_pathway_ids = {
                relationship.pathway_id
                for relationship in junction.pathway_relationships
                if relationship.endpoint is PathwayEndpoint.END
            }
            if not incoming_pathway_ids or not incoming_pathway_ids <= deleted_pathway_ids:
                continue
            following_pathway_ids = {
                relationship.pathway_id
                for relationship in junction.pathway_relationships
                if relationship.endpoint is PathwayEndpoint.START
            }
            new_pathway_ids = following_pathway_ids - deleted_pathway_ids
            if new_pathway_ids:
                deleted_pathway_ids.update(new_pathway_ids)
                changed = True
    return deleted_pathway_ids


def replace_pathway(
    definition: HarnessDefinition,
    updated_pathway: PathwayDefinition,
) -> tuple[PathwayDefinition, ...]:
    """
    Replace one pathway without changing collection order.
    """
    return tuple(
        updated_pathway if item.pathway_id == updated_pathway.pathway_id else item
        for item in definition.pathways
    )


def prune_cable_groups(
    groups: tuple[CableGroupDefinition, ...],
    retained_connection_ids: set[UUID],
) -> tuple[CableGroupDefinition, ...]:
    """
    Remove unavailable members and discard groups that no longer connect two ends.
    """
    pruned = (
        replace(
            group,
            connection_ids=tuple(
                connection_id
                for connection_id in group.connection_ids
                if connection_id in retained_connection_ids
            ),
        )
        for group in groups
    )
    return tuple(group for group in pruned if len(group.connection_ids) >= 2)


def prune_attachment_associations(
    associations: tuple[AttachmentAssociationDefinition, ...],
    retained_attachment_ids: set[UUID],
) -> tuple[AttachmentAssociationDefinition, ...]:
    """
    Remove associations whose attachment nodes were deleted with their owner.
    """
    return tuple(
        association
        for association in associations
        if all(item in retained_attachment_ids for item in association.attachment_ids)
    )


def _related_pathway_endpoints(
    definition: HarnessDefinition,
    pathway_id: UUID,
) -> set[PathwayEndpoint]:
    """
    Return endpoint boundaries anchored by junctions or standalone ends.
    """
    junction_endpoints = {
        relationship.endpoint
        for junction in definition.junctions
        for relationship in junction.pathway_relationships
        if relationship.pathway_id == pathway_id
    }
    standalone_endpoints = {
        end.endpoint for end in definition.standalone_ends if end.pathway_id == pathway_id
    }
    return junction_endpoints | standalone_endpoints


def locked_pathway_control_indexes(
    definition: HarnessDefinition,
    pathway: PathwayDefinition,
) -> set[int]:
    """
    Return control positions that define anchored pathway boundaries.
    """
    if not pathway.ordered_control_ids:
        return set()
    endpoints = _related_pathway_endpoints(definition, pathway.pathway_id)
    locked: set[int] = set()
    if PathwayEndpoint.START in endpoints:
        locked.add(0)
    if PathwayEndpoint.END in endpoints:
        locked.add(len(pathway.ordered_control_ids) - 1)
    return locked


def clamp_pathway_insertion_index(
    definition: HarnessDefinition,
    pathway: PathwayDefinition,
    requested_index: int,
) -> int:
    """
    Clamp new controls inside endpoint boundaries reserved by junctions.
    """
    endpoints = _related_pathway_endpoints(definition, pathway.pathway_id)
    minimum = 1 if PathwayEndpoint.START in endpoints else 0
    maximum = (
        len(pathway.ordered_control_ids) - 1
        if PathwayEndpoint.END in endpoints
        else len(pathway.ordered_control_ids)
    )
    if maximum < minimum:
        raise ValueError(
            "A one-control pathway related at both ends has no interior insertion position."
        )
    return min(max(requested_index, minimum), maximum)


def persist_definition(
    harness_id: UUID,
    original_serialized: str,
    definition: HarnessDefinition,
    gateway: HarnessEditGateway,
) -> None:
    """
    Persist one edit and restore the exact prior value after failure.
    """
    try:
        gateway.replace_harness_definition(harness_id, dumps(definition))
    except Exception as persistence_error:
        try:
            gateway.replace_harness_definition(harness_id, original_serialized)
        except Exception as rollback_error:
            message = (
                f"Failed to persist the harness edit and restore its definition: {rollback_error}"
            )
            raise HarnessEditError(message) from persistence_error
        raise
