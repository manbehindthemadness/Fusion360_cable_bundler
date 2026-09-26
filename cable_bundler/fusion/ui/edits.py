"""
Fusion UI services for edits.
"""

from __future__ import annotations

from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import (
    AttachmentAssociationAnchor,
    AttachmentAssociationGroup,
    AttachmentAssociationPair,
    CableEditorPairing,
    CableEditorRename,
    HarnessEditGateway,
    add_cable_end_connection,
    auto_pin_interface_contacts,
    disconnect_cable_end_main,
    disconnect_cable_end_shielding,
    move_pathway_gate,
    name_interface_contacts,
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
    rename_cable_end_attachment,
    rename_cable_group,
    rename_harness,
    rename_interface,
    rename_junction,
    rename_pathway,
    rename_standalone_end,
    save_attachment_associations,
    save_cable_editor,
    set_cable_end_attachment_properties,
    set_cable_end_attachment_shielding,
    set_cable_end_attachment_visual_overrides,
    set_cable_end_properties,
    set_cable_group_material_overrides,
    set_cable_group_properties,
    set_harness_material_defaults,
    set_harness_properties,
    set_interface_contact_details,
    set_junction_properties,
    set_pathway_end_properties,
    set_pathway_properties,
    switch_standalone_end,
    update_junction_relationships,
)
from ...application.harness_edits import set_interpolation
from ...domain import AutoTransitionPreset, JunctionPathwayRelationship, PathwayEndpoint
from ...domain.codec import parse_interpolation
from ..interface_contact_geo_import import import_interface_contact_geometry_names
from ..interface_contact_naming import import_interface_contact_names
from .payloads import (
    _read_harness_properties,
    _read_material_overrides,
    _read_material_settings,
    _read_metadata,
    _read_palette_payload,
    _read_payload_offset,
    _read_payload_uuid,
    _read_visual_overrides,
)
from .support import _create_harness_gateway

_TOPOLOGY_ACTIONS = frozenset(
    (
        "add_cable_end_connection",
        "disconnect_cable_end_relationship",
        "move_pathway_gate",
        "remove_junction_relationship",
        "update_junction_relationships",
        "remove_pathway_gate",
        "remove_end_guide",
        "remove_end_control",
        "remove_pathway",
        "remove_junction",
        "remove_interface",
        "remove_interface_contacts",
        "remove_standalone_end",
        "remove_cable_end_attachment",
    )
)


def _apply_palette_edit(
    application: adsk.core.Application,
    action: str,
    serialized_data: str,
) -> str:
    """
    Apply one ordered palette edit and return its success notice.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    if action == "set_interface_contact_name":
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        contact_id = _read_payload_uuid(payload, "contactId", "contact")
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Contact name must be text.")
        name_interface_contacts(
            harness_id, interface_id, {contact_id: name}, _create_harness_gateway(application)
        )
        return "Interface contact name updated."
    if action == "set_interface_contact_details":
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        contact_id = _read_payload_uuid(payload, "contactId", "contact")
        value = payload.get("value")
        pin = payload.get("pin")
        if not isinstance(value, str) or not isinstance(pin, str):
            raise ValueError("Contact value and pin must be text.")
        set_interface_contact_details(
            harness_id, interface_id, contact_id, value, pin, _create_harness_gateway(application)
        )
        return "Interface contact updated."
    if action == "auto_pin_interface_contacts":
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        raw_ids = payload.get("contactIds")
        if (
            not isinstance(raw_ids, list)
            or not raw_ids
            or any(not isinstance(item, str) for item in raw_ids)
        ):
            raise ValueError("Auto Pin requires contact identities.")
        contact_ids = tuple(UUID(item) for item in raw_ids)
        auto_pin_interface_contacts(
            harness_id,
            interface_id,
            contact_ids,
            payload.get("start"),
            payload.get("overwrite"),
            _create_harness_gateway(application),
        )
        return "Interface contacts pinned."
    if action in ("pos_import_interface_contacts", "load_brd_interface_contacts"):
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        source = "live" if action == "pos_import_interface_contacts" else "file"
        return import_interface_contact_names(application, harness_id, interface_id, source)
    if action == "geo_import_interface_contacts":
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        raw_ids = payload.get("contactIds")
        if not isinstance(raw_ids, list) or any(not isinstance(item, str) for item in raw_ids):
            raise ValueError("Geo Import contact IDs must be a list of identities.")
        contact_ids = tuple(UUID(item) for item in raw_ids)
        return import_interface_contact_geometry_names(
            application, harness_id, interface_id, contact_ids
        )
    gateway = _create_harness_gateway(application)
    if action in _TOPOLOGY_ACTIONS:
        return _apply_topology_edit(action, payload, harness_id, gateway)
    if action == "save_cable_editor":
        return _apply_route_editor_edit(payload, harness_id, gateway)
    if action == "save_attachment_associations":
        return _apply_attachment_association_edit(payload, harness_id, gateway)
    return _apply_property_edit(action, payload, harness_id, gateway)


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


def _apply_route_editor_edit(
    payload: dict[str, object],
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Parse and persist one complete Route Editor transaction.
    """
    left_boundary = payload.get("leftBoundary")
    right_boundary = payload.get("rightBoundary")
    raw_pairings = payload.get("pairings")
    raw_detached = payload.get("detachedConnectionIds")
    raw_renames = payload.get("renames")
    raw_deleted = payload.get("deletedConnectionIds")
    if not isinstance(left_boundary, dict) or not isinstance(right_boundary, dict):
        raise ValueError("Route Editor boundaries must be objects.")
    if (
        not isinstance(raw_pairings, list)
        or not isinstance(raw_detached, list)
        or not isinstance(raw_renames, list)
        or not isinstance(raw_deleted, list)
    ):
        raise ValueError("Route Editor changes must be lists.")
    left_endpoint = left_boundary.get("endpoint")
    right_endpoint = right_boundary.get("endpoint")
    if left_endpoint not in {member.value for member in PathwayEndpoint}:
        raise ValueError("Route Editor left boundary has an invalid endpoint.")
    if right_endpoint not in {member.value for member in PathwayEndpoint}:
        raise ValueError("Route Editor right boundary has an invalid endpoint.")
    pairings: list[CableEditorPairing] = []
    for index, raw_pairing in enumerate(raw_pairings):
        if not isinstance(raw_pairing, dict):
            raise ValueError(f"Route Editor pairing {index + 1} must be an object.")
        pairings.append(
            CableEditorPairing(
                _read_payload_uuid(raw_pairing, "leftConnectionId", "left cable end"),
                _read_payload_uuid(raw_pairing, "rightConnectionId", "right cable end"),
            )
        )
    renames: list[CableEditorRename] = []
    for index, raw_rename in enumerate(raw_renames):
        if not isinstance(raw_rename, dict) or not isinstance(raw_rename.get("name"), str):
            raise ValueError(f"Route Editor rename {index + 1} must contain a text name.")
        renames.append(
            CableEditorRename(
                _read_payload_uuid(raw_rename, "connectionId", "renamed cable end"),
                raw_rename["name"],
            )
        )
    save_cable_editor(
        harness_id,
        _read_payload_uuid(left_boundary, "pathwayId", "left pathway"),
        PathwayEndpoint(left_endpoint),
        _read_payload_uuid(right_boundary, "pathwayId", "right pathway"),
        PathwayEndpoint(right_endpoint),
        tuple(pairings),
        tuple(
            _read_payload_uuid(
                {"connectionId": connection_id}, "connectionId", "detached cable end"
            )
            for connection_id in raw_detached
        ),
        tuple(renames),
        tuple(
            _read_payload_uuid({"connectionId": connection_id}, "connectionId", "deleted cable end")
            for connection_id in raw_deleted
        ),
        gateway,
    )
    return "Saved Route Editor changes."


def _apply_attachment_association_edit(
    payload: dict[str, object],
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Parse and persist selected attachment association groups.
    """
    left_anchor = payload.get("leftAnchor")
    right_anchor = payload.get("rightAnchor")
    raw_groups = payload.get("associations")
    if not isinstance(left_anchor, dict) or not isinstance(right_anchor, dict):
        raise ValueError("Association anchors must be objects.")
    if not isinstance(raw_groups, list):
        raise ValueError("Associations must be a list.")

    def parse_anchor(value: dict[str, object]) -> AttachmentAssociationAnchor:
        """
        Parse a cable-end, attachment, route, or cable-group remainder identity.
        """
        node_kind = value.get("nodeKind", "connection")
        if node_kind in ("pathway", "junction"):
            raw_candidates = value.get("candidateAttachmentIds")
            if not isinstance(raw_candidates, list) or any(
                not isinstance(candidate, str) for candidate in raw_candidates
            ):
                raise ValueError("Route association candidates must be a list of identities.")
            return AttachmentAssociationAnchor(
                node_kind=str(node_kind),
                node_id=_read_payload_uuid(value, "nodeId", "route node"),
                candidate_attachment_ids=tuple(
                    _read_payload_uuid(
                        {"attachmentId": candidate}, "attachmentId", "route candidate"
                    )
                    for candidate in raw_candidates
                ),
            )
        if node_kind == "cableGroupRemainder":
            raw_candidates = value.get("candidateAttachmentIds")
            if not isinstance(raw_candidates, list) or any(
                not isinstance(candidate, str) for candidate in raw_candidates
            ):
                raise ValueError("Cable-group association candidates must be a list of identities.")
            return AttachmentAssociationAnchor(
                connection_id=_read_payload_uuid(value, "connectionId", "excluded cable end"),
                node_kind=node_kind,
                node_id=_read_payload_uuid(value, "nodeId", "cable group"),
                candidate_attachment_ids=tuple(
                    _read_payload_uuid(
                        {"attachmentId": candidate}, "attachmentId", "cable-group candidate"
                    )
                    for candidate in raw_candidates
                ),
            )
        if node_kind != "connection":
            raise ValueError("Unsupported association node kind.")
        attachment_id = (
            _read_payload_uuid(value, "attachmentId", "attachment node")
            if value.get("attachmentId") is not None
            else None
        )
        return AttachmentAssociationAnchor(
            _read_payload_uuid(value, "connectionId", "cable end"),
            attachment_id,
        )

    groups: list[AttachmentAssociationGroup | AttachmentAssociationPair] = []
    for index, raw_group in enumerate(raw_groups):
        if not isinstance(raw_group, dict):
            raise ValueError(f"Association {index + 1} must be an object.")
        raw_members = raw_group.get("attachmentIds")
        if raw_members is None:
            groups.append(
                AttachmentAssociationPair(
                    _read_payload_uuid(raw_group, "leftAttachmentId", "left connection node"),
                    _read_payload_uuid(raw_group, "rightAttachmentId", "right connection node"),
                )
            )
            continue
        if not isinstance(raw_members, list) or any(
            not isinstance(member, str) for member in raw_members
        ):
            raise ValueError(f"Association {index + 1} needs a list of attachment identities.")
        association_id = (
            _read_payload_uuid(raw_group, "associationId", "association")
            if raw_group.get("associationId") is not None
            else None
        )
        groups.append(
            AttachmentAssociationGroup(
                tuple(
                    _read_payload_uuid({"attachmentId": member}, "attachmentId", "connection node")
                    for member in raw_members
                ),
                association_id,
            )
        )
    save_attachment_associations(
        harness_id,
        parse_anchor(left_anchor),
        parse_anchor(right_anchor),
        tuple(groups),
        gateway,
    )
    return "Saved connection associations."


def _apply_property_edit(
    action: str,
    payload: dict[str, object],
    harness_id: UUID,
    gateway: HarnessEditGateway,
) -> str:
    """
    Apply one naming, interpolation, material, or metadata edit.
    """
    if action == "rename_standalone_end":
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Standalone end rename request requires a text name.")
        rename_standalone_end(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "standalone end"),
            name,
            gateway,
        )
        return "Saved end name."
    if action == "rename_cable_end_attachment":
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Connection rename request requires a text name.")
        rename_cable_end_attachment(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_payload_uuid(payload, "attachmentId", "connection node"),
            name,
            gateway,
        )
        return "Saved connection name."
    if action == "rename_cable_group":
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Cable-group rename request requires a text name.")
        rename_cable_group(
            harness_id,
            _read_payload_uuid(payload, "cableGroupId", "cable group"),
            name,
            gateway,
        )
        return "Saved cable-group name."
    if action == "switch_standalone_end":
        switch_standalone_end(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "standalone end"),
            gateway,
        )
        return "Switched standalone end."
    if action == "set_interpolation":
        target = payload.get("target")
        if target not in ("gate", "end", "defaults"):
            raise ValueError("Unsupported interpolation target.")
        use_defaults = payload.get("useDefaults", False)
        if not isinstance(use_defaults, bool):
            raise ValueError("Use defaults must be a boolean.")
        apply_existing = payload.get("applyExisting", False)
        if not isinstance(apply_existing, bool):
            raise ValueError("Apply to existing sections must be a boolean.")
        raw_minimum_clearance = payload.get("minimumClearanceMm")
        if raw_minimum_clearance is not None and (
            isinstance(raw_minimum_clearance, bool)
            or not isinstance(raw_minimum_clearance, (int, float))
        ):
            raise ValueError("Minimum member gap must be a number in millimeters.")
        raw_auto_transition_preset = payload.get("autoTransitionPreset")
        if raw_auto_transition_preset is not None and not isinstance(
            raw_auto_transition_preset, str
        ):
            raise ValueError("Auto transition preset must be text.")
        try:
            auto_transition_preset = (
                AutoTransitionPreset(raw_auto_transition_preset)
                if raw_auto_transition_preset is not None
                else None
            )
        except ValueError as error:
            raise ValueError("Auto transition preset is not supported.") from error
        settings = parse_interpolation(payload.get("settings"), "settings")
        set_interpolation(
            harness_id,
            target,
            settings,
            gateway,
            apply_existing=apply_existing,
            use_defaults=use_defaults,
            member_id=(
                _read_payload_uuid(payload, "memberId", "end member") if target == "end" else None
            ),
            target_id=(
                None if target == "defaults" else _read_payload_uuid(payload, "targetId", "section")
            ),
            end_defaults=(
                parse_interpolation(payload.get("endDefaults"), "endDefaults")
                if target == "defaults"
                else None
            ),
            minimum_clearance_mm=(
                float(raw_minimum_clearance)
                if target == "defaults" and raw_minimum_clearance is not None
                else None
            ),
            auto_transition_preset=(auto_transition_preset if target == "defaults" else None),
        )
        return "Saved interpolation options."
    if action == "set_cable_group_properties":
        diameter = payload.get("diameterMm")
        if isinstance(diameter, bool) or not isinstance(diameter, (int, float)):
            raise ValueError("Cable-group diameter must be a number in millimeters.")
        conductor_diameter = payload.get("conductorDiameterMm")
        if conductor_diameter is not None and (
            isinstance(conductor_diameter, bool) or not isinstance(conductor_diameter, (int, float))
        ):
            raise ValueError("Conductor diameter must be a number in millimeters or null for Auto.")
        property_materials = _read_material_overrides(
            {
                "insulationMaterial": payload.get("insulationMaterial"),
                "conductorMaterial": payload.get("conductorMaterial"),
                "shielding": payload.get("shielding"),
                "dielectricMaterial": payload.get("dielectricMaterial"),
                "manufacturer": payload.get("manufacturer"),
                "partNumber": payload.get("partNumber"),
            }
        )
        set_cable_group_properties(
            harness_id,
            _read_payload_uuid(payload, "cableGroupId", "cable group"),
            diameter,
            property_materials.insulation_material,
            property_materials.conductor_material,
            property_materials.shielding,
            property_materials.dielectric_material,
            property_materials.manufacturer,
            property_materials.part_number,
            _read_metadata(payload.get("metadataOverrides", []), "Cable metadata overrides"),
            gateway,
            conductor_diameter_mm=conductor_diameter,
        )
        return "Saved connected-cable properties."
    if action == "set_harness_material_defaults":
        set_harness_material_defaults(
            harness_id,
            _read_material_settings(payload.get("materials")),
            gateway,
        )
        return "Saved harness cable-material defaults."
    if action == "set_harness_properties":
        (
            insulation_material,
            conductor_material,
            shielding,
            dielectric_material,
            manufacturer,
            part_number,
            metadata,
        ) = _read_harness_properties(payload)
        set_harness_properties(
            harness_id,
            insulation_material,
            conductor_material,
            shielding,
            dielectric_material,
            manufacturer,
            part_number,
            metadata,
            gateway,
        )
        return "Saved harness properties."
    if action == "set_cable_group_material_overrides":
        set_cable_group_material_overrides(
            harness_id,
            _read_payload_uuid(payload, "cableGroupId", "cable group"),
            _read_material_overrides(payload.get("overrides")),
            gateway,
        )
        return "Saved connected-cable material overrides."
    if action == "set_pathway_properties":
        set_pathway_properties(
            harness_id,
            _read_payload_uuid(payload, "pathwayId", "pathway"),
            _read_metadata(payload.get("metadata", []), "Pathway metadata"),
            gateway,
        )
        return "Saved pathway properties."
    if action == "set_pathway_end_properties":
        endpoint = payload.get("endpoint")
        if endpoint not in {member.value for member in PathwayEndpoint}:
            raise ValueError("Pathway end has an invalid endpoint.")
        set_pathway_end_properties(
            harness_id,
            _read_payload_uuid(payload, "pathwayId", "pathway"),
            PathwayEndpoint(endpoint),
            _read_metadata(payload.get("metadata", []), "Pathway-end metadata"),
            gateway,
        )
        return "Saved pathway-end properties."
    if action == "set_junction_properties":
        set_junction_properties(
            harness_id,
            _read_payload_uuid(payload, "junctionId", "junction"),
            _read_metadata(payload.get("metadata", []), "Junction metadata"),
            gateway,
        )
        return "Saved junction properties."
    if action == "set_cable_end_properties":
        set_cable_end_properties(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable end"),
            _read_metadata(payload.get("metadata", []), "Cable-end metadata"),
            gateway,
        )
        return "Saved cable-end properties."
    if action == "set_cable_end_attachment_properties":
        has_construction_properties = "diameterMm" in payload
        property_overrides = (
            _read_visual_overrides(
                {
                    "diameterMm": payload.get("diameterMm"),
                    "conductorDiameterMm": payload.get("conductorDiameterMm"),
                    "insulationMaterial": payload.get("insulationMaterial"),
                    "conductorMaterial": payload.get("conductorMaterial"),
                    "shielding": payload.get("shielding"),
                    "dielectricMaterial": payload.get("dielectricMaterial"),
                    "manufacturer": payload.get("manufacturer"),
                    "partNumber": payload.get("partNumber"),
                }
            )
            if has_construction_properties
            else None
        )
        if property_overrides is not None and property_overrides.diameter_mm is None:
            raise ValueError("Connection diameter must be a number in millimeters.")
        connection_id = _read_payload_uuid(payload, "connectionId", "cable-end connection")
        attachment_id = _read_payload_uuid(payload, "attachmentId", "connection node")
        metadata = _read_metadata(payload.get("metadata", []), "Cable-end connection metadata")
        if property_overrides is None:
            set_cable_end_attachment_properties(
                harness_id, connection_id, attachment_id, metadata, gateway
            )
        else:
            set_cable_end_attachment_properties(
                harness_id,
                connection_id,
                attachment_id,
                metadata,
                gateway,
                diameter_mm=property_overrides.diameter_mm,
                conductor_diameter_mm=property_overrides.conductor_diameter_mm,
                insulation_material=property_overrides.insulation_material,
                conductor_material=property_overrides.conductor_material,
                shielding=property_overrides.shielding,
                dielectric_material=property_overrides.dielectric_material,
                manufacturer=property_overrides.manufacturer,
                part_number=property_overrides.part_number,
            )
        return "Saved cable-end connection properties."
    if action == "set_cable_end_attachment_shielding":
        shielding = payload.get("shielding")
        if shielding is not None and not isinstance(shielding, str):
            raise ValueError("Connection shielding override must be text or null.")
        dielectric_material = payload.get("dielectricMaterial")
        if dielectric_material is not None and not isinstance(dielectric_material, str):
            raise ValueError("Connection dielectric-material override must be text or null.")
        set_cable_end_attachment_shielding(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable-end connection"),
            _read_payload_uuid(payload, "attachmentId", "connection node"),
            shielding,
            dielectric_material,
            _read_metadata(payload.get("metadata", []), "Cable-end connection metadata"),
            gateway,
        )
        return "Saved cable-end connection shielding."
    if action == "set_cable_end_attachment_visual_overrides":
        set_cable_end_attachment_visual_overrides(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "cable-end connection"),
            _read_payload_uuid(payload, "attachmentId", "connection node"),
            _read_visual_overrides(payload.get("overrides")),
            gateway,
        )
        return "Saved cable-end connection materials."
    if action in {"rename_harness", "rename_junction", "rename_pathway", "rename_interface"}:
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Rename request requires a text name.")
        if action == "rename_harness":
            rename_harness(harness_id, name, gateway)
        elif action == "rename_junction":
            rename_junction(
                harness_id,
                _read_payload_uuid(payload, "junctionId", "junction"),
                name,
                gateway,
            )
        elif action == "rename_interface":
            rename_interface(
                harness_id,
                _read_payload_uuid(payload, "interfaceId", "Interface"),
                name,
                gateway,
            )
        else:
            field = payload.get("field")
            if not isinstance(field, str):
                raise ValueError("Pathway rename request requires a field.")
            rename_pathway(
                harness_id,
                _read_payload_uuid(payload, "pathwayId", "pathway"),
                field,
                name,
                gateway,
            )
        return "Saved name."
    raise ValueError(f"Unsupported harness edit: {action}")
