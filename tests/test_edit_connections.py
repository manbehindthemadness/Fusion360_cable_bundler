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
    attach_cable_end_shielding,
    disconnect_cable_end_main,
    disconnect_cable_end_shielding,
    remove_cable_end_attachment,
    rename_cable_end_attachment,
    set_cable_end_attachment_properties,
    set_cable_end_attachment_shielding,
    set_cable_end_attachment_visual_overrides,
    set_cable_group_properties,
)
from cable_bundler.domain import (
    AttachmentTargetKind,
    CableColor,
    CableEndAttachment,
    CableEndTarget,
    CableVisualOverrides,
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
        diameter_mm=0.6,
        insulation_material="ETFE",
        conductor_material="Aluminum",
        shielding="Braided copper",
        manufacturer="Branch maker",
        part_number="BR-01",
    )
    stored = loads(gateway.serialized_definition)
    saved_attachment = stored.connections[0].attachments[1]
    assert saved_attachment.metadata == (("connector", "J1"),)
    assert saved_attachment.visual_overrides.diameter_mm == 0.6
    assert saved_attachment.visual_overrides.insulation_material == "ETFE"
    assert saved_attachment.visual_overrides.conductor_material == "Aluminum"
    assert saved_attachment.visual_overrides.shielding == "Braided copper"
    assert saved_attachment.visual_overrides.manufacturer == "Branch maker"
    assert saved_attachment.visual_overrides.part_number == "BR-01"

    group = valid_harness.cable_groups[0]
    with pytest.raises(ValueError, match="collectively exceed"):
        set_cable_group_properties(
            valid_harness.harness_id,
            group.cable_group_id,
            1.0,
            None,
            None,
            None,
            None,
            None,
            (),
            gateway,
        )

    with pytest.raises(ValueError, match="collectively exceed"):
        set_cable_end_attachment_properties(
            valid_harness.harness_id,
            connection_id,
            first_attachment_id,
            (),
            gateway,
            diameter_mm=1.0,
        )

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
        visual_overrides=saved_attachment.visual_overrides,
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


def test_attaches_shielding_data_only_to_a_shielded_leaf(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist a secondary target without replacing the leaf's main geometry target.
    """
    connection = valid_harness.connections[0]
    leaf = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "main-profile",
        "Main socket",
        attachment_id=UUID(int=721),
    )
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, shielding="Foil"),
        connections=(replace(connection, attachment=leaf), *valid_harness.connections[1:]),
    )
    gateway = _recording_gateway(definition)
    target = CableEndTarget(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "shield-stud",
        "Shield stud",
    )

    attach_cable_end_shielding(
        definition.harness_id,
        connection.connection_id,
        leaf.attachment_id,
        target,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    saved = stored.connections[0].attachment
    assert saved is not None
    assert saved.entity_token == "main-profile"
    assert saved.shielding_target == target


def test_rejects_shielding_relationship_on_a_non_leaf_connection(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep shielding relationships at the final nodes of explicit connection chains.
    """
    connection = valid_harness.connections[0]
    parent = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "parent-profile",
        "Parent",
        attachment_id=UUID(int=731),
    )
    child = CableEndAttachment(
        None,
        attachment_id=UUID(int=732),
        parent_attachment_id=parent.attachment_id,
    )
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, shielding="Braid"),
        connections=(
            replace(connection, attachment=parent, additional_attachments=(child,)),
            *valid_harness.connections[1:],
        ),
    )
    gateway = _recording_gateway(definition)
    target = CableEndTarget(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "shield-stud",
        "Shield stud",
    )

    with pytest.raises(ValueError, match="final connection"):
        attach_cable_end_shielding(
            definition.harness_id,
            connection.connection_id,
            parent.attachment_id,
            target,
            gateway,
        )


def test_disconnects_main_and_shielding_relationships_independently(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Preserve the connection node and unrelated relationship when either target is removed.
    """
    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "main-target",
        "Main target",
        name="Connector",
        metadata=(("location", "J1"),),
        attachment_id=UUID(int=741),
        shielding_target=CableEndTarget(
            AttachmentTargetKind.CONSTRUCTION_POINT,
            "shield-target",
            "Shield target",
        ),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=attachment),
            *valid_harness.connections[1:],
        ),
    )
    gateway = _recording_gateway(definition)
    refine_id = UUID(int=742)
    add_connection_refine(
        definition.harness_id,
        connection.connection_id,
        attachment.attachment_id,
        0,
        RefineGeometry(
            origin_mm=(1.0, 2.0, 3.0),
            u_direction=(1.0, 0.0, 0.0),
            v_direction=(0.0, 1.0, 0.0),
            display_radius_mm=2.0,
        ),
        gateway,
        id_factory=lambda: refine_id,
    )

    disconnect_cable_end_main(
        definition.harness_id,
        connection.connection_id,
        attachment.attachment_id,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    disconnected = stored.connections[0].attachment
    assert disconnected is not None
    assert not disconnected.has_target
    assert disconnected.name == "Connector"
    assert disconnected.metadata == (("location", "J1"),)
    assert disconnected.shielding_target == attachment.shielding_target
    assert disconnected.ordered_control_ids == ()
    assert all(control.control_id != refine_id for control in stored.controls)

    disconnect_cable_end_shielding(
        definition.harness_id,
        connection.connection_id,
        attachment.attachment_id,
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    disconnected = stored.connections[0].attachment
    assert disconnected is not None
    assert disconnected.shielding_target is None


def test_rejects_main_disconnect_while_connection_children_depend_on_profile(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Retain a parent profile until its child connection nodes are removed.
    """
    connection = valid_harness.connections[0]
    parent = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "parent-profile",
        "Parent profile",
        attachment_id=UUID(int=751),
    )
    child = CableEndAttachment(
        None,
        attachment_id=UUID(int=752),
        parent_attachment_id=parent.attachment_id,
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=parent, additional_attachments=(child,)),
            *valid_harness.connections[1:],
        ),
    )
    gateway = _recording_gateway(definition)

    with pytest.raises(ValueError, match="Disconnect child connection nodes"):
        disconnect_cable_end_main(
            definition.harness_id,
            connection.connection_id,
            parent.attachment_id,
            gateway,
        )


def test_adds_and_removes_cascading_connection_descendants(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist the selected parent and delete its complete descendant subtree.
    """
    connection_id = valid_harness.connections[0].connection_id
    root_id = UUID(int=711)
    child_id = UUID(int=712)
    grandchild_id = UUID(int=713)
    gateway = _recording_gateway(valid_harness)
    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        id_factory=lambda: root_id,
    )
    attach_cable_end(
        valid_harness.harness_id,
        connection_id,
        root_id,
        CableEndAttachment(AttachmentTargetKind.PROFILE, "root-profile", "Root profile"),
        gateway,
    )
    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        parent_attachment_id=root_id,
        id_factory=lambda: child_id,
    )
    attach_cable_end(
        valid_harness.harness_id,
        connection_id,
        child_id,
        CableEndAttachment(AttachmentTargetKind.PROFILE, "child-profile", "Child profile"),
        gateway,
    )
    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        parent_attachment_id=child_id,
        id_factory=lambda: grandchild_id,
    )

    stored = loads(gateway.serialized_definition)
    assert tuple(
        (item.attachment_id, item.parent_attachment_id)
        for item in stored.connections[0].attachments
    ) == ((root_id, None), (child_id, root_id), (grandchild_id, child_id))

    remove_cable_end_attachment(
        valid_harness.harness_id,
        connection_id,
        child_id,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert tuple(item.attachment_id for item in stored.connections[0].attachments) == (root_id,)


def test_replaces_a_saved_external_target(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Replace target data after the Fusion-facing caller establishes it is disconnected.
    """
    connection_id = valid_harness.connections[0].connection_id
    attachment_id = UUID(int=703)
    gateway = _recording_gateway(valid_harness)
    add_cable_end_connection(
        valid_harness.harness_id,
        connection_id,
        gateway,
        id_factory=lambda: attachment_id,
    )
    original = CableEndAttachment(
        AttachmentTargetKind.JOINT_ORIGIN,
        "missing-joint-token",
        "Missing joint",
    )
    replacement = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "replacement-point-token",
        "Replacement point",
    )
    attach_cable_end(
        valid_harness.harness_id,
        connection_id,
        attachment_id,
        original,
        gateway,
    )

    attach_cable_end(
        valid_harness.harness_id,
        connection_id,
        attachment_id,
        replacement,
        gateway,
    )

    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[0] == replace(
        replacement,
        attachment_id=attachment_id,
    )


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


def test_connection_visual_overrides_require_multiple_nodes_and_clear_when_collapsed(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist branch visuals only while a cable end has subdivided connection geometry.
    """
    connection_id = valid_harness.connections[0].connection_id
    first_id = UUID(int=711)
    second_id = UUID(int=712)
    overrides = CableVisualOverrides(main_color=CableColor("Red", 255, 0, 0), stripes=())
    gateway = _recording_gateway(valid_harness)
    add_cable_end_connection(
        valid_harness.harness_id, connection_id, gateway, id_factory=lambda: first_id
    )
    with pytest.raises(ValueError, match="single connection inherits"):
        set_cable_end_attachment_visual_overrides(
            valid_harness.harness_id, connection_id, first_id, overrides, gateway
        )
    add_cable_end_connection(
        valid_harness.harness_id, connection_id, gateway, id_factory=lambda: second_id
    )
    set_cable_end_attachment_properties(
        valid_harness.harness_id,
        connection_id,
        first_id,
        (),
        gateway,
        diameter_mm=0.6,
        insulation_material="ETFE",
        conductor_material="Aluminum",
        shielding="Braided copper",
        manufacturer="Branch maker",
        part_number="BR-01",
    )

    set_cable_end_attachment_visual_overrides(
        valid_harness.harness_id, connection_id, first_id, overrides, gateway
    )
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[0].visual_overrides == replace(
        overrides,
        diameter_mm=0.6,
        insulation_material="ETFE",
        conductor_material="Aluminum",
        shielding="Braided copper",
        manufacturer="Branch maker",
        part_number="BR-01",
    )

    remove_cable_end_attachment(valid_harness.harness_id, connection_id, second_id, gateway)
    stored = loads(gateway.serialized_definition)
    assert stored.connections[0].attachments[0].visual_overrides == CableVisualOverrides(
        shielding="Braided copper"
    )


def test_sets_and_clears_connector_shielding_inheritance(
    valid_harness: HarnessDefinition,
) -> None:
    """
    Persist both explicit empty interruptions and null inheritance markers.
    """
    connection_id = valid_harness.connections[0].connection_id
    attachment_id = UUID(int=721)
    gateway = _recording_gateway(valid_harness)
    add_cable_end_connection(
        valid_harness.harness_id, connection_id, gateway, id_factory=lambda: attachment_id
    )

    set_cable_end_attachment_shielding(
        valid_harness.harness_id,
        connection_id,
        attachment_id,
        "  ",
        (("connector", "J1"),),
        gateway,
    )
    stored = loads(gateway.serialized_definition)
    saved_attachment = stored.connections[0].attachment
    assert saved_attachment is not None
    assert saved_attachment.visual_overrides.shielding == ""
    assert saved_attachment.metadata == (("connector", "J1"),)

    set_cable_end_attachment_shielding(
        valid_harness.harness_id, connection_id, attachment_id, None, (), gateway
    )
    stored = loads(gateway.serialized_definition)
    saved_attachment = stored.connections[0].attachment
    assert saved_attachment is not None
    assert saved_attachment.visual_overrides.shielding is None
