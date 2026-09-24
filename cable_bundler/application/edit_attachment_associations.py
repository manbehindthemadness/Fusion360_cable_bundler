"""Persist explicit groups between terminal cable-end attachment nodes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Optional
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
class AttachmentAssociationAnchor:
    """
    Identify a cable-end root or one attachment subtree in the diagram.
    """

    connection_id: UUID
    attachment_id: Optional[UUID] = None


def attachment_association_candidates(
    definition: HarnessDefinition,
    anchor: AttachmentAssociationAnchor,
) -> tuple[UUID, ...]:
    """
    Return terminal attachment IDs beneath one selected cable-end node.
    """
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
            (item for item in connection.attachments if item.attachment_id == anchor.attachment_id),
            None,
        )
        if selected is None:
            raise ValueError("Selected attachment node no longer exists.")
        roots = (selected,)
    leaves: list[UUID] = []
    pending = list(roots)
    while pending:
        current = pending.pop()
        children = connection.attachment_children(current.attachment_id)
        if children:
            pending.extend(reversed(children))
        else:
            leaves.append(current.attachment_id)
    return tuple(leaves)


def save_attachment_associations(
    harness_id: UUID,
    left_anchor: AttachmentAssociationAnchor,
    right_anchor: AttachmentAssociationAnchor,
    pairs: tuple[AttachmentAssociationPair, ...],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
) -> None:
    """
    Replace editable cross-panel pairs while preserving associations outside them.

    Existing groups with one member outside the selected candidate sets, or two
    members on the same side, remain untouched and cannot be reassigned here.
    """
    if left_anchor == right_anchor:
        raise ValueError("Association nodes must be different.")
    original, definition = read_definition(harness_id, gateway)
    left_ids = set(attachment_association_candidates(definition, left_anchor))
    right_ids = set(attachment_association_candidates(definition, right_anchor))
    if left_ids.intersection(right_ids):
        raise ValueError("The selected nodes have overlapping terminal connections.")
    pair_members: list[UUID] = []
    for pair in pairs:
        if pair.left_attachment_id not in left_ids:
            raise ValueError("An association contains a node outside the selected left hierarchy.")
        if pair.right_attachment_id not in right_ids:
            raise ValueError("An association contains a node outside the selected right hierarchy.")
        pair_members.extend((pair.left_attachment_id, pair.right_attachment_id))
    if len(pair_members) != len(set(pair_members)):
        raise ValueError("An attachment node may appear in only one association.")

    retained: list[AttachmentAssociationDefinition] = []
    reusable_ids: dict[frozenset[UUID], UUID] = {}
    for association in definition.attachment_associations:
        members = set(association.attachment_ids)
        left_member = members.intersection(left_ids)
        right_member = members.intersection(right_ids)
        editable = len(members) == 2 and len(left_member) == 1 and len(right_member) == 1
        if editable:
            reusable_ids[frozenset(members)] = association.association_id
        else:
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
    for pair in pairs:
        members = (pair.left_attachment_id, pair.right_attachment_id)
        stable_key = frozenset(members)
        association_id = reusable_ids.get(stable_key)
        if association_id is None:
            association_id = id_factory()
            if association_id in used_ids:
                raise ValueError("Generated attachment-association identity is already in use.")
            used_ids.add(association_id)
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
