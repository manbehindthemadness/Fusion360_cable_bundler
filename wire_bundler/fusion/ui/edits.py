"""
Fusion UI services for edits.
"""

from __future__ import annotations

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import (
    WireEditorPairing,
    WireEditorRename,
    move_pathway_gate,
    remove_junction,
    remove_junction_relationship,
    remove_pathway,
    remove_pathway_gate,
    remove_standalone_end,
    rename_junction,
    rename_pathway,
    rename_standalone_end,
    save_wire_editor,
    set_harness_material_defaults,
    set_harness_properties,
    set_wire_group_material_overrides,
    set_wire_group_properties,
    update_junction_relationships,
)
from ...application.edit_harness import set_interpolation
from ...domain import AutoTransitionPreset, JunctionPathwayRelationship, PathwayEndpoint
from ...domain.codec import parse_interpolation
from .payloads import (
    _read_harness_properties,
    _read_material_overrides,
    _read_material_settings,
    _read_palette_payload,
    _read_payload_offset,
    _read_payload_uuid,
)
from .support import (
    _create_harness_gateway,
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
    gateway = _create_harness_gateway(application)
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
    if action == "remove_standalone_end":
        remove_standalone_end(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "standalone end"),
            gateway,
        )
        return "Deleted standalone end."
    if action == "save_wire_editor":
        left_boundary = payload.get("leftBoundary")
        right_boundary = payload.get("rightBoundary")
        raw_pairings = payload.get("pairings")
        raw_detached = payload.get("detachedConnectionIds")
        raw_renames = payload.get("renames")
        raw_deleted = payload.get("deletedConnectionIds")
        if not isinstance(left_boundary, dict) or not isinstance(right_boundary, dict):
            raise ValueError("Route Editor boundaries must be objects.")
        if not all(
            isinstance(value, list)
            for value in (raw_pairings, raw_detached, raw_renames, raw_deleted)
        ):
            raise ValueError("Route Editor changes must be lists.")
        left_endpoint = left_boundary.get("endpoint")
        right_endpoint = right_boundary.get("endpoint")
        if left_endpoint not in {member.value for member in PathwayEndpoint}:
            raise ValueError("Route Editor left boundary has an invalid endpoint.")
        if right_endpoint not in {member.value for member in PathwayEndpoint}:
            raise ValueError("Route Editor right boundary has an invalid endpoint.")
        pairings: list[WireEditorPairing] = []
        for index, raw_pairing in enumerate(raw_pairings):
            if not isinstance(raw_pairing, dict):
                raise ValueError(f"Route Editor pairing {index + 1} must be an object.")
            pairings.append(
                WireEditorPairing(
                    _read_payload_uuid(raw_pairing, "leftConnectionId", "left wire end"),
                    _read_payload_uuid(raw_pairing, "rightConnectionId", "right wire end"),
                )
            )
        renames: list[WireEditorRename] = []
        for index, raw_rename in enumerate(raw_renames):
            if not isinstance(raw_rename, dict) or not isinstance(raw_rename.get("name"), str):
                raise ValueError(f"Route Editor rename {index + 1} must contain a text name.")
            renames.append(
                WireEditorRename(
                    _read_payload_uuid(raw_rename, "connectionId", "renamed wire end"),
                    raw_rename["name"],
                )
            )
        save_wire_editor(
            harness_id,
            _read_payload_uuid(left_boundary, "pathwayId", "left pathway"),
            PathwayEndpoint(left_endpoint),
            _read_payload_uuid(right_boundary, "pathwayId", "right pathway"),
            PathwayEndpoint(right_endpoint),
            tuple(pairings),
            tuple(
                _read_payload_uuid(
                    {"connectionId": connection_id}, "connectionId", "detached wire end"
                )
                for connection_id in raw_detached
            ),
            tuple(renames),
            tuple(
                _read_payload_uuid(
                    {"connectionId": connection_id}, "connectionId", "deleted wire end"
                )
                for connection_id in raw_deleted
            ),
            gateway,
        )
        return "Saved Route Editor changes."
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
    if action == "set_wire_group_properties":
        diameter = payload.get("diameterMm")
        if isinstance(diameter, bool) or not isinstance(diameter, (int, float)):
            raise ValueError("Wire-group diameter must be a number in millimeters.")
        property_materials = _read_material_overrides(
            {
                "insulationMaterial": payload.get("insulationMaterial"),
                "conductorMaterial": payload.get("conductorMaterial"),
                "manufacturer": payload.get("manufacturer"),
                "partNumber": payload.get("partNumber"),
                "notes": payload.get("notes"),
            }
        )
        set_wire_group_properties(
            harness_id,
            _read_payload_uuid(payload, "wireGroupId", "wire group"),
            diameter,
            property_materials.insulation_material,
            property_materials.conductor_material,
            property_materials.manufacturer,
            property_materials.part_number,
            property_materials.notes,
            gateway,
        )
        return "Saved connected-wire properties."
    if action == "set_harness_material_defaults":
        set_harness_material_defaults(
            harness_id,
            _read_material_settings(payload.get("materials")),
            gateway,
        )
        return "Saved harness wire-material defaults."
    if action == "set_harness_properties":
        (
            insulation_material,
            conductor_material,
            manufacturer,
            part_number,
            notes,
        ) = _read_harness_properties(payload)
        set_harness_properties(
            harness_id,
            insulation_material,
            conductor_material,
            manufacturer,
            part_number,
            notes,
            gateway,
        )
        return "Saved harness properties."
    if action == "set_wire_group_material_overrides":
        set_wire_group_material_overrides(
            harness_id,
            _read_payload_uuid(payload, "wireGroupId", "wire group"),
            _read_material_overrides(payload.get("overrides")),
            gateway,
        )
        return "Saved connected-wire material overrides."
    if action in {"rename_junction", "rename_pathway"}:
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Rename request requires a text name.")
        if action == "rename_junction":
            rename_junction(
                harness_id,
                _read_payload_uuid(payload, "junctionId", "junction"),
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
