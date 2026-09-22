"""
Tests for external cable-end connection editing.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from cable_bundler.application import (
    add_cable_end_connection,
    add_connection_refine,
    attach_cable_end,
    remove_cable_end_attachment,
    rename_cable_end_attachment,
    set_cable_end_attachment_properties,
)
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    HarnessDefinition,
    RefineGeometry,
    loads,
)
from tests.test_edit_harness import _recording_gateway


def test_attaches_renames_and_removes_external_cable_end_target(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist attachment lifecycle independently of assignment and target geometry.
    """
    connection_id = valid_harness.connections[0].connection_id
    first_attachment_id = UUID(int=701)
    second_attachment_id = UUID(int=702)
    attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "joint-origin-token",
        "J1 Pin 1",
    )
    gateway = _recording_gateway(valid_harness)

    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        id_factory=lambda: first_attachment_id,
    )
    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        id_factory=lambda: second_attachment_id,
    )
    stored = loads(gateway.serialized_definition)
    assert tuple(item.attachment_id for item in stored.connections[0].attachments) == (
        first_attachment_id,
        second_attachment_id,
    )

    with pytest.raises(ValueError, match="attachment is invalid"):
        attach_cable_end(
            valid_harness.harness_id,
            connection_id,
            second_attachment_id,
            CableEndAttachment(None),
            gateway,
        )

    rename_cable_end_attachment(
        valid_harness.harness_id,
        connection_id,
        second_attachment_id,
        " Bulkhead socket ",
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[1].name == "Bulkhead socket"

    set_cable_end_attachment_properties(
        valid_harness.harness_id,
        connection_id,
        second_attachment_id,
        (("connector", "J1"),),
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[1].metadata == (("connector", "J1"),)

    attach_cable_end(
        valid_harness.harness_id,
        connection_id,
        second_attachment_id,
        attachment,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[1] == replace(
        attachment,
        attachment_id=second_attachment_id,
        name="Bulkhead socket",
        metadata=(("connector", "J1"),),
    )
    assert stored.cable_groups == valid_harness.cable_groups

    remove_cable_end_attachment(
        valid_harness.harness_id,
        connection_id,
        first_attachment_id,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachment == stored.connections[0].attachments[0]
    remaining_attachment = stored.connections[0].attachment
    assert remaining_attachment is not None
    assert remaining_attachment.attachment_id == second_attachment_id
    assert stored.cable_groups == valid_harness.cable_groups


def test_adds_and_prunes_connection_owned_refine(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist a refine on one connected node and remove it with its owning node.
    """
    connection = valid_harness.connections[0]
    attachment_id = UUID(int=703)
    refine_id = UUID(int=704)
    attachment = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "joint-origin-token",
        "J1 Pin 1",
    )
    geometry = RefineGeometry(
        origin_mm=(1.0, 2.0, 3.0),
        u_direction=(1.0, 0.0, 0.0),
        v_direction=(0.0, 1.0, 0.0),
        display_radius_mm=2.0,
    )
    gateway = _recording_gateway(valid_harness)
    add_cable_end_connection(
        valid_harness.harness_id,
        connection.connection_id,
        gateway,
        id_factory=lambda: attachment_id,
    )
    attach_cable_end(
        valid_harness.harness_id,
        connection.connection_id,
        attachment_id,
        attachment,
        gateway,
    )

    add_connection_refine(
        valid_harness.harness_id,
        connection.connection_id,
        attachment_id,
        0,
        geometry,
        gateway,
        id_factory=lambda: refine_id,
    )

    stored = loads(gateway.serialized_definition)
    refined_attachment = stored.connections[0].attachments[0]
    assert refined_attachment.ordered_control_ids == (refine_id,)
    saved_control = next(item for item in stored.controls if item.control_id == refine_id)
    assert saved_control.refine_geometry == geometry

    remove_cable_end_attachment(
        valid_harness.harness_id,
        connection.connection_id,
        attachment_id,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert all(item.control_id != refine_id for item in stored.controls)
