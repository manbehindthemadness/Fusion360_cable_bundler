"""
Transactional batch connection of saved contacts to grouped cable ends.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application.batch_connect_interface_contacts import (
    batch_connect_and_associate_interface_contacts,
    batch_connect_interface_contacts,
)
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndTarget,
    CableVisualOverrides,
    HarnessDefinition,
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    loads,
)
from tests.test_edit_harness import _recording_gateway


def _contact_harness(valid_harness: HarnessDefinition) -> HarnessDefinition:
    """
    Supply two saved contact targets to an otherwise valid grouped cable.
    """
    interface = InterfaceDefinition(
        UUID(int=800),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (
            InterfaceContact(
                UUID(int=801), AttachmentTargetKind.SKETCH_POINT, "contact-a", "VCC", "A1"
            ),
            InterfaceContact(
                UUID(int=802), AttachmentTargetKind.SKETCH_POINT, "contact-b", "GND", "A2"
            ),
        ),
    )
    return replace(valid_harness, interfaces=(interface,))


def _targets() -> tuple[CableEndTarget, ...]:
    """
    Return resolved Fusion target descriptions in contact order.
    """
    return (
        CableEndTarget(AttachmentTargetKind.SKETCH_POINT, "contact-a", "Pad A"),
        CableEndTarget(AttachmentTargetKind.SKETCH_POINT, "contact-b", "Pad B"),
    )


def test_dual_batch_associates_only_unique_matching_nonblank_pins(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep two batches and their pin associations atomic while skipping ambiguity.
    """
    definition = _contact_harness(valid_harness)
    first = replace(
        definition.interfaces[0],
        contacts=(
            *definition.interfaces[0].contacts,
            InterfaceContact(
                UUID(int=803), AttachmentTargetKind.SKETCH_POINT, "contact-c", "", "A2"
            ),
            InterfaceContact(UUID(int=804), AttachmentTargetKind.SKETCH_POINT, "contact-d", "", ""),
        ),
    )
    second = InterfaceDefinition(
        UUID(int=810),
        "Target",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body-2"),),
        (
            InterfaceContact(
                UUID(int=811), AttachmentTargetKind.SKETCH_POINT, "target-a", "", "A1"
            ),
            InterfaceContact(
                UUID(int=812), AttachmentTargetKind.SKETCH_POINT, "target-b", "", "A2"
            ),
            InterfaceContact(UUID(int=813), AttachmentTargetKind.SKETCH_POINT, "target-c", "", ""),
        ),
    )
    definition = replace(definition, interfaces=(first, second))
    gateway = _recording_gateway(definition)
    ids = iter(UUID(int=value) for value in range(901, 920))
    counts = batch_connect_and_associate_interface_contacts(
        definition.harness_id,
        first.interface_id,
        definition.connections[0].connection_id,
        tuple(item.contact_id for item in first.contacts),
        (
            *_targets(),
            CableEndTarget(AttachmentTargetKind.SKETCH_POINT, "contact-c", "Pad C"),
            CableEndTarget(AttachmentTargetKind.SKETCH_POINT, "contact-d", "Pad D"),
        ),
        False,
        False,
        None,
        second.interface_id,
        definition.connections[1].connection_id,
        tuple(item.contact_id for item in second.contacts),
        tuple(
            CableEndTarget(AttachmentTargetKind.SKETCH_POINT, item.entity_token, "Target")
            for item in second.contacts
        ),
        False,
        False,
        None,
        gateway,
        id_factory=ids.__next__,
    )
    stored = loads(gateway.serialized_definition)
    assert counts == (4, 3, 1)
    assert len(stored.attachment_associations) == 1
    association = stored.attachment_associations[0]
    assert association.attachment_ids == (
        stored.connections[0].attachments[0].attachment_id,
        stored.connections[1].attachments[0].attachment_id,
    )
    assert all(
        item.pin_number is None
        for connection in stored.connections
        for item in connection.attachments
    )


def test_dual_batch_does_not_save_first_half_when_second_is_invalid(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Leave the original definition untouched when the target batch fails.
    """
    definition = _contact_harness(valid_harness)
    second = replace(
        definition.interfaces[0],
        interface_id=UUID(int=810),
        contacts=(
            InterfaceContact(
                UUID(int=811), AttachmentTargetKind.SKETCH_POINT, "target-a", "", "A1"
            ),
        ),
    )
    definition = replace(definition, interfaces=(*definition.interfaces, second))
    gateway = _recording_gateway(definition)
    original = gateway.serialized_definition
    with pytest.raises(ValueError, match="matches its saved geometry"):
        batch_connect_and_associate_interface_contacts(
            definition.harness_id,
            definition.interfaces[0].interface_id,
            definition.connections[0].connection_id,
            (UUID(int=801),),
            _targets()[:1],
            True,
            True,
            None,
            second.interface_id,
            definition.connections[1].connection_id,
            (UUID(int=811),),
            _targets()[:1],
            True,
            True,
            None,
            gateway,
        )
    assert gateway.serialized_definition == original


def test_batch_connects_contacts_without_creating_association_groups(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve contact order, copied fields, and equal automatic branch sizing.
    """
    definition = _contact_harness(valid_harness)
    gateway = _recording_gateway(definition)
    count = batch_connect_interface_contacts(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        definition.connections[0].connection_id,
        (UUID(int=801), UUID(int=802)),
        _targets(),
        True,
        True,
        None,
        gateway,
        id_factory=iter((UUID(int=901), UUID(int=902))).__next__,
    )
    stored = loads(gateway.serialized_definition)
    attachments = stored.connections[0].attachments
    assert count == 2
    assert tuple(item.attachment_id for item in attachments) == (UUID(int=901), UUID(int=902))
    assert tuple(item.name for item in attachments) == ("VCC", "GND")
    assert tuple(item.pin_number for item in attachments) == ("A1", "A2")
    assert tuple(item.entity_token for item in attachments) == ("contact-a", "contact-b")
    assert all(item.visual_overrides.diameter_mm is None for item in attachments)
    assert stored.cable_groups[0].diameter_mm == 1.2
    assert stored.attachment_associations == ()


def test_explicit_size_enlarges_group_and_unchecked_fields_remain_empty(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep the requested diameter for each branch and grow its parent once.
    """
    definition = _contact_harness(valid_harness)
    gateway = _recording_gateway(definition)
    batch_connect_interface_contacts(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        definition.connections[0].connection_id,
        (UUID(int=801), UUID(int=802)),
        _targets(),
        False,
        False,
        0.8,
        gateway,
        id_factory=iter((UUID(int=901), UUID(int=902))).__next__,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].diameter_mm == 1.6
    assert tuple(
        item.visual_overrides.diameter_mm for item in stored.connections[0].attachments
    ) == (0.8, 0.8)
    assert all(
        not item.name and item.pin_number is None for item in stored.connections[0].attachments
    )


@pytest.mark.parametrize(
    ("diameter_mm", "expected_parent_mm"),
    ((0.4, 1.2), (1.6, 1.6)),
)
def test_single_contact_honors_explicit_size_and_only_grows_parent_when_needed(
    valid_harness: HarnessDefinition,
    diameter_mm: float,
    expected_parent_mm: float,
) -> None:
    """
    Honor an explicit singleton branch without shrinking the cable group.
    """
    definition = _contact_harness(valid_harness)
    gateway = _recording_gateway(definition)
    batch_connect_interface_contacts(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        definition.connections[0].connection_id,
        (UUID(int=801),),
        _targets()[:1],
        True,
        True,
        diameter_mm,
        gateway,
        id_factory=lambda: UUID(int=901),
    )
    stored = loads(gateway.serialized_definition)
    assert stored.cable_groups[0].diameter_mm == expected_parent_mm
    assert (
        stored.cable_end_attachment_diameter(
            stored.cable_groups[0], stored.connections[0].connection_id, UUID(int=901)
        )
        == diameter_mm
    )


def test_batch_grows_parent_for_fixed_children_of_an_existing_root(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve an existing subtree's fixed branch budget after root division.
    """
    definition = _contact_harness(valid_harness)
    root_id = UUID(int=910)
    existing = replace(
        definition.connections[0],
        attachment=CableEndAttachment(
            AttachmentTargetKind.PROFILE,
            "existing-profile",
            "Connector",
            attachment_id=root_id,
        ),
        additional_attachments=(
            CableEndAttachment(
                AttachmentTargetKind.SKETCH_POINT,
                "existing-a",
                "Pin A",
                attachment_id=UUID(int=911),
                parent_attachment_id=root_id,
                visual_overrides=CableVisualOverrides(diameter_mm=0.6),
            ),
            CableEndAttachment(
                AttachmentTargetKind.SKETCH_POINT,
                "existing-b",
                "Pin B",
                attachment_id=UUID(int=912),
                parent_attachment_id=root_id,
                visual_overrides=CableVisualOverrides(diameter_mm=0.6),
            ),
        ),
    )
    definition = replace(definition, connections=(existing, definition.connections[1]))
    gateway = _recording_gateway(definition)
    batch_connect_interface_contacts(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        existing.connection_id,
        (UUID(int=801), UUID(int=802)),
        _targets(),
        True,
        True,
        None,
        gateway,
        id_factory=iter((UUID(int=901), UUID(int=902))).__next__,
    )
    stored = loads(gateway.serialized_definition)
    assert 1.2 < stored.cable_groups[0].diameter_mm < 3.6
    assert (
        stored.cable_end_attachment_pack(
            stored.cable_groups[0], stored.connections[0].connection_id, root_id
        )
        is not None
    )
    assert len(stored.connections[0].attachments) == 5


def test_batch_can_create_children_under_a_connected_profile_node(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Use the selected profile node as the connection parent, without an association group.
    """
    definition = _contact_harness(valid_harness)
    parent_id = UUID(int=910)
    parent = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "connector-profile",
        "Connector",
        attachment_id=parent_id,
    )
    connection = replace(definition.connections[0], attachment=parent)
    definition = replace(definition, connections=(connection, definition.connections[1]))
    gateway = _recording_gateway(definition)
    batch_connect_interface_contacts(
        definition.harness_id,
        definition.interfaces[0].interface_id,
        connection.connection_id,
        (UUID(int=801), UUID(int=802)),
        _targets(),
        True,
        True,
        0.8,
        gateway,
        id_factory=iter((UUID(int=901), UUID(int=902))).__next__,
        parent_attachment_id=parent_id,
    )
    stored = loads(gateway.serialized_definition)
    children = stored.connections[0].attachment_children(parent_id)
    assert tuple(item.attachment_id for item in children) == (UUID(int=901), UUID(int=902))
    assert stored.connections[0].attachment.attachment_id == parent_id
    assert stored.cable_groups[0].diameter_mm == 1.6
    assert stored.attachment_associations == ()


def test_batch_rejects_non_grouped_end_and_duplicate_target_atomically(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reject stale or repeated selections without saving a partial batch.
    """
    definition = _contact_harness(valid_harness)
    gateway = _recording_gateway(replace(definition, cable_groups=()))
    with pytest.raises(ValueError, match="grouped cable end"):
        batch_connect_interface_contacts(
            definition.harness_id,
            definition.interfaces[0].interface_id,
            definition.connections[0].connection_id,
            (UUID(int=801),),
            _targets()[:1],
            True,
            True,
            None,
            gateway,
        )
    assert loads(gateway.serialized_definition).connections[0].attachments == ()

    gateway = _recording_gateway(definition)
    with pytest.raises(ValueError, match="distinct selected contacts"):
        batch_connect_interface_contacts(
            definition.harness_id,
            definition.interfaces[0].interface_id,
            definition.connections[0].connection_id,
            (UUID(int=801), UUID(int=801)),
            _targets(),
            True,
            True,
            None,
            gateway,
        )
    assert loads(gateway.serialized_definition).connections[0].attachments == ()
