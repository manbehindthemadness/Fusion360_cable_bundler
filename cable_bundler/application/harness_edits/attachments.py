"""
Transactional edits for external cable-end connection nodes and their properties.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from typing import Optional
from uuid import UUID, uuid4

from ...domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndTarget,
    CableVisualOverrides,
    Connection,
    Metadata,
)
from .support import persist_definition, prune_attachment_associations, read_definition
from .types import HarnessEditGateway


# noinspection DuplicatedCode
def attach_cable_end(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    attachment: CableEndAttachment,
    gateway: HarnessEditGateway,
) -> None:
    """
    Attach or reconnect one existing cable end to an external Fusion target.
    """
    if not isinstance(attachment, CableEndAttachment) or not attachment.has_target:
        raise ValueError("Cable-end attachment is invalid.")
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected cable end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end has a missing connection.")
    existing = _cable_end_attachment(connection, attachment_id)
    if attachment.entity_token in connection.member_tokens:
        raise ValueError("A cable end cannot attach to its own guide geometry.")
    if any(
        item.attachment_id != attachment_id
        and item.has_target
        and item.entity_token == attachment.entity_token
        for item in connection.attachments
    ) or any(
        item.shielding_target is not None
        and item.shielding_target.entity_token == attachment.entity_token
        for item in connection.attachments
    ):
        raise ValueError("Each cable-end connection requires a unique target.")
    completed_attachment = replace(
        attachment,
        attachment_id=attachment_id,
        parent_attachment_id=existing.parent_attachment_id,
        name=attachment.name or existing.name,
        metadata=existing.metadata,
        ordered_control_ids=existing.ordered_control_ids,
        visual_overrides=existing.visual_overrides,
        shielding_target=existing.shielding_target,
    )
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, completed_attachment
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def attach_cable_end_shielding(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    target: CableEndTarget,
    gateway: HarnessEditGateway,
) -> None:
    """
    Attach a non-geometric shielding relationship to one shielded leaf connection.
    """
    if not isinstance(target, CableEndTarget):
        raise ValueError("Cable-end shielding target is invalid.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    if connection.attachment_children(attachment_id):
        raise ValueError("Shielding can connect only from a final connection node.")
    group = next(
        (item for item in definition.cable_groups if connection_id in item.connection_ids),
        None,
    )
    if group is None:
        raise ValueError("Shielding connections require an assigned cable group.")
    materials = definition.cable_end_attachment_materials(group, connection_id, attachment_id)
    if not materials.shielding.strip():
        raise ValueError("This final connection does not specify shielding.")
    if target.entity_token in connection.member_tokens:
        raise ValueError("A shielding relationship cannot target its own guide geometry.")
    occupied_tokens = {
        token
        for item in connection.attachments
        for token in (
            item.entity_token if item.has_target else "",
            (
                item.shielding_target.entity_token
                if item.shielding_target is not None and item.attachment_id != attachment_id
                else ""
            ),
        )
        if token
    }
    if target.entity_token in occupied_tokens:
        raise ValueError("Each cable-end relationship requires a unique target.")
    updated_attachment = replace(attachment, shielding_target=target)
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, updated_attachment
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def disconnect_cable_end_main(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one node's geometric target and its target-dependent refine controls.

    Parent profiles remain connected until their child connection relationships are
    removed, preserving the explicit connection-chain invariant.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    if not attachment.has_target:
        raise ValueError("Selected connection does not have a main relationship.")
    if connection.attachment_children(attachment_id):
        raise ValueError("Disconnect child connection nodes before their parent profile.")
    removed_control_ids = frozenset(attachment.ordered_control_ids)
    disconnected = replace(
        attachment,
        target_kind=None,
        entity_token="",
        inherited_name="",
        parameters=(),
        ordered_control_ids=(),
    )
    updated_connection = _replace_cable_end_attachment(connection, attachment_id, disconnected)
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if control.control_id not in removed_control_ids
        ),
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def disconnect_cable_end_shielding(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Remove one node's non-geometric shielding target relationship.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    if attachment.shielding_target is None:
        raise ValueError("Selected connection does not have a shielding relationship.")
    updated_connection = _replace_cable_end_attachment(
        connection,
        attachment_id,
        replace(attachment, shielding_target=None),
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


# noinspection DuplicatedCode
def add_cable_end_connection(
    harness_id: UUID,
    connection_id: UUID,
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
    *,
    parent_attachment_id: Optional[UUID] = None,
) -> CableEndAttachment:
    """
    Persist an unattached root or child connection node for one cable end.
    """
    original, definition = read_definition(harness_id, gateway)
    if all(end.connection_id != connection_id for end in definition.standalone_ends):
        raise ValueError("Selected cable end does not exist in this harness.")
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end has a missing connection.")
    if parent_attachment_id is not None:
        parent = _cable_end_attachment(connection, parent_attachment_id)
        if parent.target_kind is not AttachmentTargetKind.PROFILE:
            raise ValueError("Child connections require a sketch-profile parent.")
    attachment_id = id_factory()
    existing_ids = {
        definition.harness_id,
        *(item.connection_id for item in definition.connections),
        *(item.control_id for item in definition.controls),
        *(item.pathway_id for item in definition.pathways),
        *(item.junction_id for item in definition.junctions),
        *(item.cable_group_id for item in definition.cable_groups),
        *(association.association_id for association in definition.attachment_associations),
        *(
            item.attachment_id
            for cable_end in definition.connections
            for item in cable_end.attachments
        ),
    }
    if attachment_id in existing_ids:
        raise ValueError("Generated cable-end connection identity is already in use.")
    attachment = CableEndAttachment(
        None,
        attachment_id=attachment_id,
        parent_attachment_id=parent_attachment_id,
    )
    if connection.attachment is None:
        updated_connection = replace(connection, attachment=attachment)
    else:
        updated_connection = replace(
            connection,
            additional_attachments=(*connection.additional_attachments, attachment),
        )
    group = next(
        (item for item in definition.cable_groups if connection_id in item.connection_ids),
        None,
    )
    if group is not None:
        _validate_connection_diameter_budget(group.diameter_mm, updated_connection)
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)
    return attachment


def rename_cable_end_attachment(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    name: str,
    gateway: HarnessEditGateway,
) -> None:
    """
    Set or clear the display-name override for one cable-end attachment.
    """
    if not isinstance(name, str):
        raise ValueError("Connection name must be text.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, replace(attachment, name=name.strip())
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def set_cable_end_attachment_properties(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    metadata: Metadata,
    gateway: HarnessEditGateway,
    *,
    diameter_mm: Optional[float] = None,
    conductor_diameter_mm: Optional[float] = None,
    insulation_material: Optional[str] = None,
    conductor_material: Optional[str] = None,
    shielding: Optional[str] = None,
    dielectric_material: Optional[str] = None,
    manufacturer: Optional[str] = None,
    part_number: Optional[str] = None,
) -> None:
    """
    Replace metadata and optional construction overrides owned by one branch.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    branch_overrides = attachment.visual_overrides
    group_diameter_mm: Optional[float] = None
    if diameter_mm is not None:
        if conductor_diameter_mm is not None and (
            isinstance(conductor_diameter_mm, bool)
            or not isinstance(conductor_diameter_mm, (int, float))
            or not math.isfinite(conductor_diameter_mm)
            or conductor_diameter_mm <= 0
            or conductor_diameter_mm > diameter_mm
        ):
            raise ValueError(
                "Conductor diameter must be positive and no larger than the connection diameter."
            )
        siblings = connection.attachment_children(attachment.parent_attachment_id)
        if len(siblings) <= 1:
            raise ValueError("A single connection inherits its parent properties.")
        group = next(
            (item for item in definition.cable_groups if connection_id in item.connection_ids),
            None,
        )
        if group is None:
            raise ValueError("Connection properties require an assigned cable group.")
        group_diameter_mm = group.diameter_mm
        branch_overrides = replace(
            branch_overrides,
            diameter_mm=diameter_mm,
            conductor_diameter_mm=conductor_diameter_mm,
            insulation_material=insulation_material,
            conductor_material=conductor_material,
            shielding=shielding,
            dielectric_material=dielectric_material,
            manufacturer=manufacturer,
            part_number=part_number,
        )
    updated_connection = _replace_cable_end_attachment(
        connection,
        attachment_id,
        replace(attachment, metadata=metadata, visual_overrides=branch_overrides),
    )
    if group_diameter_mm is not None:
        _validate_connection_diameter_budget(group_diameter_mm, updated_connection)
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def set_cable_end_attachment_shielding(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    shielding: Optional[str],
    dielectric_material: Optional[str],
    metadata: Metadata,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace connector metadata and its shielding construction overrides atomically.

    A null value resumes inheritance. An explicit empty string interrupts inherited
    shielding for the selected node and all descendants that continue to inherit.
    """
    if shielding is not None and not isinstance(shielding, str):
        raise ValueError("Connection shielding override must be text or null.")
    if dielectric_material is not None and not isinstance(dielectric_material, str):
        raise ValueError("Connection dielectric-material override must be text or null.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    normalized = None if shielding is None else shielding.strip()
    normalized_dielectric = None if dielectric_material is None else dielectric_material.strip()
    updated_attachment = replace(
        attachment,
        metadata=metadata,
        visual_overrides=replace(
            attachment.visual_overrides,
            shielding=normalized,
            dielectric_material=normalized_dielectric,
        ),
    )
    updated_connection = _replace_cable_end_attachment(
        connection, attachment_id, updated_attachment
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def set_cable_end_attachment_visual_overrides(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    overrides: CableVisualOverrides,
    gateway: HarnessEditGateway,
) -> None:
    """
    Replace eligible visual overrides for one cable-end connection node.
    """
    if not isinstance(overrides, CableVisualOverrides):
        raise ValueError("Connection material overrides are invalid.")
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    attachment = _cable_end_attachment(connection, attachment_id)
    if len(connection.attachment_children(attachment.parent_attachment_id)) > 1:
        visual_overrides = replace(
            attachment.visual_overrides,
            main_color=overrides.main_color,
            appearance=overrides.appearance,
            stripes=overrides.stripes,
            pullback=overrides.pullback,
            weld=overrides.weld,
        )
    else:
        visual_overrides = replace(
            attachment.visual_overrides,
            pullback=overrides.pullback,
            weld=overrides.weld,
        )
    updated_connection = _replace_cable_end_attachment(
        connection,
        attachment_id,
        replace(attachment, visual_overrides=visual_overrides),
    )
    updated = replace(
        definition,
        connections=tuple(
            updated_connection if item.connection_id == connection_id else item
            for item in definition.connections
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def _validate_connection_diameter_budget(
    parent_diameter_mm: float,
    connection: Connection,
) -> None:
    """
    Reject any sibling branch group whose diameters exceed its immediate parent.
    """

    def validate_children(parent_attachment_id: Optional[UUID], diameter_mm: float) -> None:
        children = connection.attachment_children(parent_attachment_id)
        if not children:
            return
        inherited_diameter_mm = diameter_mm / len(children)
        child_diameters = (
            (diameter_mm,)
            if len(children) == 1
            else tuple(
                inherited_diameter_mm
                if child.visual_overrides.diameter_mm is None
                else child.visual_overrides.diameter_mm
                for child in children
            )
        )
        if len(children) > 1 and sum(child_diameters) > diameter_mm + 1e-9:
            raise ValueError(
                "Connection diameters cannot collectively exceed the parent cable diameter."
            )
        for child, child_diameter_mm in zip(children, child_diameters):
            validate_children(child.attachment_id, child_diameter_mm)

    validate_children(None, parent_diameter_mm)


def remove_cable_end_attachment(
    harness_id: UUID,
    connection_id: UUID,
    attachment_id: UUID,
    gateway: HarnessEditGateway,
) -> None:
    """
    Detach one cable end without deleting its referenced Fusion target.
    """
    original, definition = read_definition(harness_id, gateway)
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id),
        None,
    )
    if connection is None:
        raise ValueError("Selected cable end does not exist.")
    _cable_end_attachment(connection, attachment_id)
    removed_attachment_ids = {attachment_id}
    while True:
        descendants = {
            attachment.attachment_id
            for attachment in connection.attachments
            if attachment.parent_attachment_id in removed_attachment_ids
        }
        expanded = removed_attachment_ids | descendants
        if expanded == removed_attachment_ids:
            break
        removed_attachment_ids = expanded
    removed_attachments = tuple(
        attachment
        for attachment in connection.attachments
        if attachment.attachment_id in removed_attachment_ids
    )
    remaining = tuple(
        attachment
        for attachment in connection.attachments
        if attachment.attachment_id not in removed_attachment_ids
    )
    remaining = tuple(
        replace(
            attachment,
            visual_overrides=CableVisualOverrides(
                shielding=attachment.visual_overrides.shielding,
                dielectric_material=attachment.visual_overrides.dielectric_material,
                pullback=attachment.visual_overrides.pullback,
                weld=attachment.visual_overrides.weld,
            ),
        )
        if sum(
            candidate.parent_attachment_id == attachment.parent_attachment_id
            for candidate in remaining
        )
        == 1
        else attachment
        for attachment in remaining
    )
    updated_connection = replace(
        connection,
        attachment=remaining[0] if remaining else None,
        additional_attachments=remaining[1:],
    )
    group = next(
        (item for item in definition.cable_groups if connection_id in item.connection_ids),
        None,
    )
    if group is not None:
        _validate_connection_diameter_budget(group.diameter_mm, updated_connection)
    updated_connections = tuple(
        updated_connection if item.connection_id == connection_id else item
        for item in definition.connections
    )
    updated = replace(
        definition,
        controls=tuple(
            control
            for control in definition.controls
            if all(
                control.control_id not in attachment.ordered_control_ids
                for attachment in removed_attachments
            )
        ),
        connections=updated_connections,
        attachment_associations=prune_attachment_associations(
            definition.attachment_associations,
            {
                attachment.attachment_id
                for connection_item in updated_connections
                for attachment in connection_item.attachments
            },
        ),
    )
    persist_definition(harness_id, original, updated, gateway)


def _cable_end_attachment(
    connection: Connection,
    attachment_id: UUID,
) -> CableEndAttachment:
    """
    Resolve one external connection node by its stable identity.
    """
    attachment = next(
        (item for item in connection.attachments if item.attachment_id == attachment_id),
        None,
    )
    if attachment is None:
        raise ValueError("Selected cable-end connection does not exist.")
    return attachment


def _replace_cable_end_attachment(
    connection: Connection,
    attachment_id: UUID,
    replacement: CableEndAttachment,
) -> Connection:
    """
    Replace one external connection node without changing collection order.
    """
    attachments = tuple(
        replacement if item.attachment_id == attachment_id else item
        for item in connection.attachments
    )
    return replace(
        connection,
        attachment=attachments[0],
        additional_attachments=attachments[1:],
    )
