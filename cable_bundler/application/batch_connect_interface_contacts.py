"""
Create terminal connections to Interface contacts on one grouped cable end.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from typing import Optional
from uuid import UUID, uuid4

from ..domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndTarget,
    CableVisualOverrides,
    HarnessDefinition,
    validate_harness,
)
from ..domain.connection_packing import required_parent_diameter
from .harness_edits.attachments import _replace_cable_end_attachment
from .harness_edits.support import persist_definition, read_definition
from .harness_edits.types import HarnessEditGateway


def batch_connect_interface_contacts(
    harness_id: UUID,
    interface_id: UUID,
    connection_id: UUID,
    contact_ids: tuple[UUID, ...],
    targets: tuple[CableEndTarget, ...],
    include_pins: bool,
    include_values: bool,
    diameter_mm: Optional[float],
    gateway: HarnessEditGateway,
    id_factory: Callable[[], UUID] = uuid4,
    *,
    parent_attachment_id: Optional[UUID] = None,
) -> int:
    """
    Add contact-backed nodes beneath a grouped end or profile node in one edit.

    Blank size uses loose packing inside the selected parent; an explicit size
    remains fixed and may enlarge the parent. No association group is created.
    """
    if not isinstance(include_pins, bool) or not isinstance(include_values, bool):
        raise ValueError("Auto Connect options must be checked or unchecked.")
    if diameter_mm is not None and (
        isinstance(diameter_mm, bool)
        or not isinstance(diameter_mm, (int, float))
        or not math.isfinite(diameter_mm)
        or diameter_mm <= 0
    ):
        raise ValueError("Connection diameter must be a finite positive value.")
    if not contact_ids or len(contact_ids) > 1024 or len(set(contact_ids)) != len(contact_ids):
        raise ValueError("Auto Connect requires distinct selected contacts.")
    if len(targets) != len(contact_ids) or any(
        not isinstance(target, CableEndTarget) for target in targets
    ):
        raise ValueError("Every selected contact needs one resolved target.")

    original, definition = read_definition(harness_id, gateway)
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    connection = next(
        (item for item in definition.connections if item.connection_id == connection_id), None
    )
    group = next(
        (item for item in definition.cable_groups if connection_id in item.connection_ids), None
    )
    if interface is None or connection is None or group is None:
        raise ValueError("Select an existing Interface and grouped cable end.")
    if parent_attachment_id is not None:
        parent = next(
            (item for item in connection.attachments if item.attachment_id == parent_attachment_id),
            None,
        )
        if parent is None or parent.target_kind is not AttachmentTargetKind.PROFILE:
            raise ValueError("Select a connected profile node on the grouped cable end.")
    contacts = {contact.contact_id: contact for contact in interface.contacts}
    if any(contact_id not in contacts for contact_id in contact_ids):
        raise ValueError("Selected contacts changed; reopen Auto Connect.")
    unavailable_tokens = (
        set(connection.member_tokens)
        | {item.entity_token for item in connection.attachments if item.has_target}
        | {
            item.shielding_target.entity_token
            for item in connection.attachments
            if item.shielding_target is not None
        }
    )
    if len({target.entity_token for target in targets}) != len(targets):
        raise ValueError("Selected contacts must have distinct geometry.")
    for contact_id, target in zip(contact_ids, targets):
        contact = contacts[contact_id]
        if target.target_kind is not contact.kind or target.entity_token != contact.entity_token:
            raise ValueError("A selected contact no longer matches its saved geometry.")
        if target.entity_token in unavailable_tokens:
            raise ValueError("A selected contact is already connected to this cable end.")

    used_ids = {
        definition.harness_id,
        *(item.connection_id for item in definition.connections),
        *(member_id for item in definition.connections for member_id in item.member_identities),
        *(item.attachment_id for item in definition.connections for item in item.attachments),
        *(item.control_id for item in definition.controls),
        *(item.pathway_id for item in definition.pathways),
        *(item.junction_id for item in definition.junctions),
        *(item.cable_group_id for item in definition.cable_groups),
        *(item.interface_id for item in definition.interfaces),
        *(item.contact_id for item in definition.interfaces for item in item.contacts),
        *(item.association_id for item in definition.attachment_associations),
    }
    new_ids = tuple(id_factory() for _ in contact_ids)
    if len(set(new_ids)) != len(new_ids) or any(item in used_ids for item in new_ids):
        raise ValueError("Generated connection identity is already in use.")
    additions = tuple(
        CableEndAttachment(
            target_kind=target.target_kind,
            entity_token=target.entity_token,
            inherited_name=target.inherited_name,
            name=contact.name if include_values else "",
            parameters=target.parameters,
            attachment_id=attachment_id,
            parent_attachment_id=parent_attachment_id,
            pin_number=contact.pin if include_pins and contact.pin else None,
            visual_overrides=CableVisualOverrides(diameter_mm=diameter_mm),
        )
        for contact_id, target, attachment_id in zip(contact_ids, targets, new_ids)
        for contact in (contacts[contact_id],)
    )
    updated_connection = replace(
        connection,
        attachment=connection.attachment or additions[0],
        additional_attachments=(
            (*connection.additional_attachments, *additions)
            if connection.attachment is not None
            else additions[1:]
        ),
    )

    def with_diameter(value_mm: float) -> HarnessDefinition:
        """
        Stage the same batch with one candidate parent diameter.
        """
        candidate_group = replace(group, diameter_mm=value_mm)
        return replace(
            definition,
            connections=tuple(
                updated_connection if item.connection_id == connection_id else item
                for item in definition.connections
            ),
            cable_groups=tuple(
                candidate_group if item.cable_group_id == group.cable_group_id else item
                for item in definition.cable_groups
            ),
        )

    current_parent_id = parent_attachment_id
    while True:
        children = updated_connection.attachment_children(current_parent_id)
        fixed = tuple(
            item.visual_overrides.diameter_mm
            for item in children
            if item.visual_overrides.diameter_mm is not None
        )
        automatic_seed = min(fixed) if fixed else 0.0
        required = required_parent_diameter(
            tuple(item.visual_overrides.diameter_mm or automatic_seed for item in children)
        )
        if current_parent_id is None:
            group = replace(group, diameter_mm=max(group.diameter_mm, required))
            break
        parent = next(
            item
            for item in updated_connection.attachments
            if item.attachment_id == current_parent_id
        )
        actual = with_diameter(group.diameter_mm).cable_end_attachment_diameter(
            group, connection_id, current_parent_id
        )
        if required > actual:
            updated_parent = replace(
                parent,
                visual_overrides=replace(parent.visual_overrides, diameter_mm=required),
            )
            updated_connection = _replace_cable_end_attachment(
                updated_connection, current_parent_id, updated_parent
            )
        current_parent_id = parent.parent_attachment_id

    def diameter_issue(value_mm: float) -> Optional[str]:
        """
        Report the first diameter budget failure at one proposed size.
        """
        return next(
            (
                issue.message
                for issue in validate_harness(with_diameter(value_mm))
                if issue.code == "connection_diameter_budget_exceeded"
            ),
            None,
        )

    lower = group.diameter_mm
    budget_issue = diameter_issue(lower)
    if budget_issue is not None:
        upper = lower
        for _ in range(32):
            upper *= 2
            if not math.isfinite(upper):
                raise ValueError(budget_issue)
            if diameter_issue(upper) is None:
                for _ in range(32):
                    middle = (lower + upper) / 2
                    if diameter_issue(middle) is None:
                        upper = middle
                    else:
                        lower = middle
                break
            lower = upper
        else:
            raise ValueError(budget_issue)
        if diameter_issue(upper) is not None:
            raise ValueError(budget_issue)
        group = replace(group, diameter_mm=upper)
    updated = with_diameter(group.diameter_mm)
    persist_definition(harness_id, original, updated, gateway)
    return len(additions)
