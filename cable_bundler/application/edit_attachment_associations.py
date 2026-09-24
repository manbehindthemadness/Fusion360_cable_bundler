"""Persist explicit groups between terminal cable-end attachment nodes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Optional, Union
from uuid import UUID, uuid4

from ..domain import AttachmentAssociationDefinition, HarnessDefinition, validate_harness
from .harness_edits.support import persist_definition, read_definition
from .harness_edits.types import HarnessEditGateway


@dataclass(frozen=True)
class AttachmentAssociationPair:
    """
    Pair one terminal attachment from each selected diagram node.
    """

    left_attachment_id: UUID
    right_attachment_id: UUID


@dataclass(frozen=True)
class AttachmentAssociationGroup:
    """
    Stage one association with each attachment listed once.

    An existing identity may be retained while its membership changes.
    """

    attachment_ids: tuple[UUID, ...]
    association_id: Optional[UUID] = None


@dataclass(frozen=True)
class AttachmentAssociationAnchor:
    """
    Identify a cable end, subtree, route node, or other ends of a cable group.
    """

    connection_id: Optional[UUID] = None
    attachment_id: Optional[UUID] = None
    node_kind: str = "connection"
    node_id: Optional[UUID] = None
    candidate_attachment_ids: Optional[tuple[UUID, ...]] = None


def attachment_association_candidates(
    definition: HarnessDefinition,
    anchor: AttachmentAssociationAnchor,
) -> tuple[UUID, ...]:
    """
    Return terminal attachment IDs represented by one selected diagram node.
    """
    if anchor.node_kind == "cableGroupRemainder":
        group = next(
            (item for item in definition.cable_groups if item.cable_group_id == anchor.node_id),
            None,
        )
        if group is None or anchor.connection_id not in group.connection_ids:
            raise ValueError("Selected cable-group remainder no longer exists.")
        connection_ids = set(group.connection_ids) - {anchor.connection_id}
        roots = tuple(
            attachment
            for connection in definition.connections
            if connection.connection_id in connection_ids
            for attachment in connection.attachment_children(None)
        )
    elif anchor.node_kind in ("pathway", "junction"):
        graph: dict[tuple[str, UUID], set[tuple[str, UUID]]] = {
            ("pathway", pathway.pathway_id): set() for pathway in definition.pathways
        }
        for junction in definition.junctions:
            junction_key = ("junction", junction.junction_id)
            graph.setdefault(junction_key, set())
            for relationship in junction.pathway_relationships:
                pathway_key = ("pathway", relationship.pathway_id)
                graph.setdefault(pathway_key, set()).add(junction_key)
                graph[junction_key].add(pathway_key)
        start = (anchor.node_kind, anchor.node_id)
        if anchor.node_id is None or start not in graph:
            raise ValueError("Selected route node no longer exists.")
        route_nodes = {start}
        pending_nodes = [start]
        while pending_nodes:
            current = pending_nodes.pop()
            for neighbor in graph[current] - route_nodes:
                route_nodes.add(neighbor)
                pending_nodes.append(neighbor)
        connection_ids = {
            end.connection_id
            for end in definition.standalone_ends
            if ("pathway", end.pathway_id) in route_nodes
        }
        roots = tuple(
            attachment
            for connection in definition.connections
            if connection.connection_id in connection_ids
            for attachment in connection.attachment_children(None)
        )
    else:
        connection = next(
            (item for item in definition.connections if item.connection_id == anchor.connection_id),
            None,
        )
        if connection is None:
            raise ValueError("Selected cable-end node no longer exists.")
        if anchor.attachment_id is None:
            roots = connection.attachment_children(None)
        else:
            selected = next(
                (
                    item
                    for item in connection.attachments
                    if item.attachment_id == anchor.attachment_id
                ),
                None,
            )
            if selected is None:
                raise ValueError("Selected attachment node no longer exists.")
            roots = (selected,)
    leaves: list[UUID] = []
    if anchor.node_kind in ("pathway", "junction", "cableGroupRemainder"):
        connection_by_attachment = {
            attachment.attachment_id: connection
            for connection in definition.connections
            for attachment in connection.attachments
        }
        pending = [(connection_by_attachment[item.attachment_id], item) for item in roots]
    else:
        pending = [(connection, item) for item in roots]
    while pending:
        owner, current = pending.pop()
        children = owner.attachment_children(current.attachment_id)
        if children:
            pending.extend((owner, child) for child in reversed(children))
        else:
            leaves.append(current.attachment_id)
    candidates = tuple(leaves)
    if anchor.candidate_attachment_ids is None:
        return candidates
    requested = set(anchor.candidate_attachment_ids)
    if len(requested) != len(anchor.candidate_attachment_ids) or not requested.issubset(candidates):
        raise ValueError("Association candidates do not belong to the selected route node.")
    if anchor.node_kind == "cableGroupRemainder" and requested != set(candidates):
        raise ValueError("Cable-group association candidates changed since selection.")
    return tuple(item_id for item_id in candidates if item_id in requested)


def save_attachment_associations(
    harness_id: UUID,
    left_anchor: AttachmentAssociationAnchor,
    right_anchor: AttachmentAssociationAnchor,
    groups: tuple[Union[AttachmentAssociationGroup, AttachmentAssociationPair], ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> None:
    """
    Replace editable cross-panel associations while preserving those outside them.

    Outside associations remain intact unless their complete membership is
    explicitly brought into a submitted group. Multiple such associations may
    be merged, but none may be split or silently lose a member.
    """
    if left_anchor == right_anchor:
        raise ValueError("Association nodes must be different.")
    original, definition = read_definition(harness_id, gateway)
    left_ids = set(attachment_association_candidates(definition, left_anchor))
    right_ids = set(attachment_association_candidates(definition, right_anchor))
    if left_ids.intersection(right_ids):
        raise ValueError("The selected nodes have overlapping terminal connections.")
    selected_ids = left_ids | right_ids
    protected_associations = {
        association.association_id: association
        for association in definition.attachment_associations
        if not (
            set(association.attachment_ids).issubset(selected_ids)
            and bool(set(association.attachment_ids).intersection(left_ids))
            and bool(set(association.attachment_ids).intersection(right_ids))
        )
    }
    normalized = tuple(
        group
        if isinstance(group, AttachmentAssociationGroup)
        else AttachmentAssociationGroup((group.left_attachment_id, group.right_attachment_id))
        for group in groups
    )
    grouped_members: list[UUID] = []
    consumed_protected_ids: set[UUID] = set()
    for group in normalized:
        members = group.attachment_ids
        member_ids = set(members)
        if len(members) < 2 or len(member_ids) != len(members):
            raise ValueError("An association needs at least two distinct attachment nodes.")
        if not member_ids.intersection(selected_ids):
            raise ValueError("An association needs a node from a selected hierarchy.")
        outside_members: set[UUID] = set()
        protected_in_group: set[UUID] = set()
        for association_id, association in protected_associations.items():
            original_members = set(association.attachment_ids)
            if not member_ids.intersection(original_members):
                continue
            if not original_members.intersection(selected_ids):
                raise ValueError(
                    "An association outside the selected hierarchies cannot be changed."
                )
            if not original_members.issubset(member_ids):
                raise ValueError("An existing outside association cannot be split.")
            consumed_protected_ids.add(association_id)
            protected_in_group.add(association_id)
            outside_members.update(original_members - selected_ids)
        if member_ids - selected_ids != outside_members:
            raise ValueError(
                "An association contains an unrelated node outside the selected hierarchies."
            )
        if not protected_in_group and (
            not member_ids.intersection(left_ids) or not member_ids.intersection(right_ids)
        ):
            raise ValueError("An association needs a node from each selected hierarchy.")
        grouped_members.extend(members)
    if len(grouped_members) != len(set(grouped_members)):
        raise ValueError("An attachment node may appear in only one association.")

    retained: list[AttachmentAssociationDefinition] = []
    reusable_ids: dict[frozenset[UUID], UUID] = {}
    editable_ids: set[UUID] = set()
    for association in definition.attachment_associations:
        members = set(association.attachment_ids)
        left_member = members.intersection(left_ids)
        right_member = members.intersection(right_ids)
        editable = (
            members.issubset(left_ids | right_ids) and bool(left_member) and bool(right_member)
        )
        if editable:
            reusable_ids[frozenset(members)] = association.association_id
            editable_ids.add(association.association_id)
        elif association.association_id not in consumed_protected_ids:
            retained.append(association)

    used_ids = {
        definition.harness_id,
        *(connection.connection_id for connection in definition.connections),
        *(control.control_id for control in definition.controls),
        *(pathway.pathway_id for pathway in definition.pathways),
        *(junction.junction_id for junction in definition.junctions),
        *(group.cable_group_id for group in definition.cable_groups),
        *(
            attachment.attachment_id
            for connection in definition.connections
            for attachment in connection.attachments
        ),
        *(association.association_id for association in definition.attachment_associations),
    }
    updated_associations = list(retained)
    claimed_ids: set[UUID] = set()
    for group in normalized:
        members = group.attachment_ids
        stable_key = frozenset(members)
        if group.association_id is not None and group.association_id not in (
            editable_ids | consumed_protected_ids
        ):
            raise ValueError("Association identity is stale or outside the selected hierarchies.")
        if group.association_id in protected_associations and not set(
            protected_associations[group.association_id].attachment_ids
        ).issubset(members):
            raise ValueError("An outside association identity must stay with all its members.")
        association_id = group.association_id or reusable_ids.get(stable_key)
        if association_id in claimed_ids:
            raise ValueError("An association identity may be used only once.")
        if association_id is None:
            association_id = id_factory()
            if association_id in used_ids:
                raise ValueError("Generated attachment-association identity is already in use.")
            used_ids.add(association_id)
        claimed_ids.add(association_id)
        updated_associations.append(
            AttachmentAssociationDefinition(association_id, members),
        )

    updated = replace(definition, attachment_associations=tuple(updated_associations))
    association_issues = tuple(
        issue
        for issue in validate_harness(updated)
        if issue.path.startswith("attachment_associations[")
    )
    if association_issues:
        raise ValueError(association_issues[0].message)
    persist_definition(harness_id, original, updated, gateway)
