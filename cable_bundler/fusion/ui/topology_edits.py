"""
Fusion palette edits that change harness topology.
"""

from __future__ import annotations

from uuid import UUID

from ...application import (
    HarnessEditGateway,
    add_cable_end_connection,
    disconnect_cable_end_main,
    disconnect_cable_end_shielding,
    move_pathway_gate,
    remove_cable_end_attachment,
    remove_end_control,
    remove_end_guide,
    remove_interface,
    remove_interface_contacts,
    remove_junction,
    remove_junction_relationship,
    remove_pathway,
    remove_pathway_gate,
    remove_standalone_end,
    update_junction_relationships,
)
from ...domain import JunctionPathwayRelationship, PathwayEndpoint
from .payloads import _read_payload_offset, _read_payload_uuid


def _apply_topology_edit(
    action: str,
    payload: dict[str, object],
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Apply one relationship, ordering, or deletion edit.
    """
    if action == "add_cable_end_connection":
        parent_attachment_id = (
            _read_payload_uuid(payload, "parentAttachmentId", "parent connection")
            if payload.get("parentAttachmentId") is not None
            else None
        )
        add_cable_end_connection(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            gateway,
            parent_attachment_id=parent_attachment_id,
        )
        return "Added cable-end connection."
    if action == "disconnect_cable_end_relationship":
        relationship = payload.get("relationship")
        if relationship not in {"main", "shielding"}:
            raise ValueError("Cable-end relationship kind is invalid.")
        arguments = (
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_payload_uuid(payload, "attachmentId", "connection node"),
            gateway,
        )
        if relationship == "main":
            disconnect_cable_end_main(*arguments)
        else:
            disconnect_cable_end_shielding(*arguments)
        return f"Disconnected cable-end {relationship} relationship."
    if action == "move_pathway_gate":
        move_pathway_gate(
            harness_id,
            _read_payload_uuid(payload, "pathwayId", "pathway"),
            _read_payload_uuid(payload, "controlId", "gate"),
            _read_payload_offset(payload),
            gateway,
        )
        return "Reordered pathway gate."
    if action == "remove_junction_relationship":
        endpoint = payload.get("endpoint")
        if endpoint not in {member.value for member in PathwayEndpoint}:
            raise ValueError("Junction relationship has an invalid endpoint.")
        remove_junction_relationship(
            harness_id,
            _read_payload_uuid(payload, "junctionId", "junction"),
            JunctionPathwayRelationship(
                _read_payload_uuid(payload, "pathwayId", "pathway"),
                PathwayEndpoint(endpoint),
            ),
            gateway,
        )
        return "Removed junction relationship."
    if action == "update_junction_relationships":
        raw_relationships = payload.get("pathwayRelationships")
        if not isinstance(raw_relationships, list):
            raise ValueError("Junction relationships must be a list.")
        relationships: list[JunctionPathwayRelationship] = []
        for index, raw_relationship in enumerate(raw_relationships):
            if not isinstance(raw_relationship, dict):
                raise ValueError(f"Junction relationship {index + 1} must be an object.")
            endpoint = raw_relationship.get("endpoint")
            if endpoint not in {member.value for member in PathwayEndpoint}:
                raise ValueError(f"Junction relationship {index + 1} has an invalid endpoint.")
            relationships.append(
                JunctionPathwayRelationship(
                    _read_payload_uuid(raw_relationship, "pathwayId", "pathway"),
                    PathwayEndpoint(endpoint),
                )
            )
        update_junction_relationships(
            harness_id,
            _read_payload_uuid(payload, "junctionId", "junction"),
            tuple(relationships),
            gateway,
        )
        return "Saved junction relationships."
    if action == "remove_pathway_gate":
        remove_pathway_gate(
            harness_id,
            _read_payload_uuid(payload, "pathwayId", "pathway"),
            _read_payload_uuid(payload, "controlId", "gate"),
            gateway,
        )
        return "Removed pathway gate."
    if action == "remove_end_guide":
        remove_end_guide(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_payload_uuid(payload, "memberId", "guide"),
            gateway,
        )
        return "Removed cable-end guide."
    if action == "remove_end_control":
        remove_end_control(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_payload_uuid(payload, "controlId", "control"),
            gateway,
        )
        return "Removed cable-end control."
    if action == "remove_pathway":
        remove_pathway(
            harness_id,
            _read_payload_uuid(payload, "pathwayId", "pathway"),
            gateway,
        )
        return "Deleted pathway branch."
    if action == "remove_junction":
        remove_junction(
            harness_id,
            _read_payload_uuid(payload, "junctionId", "junction"),
            gateway,
        )
        return "Deleted junction."
    if action == "remove_interface":
        remove_interface(
            harness_id,
            _read_payload_uuid(payload, "interfaceId", "Interface"),
            gateway,
        )
        return "Deleted Interface."
    if action == "remove_interface_contacts":
        raw_ids = payload.get("contactIds")
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError("Contact deletion requires selected contact IDs.")
        contact_ids = tuple(
            _read_payload_uuid({"contactId": item}, "contactId", "contact") for item in raw_ids
        )
        remove_interface_contacts(
            harness_id,
            _read_payload_uuid(payload, "interfaceId", "Interface"),
            contact_ids,
            gateway,
        )
        return "Deleted selected Interface contacts."
    if action == "remove_standalone_end":
        remove_standalone_end(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "standalone end"),
            gateway,
        )
        return "Deleted standalone end."
    if action == "remove_cable_end_attachment":
        remove_cable_end_attachment(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_payload_uuid(payload, "attachmentId", "connection node"),
            gateway,
        )
        return "Detached cable end."
    raise ValueError(f"Unsupported topology edit: {action}")
