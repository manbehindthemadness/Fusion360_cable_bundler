"""
Fusion UI services for edits.
"""

from __future__ import annotations

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import (
    move_pathway_gate,
    move_wire_endpoint,
    remove_junction_relationship,
    remove_pathway_gate,
    remove_standalone_end,
    remove_wire,
    rename_junction,
    rename_pathway,
    rename_route_end,
    rename_wire,
    set_harness_material_defaults,
    set_wire_diameter,
    set_wire_material_overrides,
    update_junction_relationships,
)
from ...application.edit_harness import set_interpolation
from ...domain import JunctionPathwayRelationship, PathwayEndpoint
from ...domain.codec import parse_interpolation
from .commands.ends import apply_end_member_edit
from .payloads import (
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
    if action == "remove_end_member":
        apply_end_member_edit(application, {**payload, "editAction": "remove"})
        return "Removed end member."
    if action == "move_end_member":
        apply_end_member_edit(application, {**payload, "editAction": "reorder"})
        return "Reordered end member."
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
    if action == "remove_standalone_end":
        remove_standalone_end(
            harness_id,
            _read_payload_uuid(payload, "connectionId", "standalone end"),
            gateway,
        )
        return "Deleted standalone end."
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
        )
        return "Saved interpolation options."
    if action == "set_wire_diameter":
        diameter = payload.get("diameterMm")
        if isinstance(diameter, bool) or not isinstance(diameter, (int, float)):
            raise ValueError("Wire diameter must be a number in millimeters.")
        set_wire_diameter(
            harness_id, _read_payload_uuid(payload, "wireId", "wire"), diameter, gateway
        )
        return "Saved wire diameter."
    if action == "set_harness_material_defaults":
        set_harness_material_defaults(
            harness_id,
            _read_material_settings(payload.get("materials")),
            gateway,
        )
        return "Saved harness wire-material defaults."
    if action == "set_wire_material_overrides":
        set_wire_material_overrides(
            harness_id,
            _read_payload_uuid(payload, "wireId", "wire"),
            _read_material_overrides(payload.get("overrides")),
            gateway,
        )
        return "Saved wire-material overrides."
    if action in {"rename_junction", "rename_pathway", "rename_wire"}:
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Rename request requires a text name.")
        if action == "rename_wire":
            rename_wire(harness_id, _read_payload_uuid(payload, "wireId", "wire"), name, gateway)
        elif action == "rename_junction":
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
    if action == "rename_route_end":
        endpoint = payload.get("endpoint")
        name = payload.get("name")
        if not isinstance(endpoint, str) or not isinstance(name, str):
            raise ValueError("End name request requires an endpoint and a text name.")
        rename_route_end(
            harness_id,
            _read_payload_uuid(payload, "wireId", "wire"),
            endpoint,
            name,
            gateway,
        )
        return "Saved end name."
    if action == "move_wire_endpoint":
        endpoint = payload.get("endpoint")
        if not isinstance(endpoint, str):
            raise ValueError("Wire endpoint request is missing an endpoint sequence.")
        move_wire_endpoint(
            harness_id,
            _read_payload_uuid(payload, "wireId", "wire"),
            endpoint,
            _read_payload_offset(payload),
            gateway,
        )
        return f"Reordered {endpoint} connection sequence."
    if action == "remove_wire":
        remove_wire(
            harness_id,
            _read_payload_uuid(payload, "wireId", "wire"),
            gateway,
        )
        return "Removed wire pair."
    raise ValueError(f"Unsupported harness edit: {action}")
