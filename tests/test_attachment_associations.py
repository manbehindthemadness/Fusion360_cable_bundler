"""
Test persistent terminal attachment associations and their edit boundaries.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application import (
    AttachmentAssociationAnchor,
    AttachmentAssociationGroup,
    attachment_association_candidates,
    save_attachment_associations,
)
from cable_bundler.application.harness_edits.support import prune_attachment_associations
from cable_bundler.domain import (
    AttachmentAssociationDefinition,
    AttachmentTargetKind,
    CableEndAttachment,
    HarnessDefinition,
    loads,
)
from tests.harness_edit_support import recording_gateway as _recording_gateway


def test_attachment_associations_grow_to_odd_sized_groups_with_stable_identity(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep one association identity as three and then five attachment nodes are grouped.
    """
    left_ids = tuple(UUID(int=710 + index) for index in range(3))
    right_ids = tuple(UUID(int=720 + index) for index in range(2))
    association_id = UUID(int=730)
    left_connection, right_connection = valid_harness.connections
    definition = replace(
        valid_harness,
        connections=(
            replace(
                left_connection,
                attachment=CableEndAttachment(None, attachment_id=left_ids[0]),
                additional_attachments=tuple(
                    CableEndAttachment(None, attachment_id=item) for item in left_ids[1:]
                ),
            ),
            replace(
                right_connection,
                attachment=CableEndAttachment(None, attachment_id=right_ids[0]),
                additional_attachments=(CableEndAttachment(None, attachment_id=right_ids[1]),),
            ),
        ),
    )
    gateway = _recording_gateway(definition)
    left_anchor = AttachmentAssociationAnchor(connection_id=left_connection.connection_id)
    right_anchor = AttachmentAssociationAnchor(connection_id=right_connection.connection_id)
    three_members = (left_ids[0], right_ids[0], left_ids[1])

    save_attachment_associations(
        definition.harness_id,
        left_anchor,
        right_anchor,
        (AttachmentAssociationGroup(three_members),),
        gateway,
        id_factory=lambda: association_id,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.attachment_associations[0].attachment_ids == three_members
    assert stored.attachment_associations[0].association_id == association_id

    five_members = (*three_members, right_ids[1], left_ids[2])
    save_attachment_associations(
        definition.harness_id,
        left_anchor,
        right_anchor,
        (AttachmentAssociationGroup(five_members, association_id),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.attachment_associations[0].attachment_ids == five_members
    assert stored.attachment_associations[0].association_id == association_id
    surviving = prune_attachment_associations(
        stored.attachment_associations, set(five_members[:-1])
    )
    assert surviving[0].attachment_ids == five_members[:-1]
    assert surviving[0].association_id == association_id
    assert prune_attachment_associations(stored.attachment_associations, {five_members[0]}) == ()

    with pytest.raises(ValueError, match="only one association"):
        save_attachment_associations(
            definition.harness_id,
            left_anchor,
            right_anchor,
            (
                AttachmentAssociationGroup(three_members, association_id),
                AttachmentAssociationGroup((left_ids[1], right_ids[1])),
            ),
            gateway,
        )
    assert loads(gateway.serialized_definition) == stored


def test_attachment_associations_merge_complete_outside_groups(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Merge only explicitly imported outside groups and preserve their hidden members.
    """
    left_ids = tuple(UUID(int=810 + index) for index in range(3))
    right_ids = tuple(UUID(int=820 + index) for index in range(3))
    center_id, left_id, right_id = (UUID(int=830 + index) for index in range(3))
    left_connection, right_connection = valid_harness.connections
    definition = replace(
        valid_harness,
        connections=(
            replace(
                left_connection,
                attachment=CableEndAttachment(None, attachment_id=left_ids[0]),
                additional_attachments=tuple(
                    CableEndAttachment(None, attachment_id=item) for item in left_ids[1:]
                ),
            ),
            replace(
                right_connection,
                attachment=CableEndAttachment(None, attachment_id=right_ids[0]),
                additional_attachments=tuple(
                    CableEndAttachment(None, attachment_id=item) for item in right_ids[1:]
                ),
            ),
        ),
        attachment_associations=(
            AttachmentAssociationDefinition(center_id, (left_ids[1], right_ids[1])),
            AttachmentAssociationDefinition(left_id, (left_ids[0], left_ids[2])),
            AttachmentAssociationDefinition(right_id, (right_ids[0], right_ids[2])),
        ),
    )
    gateway = _recording_gateway(definition)
    left_anchor = AttachmentAssociationAnchor(
        connection_id=left_connection.connection_id,
        candidate_attachment_ids=left_ids[:2],
    )
    right_anchor = AttachmentAssociationAnchor(
        connection_id=right_connection.connection_id,
        candidate_attachment_ids=right_ids[:2],
    )
    first_members = (left_ids[1], right_ids[1], left_ids[0], left_ids[2])

    save_attachment_associations(
        definition.harness_id,
        left_anchor,
        right_anchor,
        (AttachmentAssociationGroup(first_members, center_id),),
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert {item.association_id for item in stored.attachment_associations} == {
        center_id,
        right_id,
    }
    assert (
        next(
            item for item in stored.attachment_associations if item.association_id == center_id
        ).attachment_ids
        == first_members
    )

    all_members = (*first_members, right_ids[0], right_ids[2])
    save_attachment_associations(
        definition.harness_id,
        left_anchor,
        right_anchor,
        (AttachmentAssociationGroup(all_members, center_id),),
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.attachment_associations == (
        AttachmentAssociationDefinition(center_id, all_members),
    )

    with pytest.raises(ValueError, match="cannot be split"):
        save_attachment_associations(
            definition.harness_id,
            left_anchor,
            right_anchor,
            (AttachmentAssociationGroup(all_members[:-1], center_id),),
            gateway,
        )
    assert loads(gateway.serialized_definition) == stored


def test_attachment_associations_split_attachment_from_other_group_ends(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Resolve an attachment's owner selection to the other cable-group ends.
    """
    owner, other = valid_harness.connections
    group = valid_harness.cable_groups[0]
    parent_id, first_id, second_id, other_id, association_id = (
        UUID(int=940 + index) for index in range(5)
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(
                owner,
                attachment=CableEndAttachment(
                    AttachmentTargetKind.PROFILE,
                    "split-profile",
                    "Split profile",
                    attachment_id=parent_id,
                ),
                additional_attachments=(
                    CableEndAttachment(
                        None, attachment_id=first_id, parent_attachment_id=parent_id
                    ),
                    CableEndAttachment(
                        None, attachment_id=second_id, parent_attachment_id=parent_id
                    ),
                ),
            ),
            replace(other, attachment=CableEndAttachment(None, attachment_id=other_id)),
        ),
    )
    left_anchor = AttachmentAssociationAnchor(
        connection_id=owner.connection_id, attachment_id=parent_id
    )
    right_anchor = AttachmentAssociationAnchor(
        connection_id=owner.connection_id,
        node_kind="cableGroupRemainder",
        node_id=group.cable_group_id,
        candidate_attachment_ids=(other_id,),
    )
    assert attachment_association_candidates(definition, left_anchor) == (first_id, second_id)
    assert attachment_association_candidates(definition, right_anchor) == (other_id,)

    gateway = _recording_gateway(definition)
    save_attachment_associations(
        definition.harness_id,
        left_anchor,
        right_anchor,
        (AttachmentAssociationGroup((first_id, other_id)),),
        gateway,
        id_factory=lambda: association_id,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.attachment_associations == (
        AttachmentAssociationDefinition(association_id, (first_id, other_id)),
    )

    invalid_anchor = replace(right_anchor, candidate_attachment_ids=(first_id,))
    with pytest.raises(ValueError, match="do not belong"):
        attachment_association_candidates(definition, invalid_anchor)
    incomplete_anchor = replace(right_anchor, candidate_attachment_ids=())
    with pytest.raises(ValueError, match="changed since selection"):
        attachment_association_candidates(definition, incomplete_anchor)
