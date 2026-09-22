"""
JSON serialization for versioned harness definitions.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, Optional, cast
from uuid import UUID

from .codec_support import DefinitionParseError, parse_interpolation
from .codec_support import optional_float as _optional_float
from .codec_support import optional_str as _optional_str
from .codec_support import parse_uuid as _parse_uuid
from .codec_support import require_enum as _require_enum
from .codec_support import require_finite_nonnegative_float as _require_finite_nonnegative_float
from .codec_support import require_float as _require_float
from .codec_support import require_int as _require_int
from .codec_support import require_list as _require_list
from .codec_support import require_mapping as _require_mapping
from .codec_support import require_str as _require_str
from .codec_support import require_uuid as _require_uuid
from .model import (
    SCHEMA_VERSION,
    AttachmentTargetKind,
    AutoTransitionPreset,
    CableAppearanceReference,
    CableColor,
    CableEndAttachment,
    CableEndTarget,
    CableGroupDefinition,
    CableMaterialOverrides,
    CableMaterialSettings,
    CableStripe,
    CableVisualOverrides,
    Connection,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    PathwayDefinition,
    PathwayEndpoint,
    RefineGeometry,
    RoutingMode,
    StandaloneEndDefinition,
    StripePattern,
)


def dumps(definition: HarnessDefinition) -> str:
    """
    Serialize a harness definition to deterministic JSON.
    """
    payload = _definition_to_dict(definition)
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    return serialized


def loads(serialized: str) -> HarnessDefinition:
    """
    Parse and shape-check a serialized harness definition.

    Raises:
        DefinitionParseError: If JSON or a required data shape is invalid.
    """
    try:
        raw_payload = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise DefinitionParseError("$", f"invalid JSON: {error.msg}") from error

    payload = _require_mapping(raw_payload, "$")
    schema_version = _require_int(payload, "schema_version", "$.schema_version")
    if schema_version not in (
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        SCHEMA_VERSION,
    ):
        raise DefinitionParseError(
            "$.schema_version",
            f"unsupported version {schema_version}; expected {SCHEMA_VERSION} "
            "(schemas 12 through 23 are migratable)",
        )

    harness_id = _require_uuid(payload, "harness_id", "$.harness_id")
    name = _require_str(payload, "name", "$.name")
    routing_mode = _require_enum(RoutingMode, payload, "routing_mode", "$.routing_mode")
    connections = tuple(
        _parse_connection(item, f"$.connections[{index}]")
        for index, item in enumerate(_require_list(payload, "connections", "$.connections"))
    )
    controls = tuple(
        _parse_control(item, f"$.controls[{index}]")
        for index, item in enumerate(_require_list(payload, "controls", "$.controls"))
    )
    pathways = tuple(
        _parse_pathway(item, f"$.pathways[{index}]")
        for index, item in enumerate(_require_list(payload, "pathways", "$.pathways"))
    )
    junctions = tuple(
        _parse_junction(item, f"$.junctions[{index}]")
        for index, item in enumerate(_require_list(payload, "junctions", "$.junctions"))
    )
    standalone_ends = tuple(
        _parse_standalone_end(
            item,
            f"$.standalone_ends[{index}]",
            require_controls=schema_version >= 16,
        )
        for index, item in enumerate(_require_list(payload, "standalone_ends", "$.standalone_ends"))
    )
    cable_groups = tuple(
        _parse_cable_group(item, f"$.cable_groups[{index}]")
        for index, item in enumerate(_require_list(payload, "cable_groups", "$.cable_groups"))
    )
    definition = HarnessDefinition(
        schema_version=SCHEMA_VERSION,
        harness_id=harness_id,
        name=name,
        routing_mode=routing_mode,
        connections=connections,
        controls=controls,
        pathways=pathways,
        junctions=junctions,
        standalone_ends=standalone_ends,
        cable_groups=cable_groups,
        gate_defaults=parse_interpolation(payload.get("gate_defaults", {}), "$.gate_defaults"),
        end_defaults=parse_interpolation(payload.get("end_defaults", {}), "$.end_defaults"),
        material_defaults=parse_material_settings(
            payload.get("material_defaults"), "$.material_defaults"
        ),
        minimum_clearance_mm=_require_finite_nonnegative_float(
            payload.get("minimum_clearance_mm", 0.0),
            "$.minimum_clearance_mm",
        ),
        auto_transition_preset=(
            _require_enum(
                AutoTransitionPreset,
                payload,
                "auto_transition_preset",
                "$.auto_transition_preset",
            )
            if schema_version >= 14
            else AutoTransitionPreset.TIGHT
        ),
        metadata=_parse_metadata(payload.get("metadata", []), "$.metadata"),
    )
    return definition


def _definition_to_dict(definition: HarnessDefinition) -> dict[str, Any]:
    """
    Convert a definition to JSON-compatible primitives.
    """
    payload = {
        "schema_version": definition.schema_version,
        "harness_id": str(definition.harness_id),
        "name": definition.name,
        "routing_mode": definition.routing_mode.value,
        "gate_defaults": asdict(definition.gate_defaults),
        "end_defaults": asdict(definition.end_defaults),
        "material_defaults": _materials_to_dict(definition.material_defaults),
        "minimum_clearance_mm": definition.minimum_clearance_mm,
        "auto_transition_preset": definition.auto_transition_preset.value,
        "metadata": _metadata_to_list(definition.metadata),
        "connections": [
            {
                "interpolation": asdict(connection.interpolation),
                "connection_id": str(connection.connection_id),
                "name": connection.name,
                "entity_token": connection.entity_token,
                "additional_entity_tokens": list(connection.additional_entity_tokens),
                "metadata": _metadata_to_list(connection.metadata),
                "attachment": (
                    _attachment_to_dict(connection.attachment)
                    if connection.attachment is not None
                    else None
                ),
                "additional_attachments": [
                    _attachment_to_dict(attachment)
                    for attachment in connection.additional_attachments
                ],
                **(
                    {
                        "member_interpolations": [
                            asdict(item) if item is not None else None
                            for item in connection.member_interpolations
                        ]
                    }
                    if connection.member_interpolations
                    else {}
                ),
                **(
                    {"member_ids": [str(identity) for identity in connection.member_ids]}
                    if connection.member_ids
                    else {}
                ),
            }
            for connection in definition.connections
        ],
        "controls": [
            {
                "interpolation": asdict(control.interpolation),
                "interpolation_is_override": control.interpolation_is_override,
                "control_id": str(control.control_id),
                "name": control.name,
                "kind": control.kind.value,
                "entity_token": control.entity_token,
                "refine_geometry": (
                    asdict(control.refine_geometry) if control.refine_geometry is not None else None
                ),
            }
            for control in definition.controls
        ],
        "pathways": [
            {
                "pathway_id": str(pathway.pathway_id),
                "name": pathway.name,
                "start_name": pathway.start_name,
                "end_name": pathway.end_name,
                "routing_mode": pathway.routing_mode.value,
                "ordered_control_ids": [
                    str(control_id) for control_id in pathway.ordered_control_ids
                ],
                "metadata": _metadata_to_list(pathway.metadata),
                "start_metadata": _metadata_to_list(pathway.start_metadata),
                "end_metadata": _metadata_to_list(pathway.end_metadata),
            }
            for pathway in definition.pathways
        ],
        "junctions": [
            {
                "junction_id": str(junction.junction_id),
                "name": junction.name,
                "control_id": str(junction.control_id),
                "pathway_relationships": [
                    {
                        "pathway_id": str(relationship.pathway_id),
                        "endpoint": relationship.endpoint.value,
                    }
                    for relationship in junction.pathway_relationships
                ],
                "metadata": _metadata_to_list(junction.metadata),
            }
            for junction in definition.junctions
        ],
        "standalone_ends": [
            {
                "connection_id": str(end.connection_id),
                "pathway_id": str(end.pathway_id),
                "endpoint": end.endpoint.value,
                "ordered_control_ids": [str(control_id) for control_id in end.ordered_control_ids],
            }
            for end in definition.standalone_ends
        ],
        "cable_groups": [
            {
                "cable_group_id": str(group.cable_group_id),
                "connection_ids": [str(connection_id) for connection_id in group.connection_ids],
                "diameter_mm": group.diameter_mm,
                "material_overrides": _material_overrides_to_dict(group.material_overrides),
                "metadata_overrides": _metadata_to_list(group.metadata_overrides),
                "name": group.name,
            }
            for group in definition.cable_groups
        ],
    }
    return payload


def _attachment_to_dict(attachment: CableEndAttachment) -> dict[str, Any]:
    """
    Convert one ordered external connection node to JSON-compatible primitives.
    """
    return {
        "target_kind": (
            attachment.target_kind.value if attachment.target_kind is not None else None
        ),
        "entity_token": attachment.entity_token,
        "inherited_name": attachment.inherited_name,
        "name": attachment.name,
        "parameters": list(attachment.parameters),
        "metadata": _metadata_to_list(attachment.metadata),
        "attachment_id": str(attachment.attachment_id),
        "parent_attachment_id": (
            str(attachment.parent_attachment_id)
            if attachment.parent_attachment_id is not None
            else None
        ),
        "ordered_control_ids": [str(control_id) for control_id in attachment.ordered_control_ids],
        "visual_overrides": _visual_overrides_to_dict(attachment.visual_overrides),
        "shielding_target": (
            None
            if attachment.shielding_target is None
            else _target_to_dict(attachment.shielding_target)
        ),
    }


def _target_to_dict(target: CableEndTarget) -> dict[str, object]:
    """
    Convert one secondary external relationship target to portable values.
    """
    return {
        "target_kind": target.target_kind.value,
        "entity_token": target.entity_token,
        "inherited_name": target.inherited_name,
        "name": target.name,
        "parameters": list(target.parameters),
    }


def _visual_overrides_to_dict(overrides: CableVisualOverrides) -> dict[str, object]:
    """
    Convert branch overrides while preserving null inheritance.
    """
    return {
        "diameter_mm": overrides.diameter_mm,
        "insulation_material": overrides.insulation_material,
        "conductor_material": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectric_material": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "part_number": overrides.part_number,
        "main_color": None
        if overrides.main_color is None
        else _color_to_dict(overrides.main_color),
        "appearance": _appearance_to_dict(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_to_dict(item) for item in overrides.stripes]
        ),
    }


def _color_to_dict(color: CableColor) -> dict[str, object]:
    """
    Convert one portable cable color to JSON-compatible values.
    """
    return {
        "name": color.name,
        "red": color.red,
        "green": color.green,
        "blue": color.blue,
    }


def _metadata_to_list(entries: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    """
    Convert ordered searchable metadata to JSON-compatible rows.
    """
    return [{"key": key, "value": value} for key, value in entries]


def _parse_metadata(raw_value: object, path: str) -> tuple[tuple[str, str], ...]:
    """
    Parse ordered key/value metadata while rejecting ambiguous duplicate keys.
    """
    if not isinstance(raw_value, list):
        raise DefinitionParseError(path, "expected a list")
    entries: list[tuple[str, str]] = []
    normalized_keys: set[str] = set()
    for index, raw_entry in enumerate(raw_value):
        entry_path = f"{path}[{index}]"
        entry = _require_mapping(raw_entry, entry_path)
        key = _require_str(entry, "key", f"{entry_path}.key")
        value = _require_str(entry, "value", f"{entry_path}.value")
        normalized_key = key.strip().casefold()
        if not normalized_key:
            raise DefinitionParseError(f"{entry_path}.key", "expected non-empty text")
        if normalized_key in normalized_keys:
            raise DefinitionParseError(f"{entry_path}.key", "duplicate metadata key")
        normalized_keys.add(normalized_key)
        entries.append((key, value))
    return tuple(entries)


def _stripe_to_dict(stripe: CableStripe) -> dict[str, object]:
    """
    Convert one procedural stripe to JSON-compatible values.
    """
    return {
        "color": _color_to_dict(stripe.color),
        "width_mm": stripe.width_mm,
        "pattern": stripe.pattern.value,
        "angle_deg": stripe.angle_deg,
        "repeat_mm": stripe.repeat_mm,
    }


def _materials_to_dict(settings: CableMaterialSettings) -> dict[str, object]:
    """
    Convert resolved cable material settings to JSON-compatible values.
    """
    return {
        "insulation_material": settings.insulation_material,
        "main_color": _color_to_dict(settings.main_color),
        "appearance": _appearance_to_dict(settings.appearance),
        "stripes": [_stripe_to_dict(stripe) for stripe in settings.stripes],
        "conductor_material": settings.conductor_material,
        "shielding": settings.shielding,
        "dielectric_material": settings.dielectric_material,
        "manufacturer": settings.manufacturer,
        "part_number": settings.part_number,
        "notes": settings.notes,
    }


def _material_overrides_to_dict(overrides: CableMaterialOverrides) -> dict[str, object]:
    """
    Preserve null inheritance markers while serializing per-group overrides.
    """
    return {
        "insulation_material": overrides.insulation_material,
        "main_color": (
            None if overrides.main_color is None else _color_to_dict(overrides.main_color)
        ),
        "appearance": _appearance_to_dict(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_to_dict(stripe) for stripe in overrides.stripes]
        ),
        "conductor_material": overrides.conductor_material,
        "shielding": overrides.shielding,
        "dielectric_material": overrides.dielectric_material,
        "manufacturer": overrides.manufacturer,
        "part_number": overrides.part_number,
        "notes": overrides.notes,
    }


def _parse_color(raw_value: object, path: str) -> CableColor:
    """
    Parse one named RGB color at an external-data boundary.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableColor(
            name=_require_str(value, "name", f"{path}.name"),
            red=_require_int(value, "red", f"{path}.red"),
            green=_require_int(value, "green", f"{path}.green"),
            blue=_require_int(value, "blue", f"{path}.blue"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _appearance_to_dict(
    appearance: Optional[CableAppearanceReference],
) -> Optional[dict[str, str]]:
    """
    Convert an optional Fusion library appearance reference to portable values.
    """
    if appearance is None:
        return None
    return {
        "library_id": appearance.library_id,
        "library_name": appearance.library_name,
        "appearance_id": appearance.appearance_id,
        "appearance_name": appearance.appearance_name,
    }


def _parse_appearance(raw_value: object, path: str) -> Optional[CableAppearanceReference]:
    """
    Parse an optional Fusion library appearance reference.
    """
    if raw_value is None:
        return None
    value = _require_mapping(raw_value, path)
    try:
        return CableAppearanceReference(
            library_id=_require_str(value, "library_id", f"{path}.library_id"),
            library_name=_require_str(value, "library_name", f"{path}.library_name"),
            appearance_id=_require_str(value, "appearance_id", f"{path}.appearance_id"),
            appearance_name=_require_str(value, "appearance_name", f"{path}.appearance_name"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_stripes(raw_value: object, path: str) -> tuple[CableStripe, ...]:
    """
    Parse an ordered procedural stripe collection.
    """
    if not isinstance(raw_value, list):
        raise DefinitionParseError(path, "expected a list")
    stripes: list[CableStripe] = []
    for index, raw_stripe in enumerate(raw_value):
        stripe_path = f"{path}[{index}]"
        value = _require_mapping(raw_stripe, stripe_path)
        try:
            stripes.append(
                CableStripe(
                    color=_parse_color(value.get("color"), f"{stripe_path}.color"),
                    width_mm=_require_float(value, "width_mm", f"{stripe_path}.width_mm"),
                    pattern=_require_enum(
                        StripePattern, value, "pattern", f"{stripe_path}.pattern"
                    ),
                    angle_deg=_require_float(
                        {"angle_deg": 0.0, **value}, "angle_deg", f"{stripe_path}.angle_deg"
                    ),
                    repeat_mm=_optional_float(value.get("repeat_mm"), f"{stripe_path}.repeat_mm"),
                )
            )
        except ValueError as error:
            raise DefinitionParseError(stripe_path, str(error)) from error
    return tuple(stripes)


def parse_material_settings(raw_value: object, path: str) -> CableMaterialSettings:
    """
    Parse complete harness-level cable material defaults.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableMaterialSettings(
            insulation_material=_require_str(
                value, "insulation_material", f"{path}.insulation_material"
            ),
            main_color=_parse_color(value.get("main_color"), f"{path}.main_color"),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=_parse_stripes(value.get("stripes"), f"{path}.stripes"),
            conductor_material=_require_str(
                value, "conductor_material", f"{path}.conductor_material"
            ),
            shielding=_require_str({"shielding": "", **value}, "shielding", f"{path}.shielding"),
            dielectric_material=_require_str(
                {"dielectric_material": "", **value},
                "dielectric_material",
                f"{path}.dielectric_material",
            ),
            manufacturer=_require_str(value, "manufacturer", f"{path}.manufacturer"),
            part_number=_require_str(value, "part_number", f"{path}.part_number"),
            notes=_require_str(value, "notes", f"{path}.notes"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def parse_material_overrides(raw_value: object, path: str) -> CableMaterialOverrides:
    """
    Parse nullable field-level material overrides for one cable.
    """
    value = _require_mapping(raw_value, path)
    try:
        return CableMaterialOverrides(
            insulation_material=_optional_str(
                value.get("insulation_material"), f"{path}.insulation_material"
            ),
            main_color=(
                None
                if value.get("main_color") is None
                else _parse_color(value.get("main_color"), f"{path}.main_color")
            ),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=(
                None
                if value.get("stripes") is None
                else _parse_stripes(value.get("stripes"), f"{path}.stripes")
            ),
            conductor_material=_optional_str(
                value.get("conductor_material"), f"{path}.conductor_material"
            ),
            shielding=_optional_str(value.get("shielding"), f"{path}.shielding"),
            dielectric_material=_optional_str(
                value.get("dielectric_material"), f"{path}.dielectric_material"
            ),
            manufacturer=_optional_str(value.get("manufacturer"), f"{path}.manufacturer"),
            part_number=_optional_str(value.get("part_number"), f"{path}.part_number"),
            notes=_optional_str(value.get("notes"), f"{path}.notes"),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_connection(raw_value: object, path: str) -> Connection:
    """
    Parse one physical connection reference.
    """
    value = _require_mapping(raw_value, path)
    raw_members = _require_list(
        {"additional_entity_tokens": [], **value},
        "additional_entity_tokens",
        f"{path}.additional_entity_tokens",
    )
    members: list[str] = []
    for token in raw_members:
        if not isinstance(token, str) or not token.strip():
            raise DefinitionParseError(
                f"{path}.additional_entity_tokens", "expected non-empty strings"
            )
        members.append(token)
    identities = tuple(
        _parse_uuid(identity, f"{path}.member_ids[{index}]")
        for index, identity in enumerate(
            _require_list({"member_ids": [], **value}, "member_ids", f"{path}.member_ids")
        )
    )
    if "member_ids" in value and (
        len(identities) != len(members) + 1 or len(set(identities)) != len(identities)
    ):
        raise DefinitionParseError(f"{path}.member_ids", "expected one unique ID per member")
    settings = tuple(
        parse_interpolation(item, f"{path}.member_interpolations[{index}]")
        if item is not None
        else None
        for index, item in enumerate(
            _require_list(
                {"member_interpolations": [], **value},
                "member_interpolations",
                f"{path}.member_interpolations",
            )
        )
    )
    if "member_interpolations" in value and len(settings) != len(members) + 1:
        raise DefinitionParseError(
            f"{path}.member_interpolations", "expected one setting per member"
        )
    connection = Connection(
        connection_id=_require_uuid(value, "connection_id", f"{path}.connection_id"),
        name=_require_str(value, "name", f"{path}.name"),
        entity_token=_require_str(value, "entity_token", f"{path}.entity_token"),
        additional_entity_tokens=tuple(members),
        member_ids=identities,
        member_interpolations=settings,
        interpolation=parse_interpolation(value.get("interpolation", {}), f"{path}.interpolation"),
        metadata=_parse_metadata(value.get("metadata", []), f"{path}.metadata"),
        attachment=_parse_attachment(value.get("attachment"), f"{path}.attachment"),
        additional_attachments=_parse_additional_attachments(value, path),
    )
    return connection


def _parse_additional_attachments(
    value: Mapping[str, Any],
    path: str,
) -> tuple[CableEndAttachment, ...]:
    """
    Parse required connection nodes from the optional ordered extension list.
    """
    raw_items = _require_list(
        {"additional_attachments": [], **value},
        "additional_attachments",
        f"{path}.additional_attachments",
    )
    attachments: list[CableEndAttachment] = []
    for index, item in enumerate(raw_items):
        item_path = f"{path}.additional_attachments[{index}]"
        attachment = _parse_attachment(item, item_path)
        if attachment is None:
            raise DefinitionParseError(item_path, "expected a connection object")
        attachments.append(attachment)
    return tuple(attachments)


def _parse_attachment(raw_value: object, path: str) -> Optional[CableEndAttachment]:
    """
    Parse one optional Fusion-backed cable-end attachment.
    """
    if raw_value is None:
        return None
    value = _require_mapping(raw_value, path)
    parameters = _parse_target_parameters(value, path)
    try:
        raw_target_kind = value.get("target_kind")
        target_kind = (
            None
            if raw_target_kind is None
            else _require_enum(
                AttachmentTargetKind,
                value,
                "target_kind",
                f"{path}.target_kind",
            )
        )
        return CableEndAttachment(
            target_kind=target_kind,
            entity_token=_require_str(value, "entity_token", f"{path}.entity_token"),
            inherited_name=_require_str(value, "inherited_name", f"{path}.inherited_name"),
            name=_require_str(value, "name", f"{path}.name"),
            parameters=tuple(parameters),
            metadata=_parse_metadata(value.get("metadata", []), f"{path}.metadata"),
            attachment_id=(
                _require_uuid(value, "attachment_id", f"{path}.attachment_id")
                if "attachment_id" in value
                else UUID(int=0)
            ),
            parent_attachment_id=(
                _require_uuid(value, "parent_attachment_id", f"{path}.parent_attachment_id")
                if value.get("parent_attachment_id") is not None
                else None
            ),
            ordered_control_ids=tuple(
                _parse_uuid(control_id, f"{path}.ordered_control_ids[{index}]")
                for index, control_id in enumerate(
                    _require_list(
                        {"ordered_control_ids": [], **value},
                        "ordered_control_ids",
                        f"{path}.ordered_control_ids",
                    )
                )
            ),
            visual_overrides=_parse_visual_overrides(
                value.get("visual_overrides", {}), f"{path}.visual_overrides"
            ),
            shielding_target=(
                None
                if value.get("shielding_target") is None
                else _parse_target(value.get("shielding_target"), f"{path}.shielding_target")
            ),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_target(raw_value: object, path: str) -> CableEndTarget:
    """
    Parse one complete secondary external relationship target.
    """
    value = _require_mapping(raw_value, path)
    parameters = _parse_target_parameters(value, path)
    try:
        return CableEndTarget(
            target_kind=_require_enum(
                AttachmentTargetKind, value, "target_kind", f"{path}.target_kind"
            ),
            entity_token=_require_str(value, "entity_token", f"{path}.entity_token"),
            inherited_name=_require_str(value, "inherited_name", f"{path}.inherited_name"),
            name=_require_str({"name": "", **value}, "name", f"{path}.name"),
            parameters=parameters,
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_target_parameters(value: Mapping[str, Any], path: str) -> tuple[float, ...]:
    """
    Parse finite target parameters shared by primary and shielding relationships.
    """
    raw_parameters = _require_list(value, "parameters", f"{path}.parameters")
    parameters: list[float] = []
    for index, raw_parameter in enumerate(raw_parameters):
        parameter_path = f"{path}.parameters[{index}]"
        if isinstance(raw_parameter, bool) or not isinstance(raw_parameter, (int, float)):
            raise DefinitionParseError(parameter_path, "expected a number")
        parameter = float(raw_parameter)
        if not math.isfinite(parameter):
            raise DefinitionParseError(parameter_path, "expected a finite number")
        parameters.append(parameter)
    return tuple(parameters)


def _parse_visual_overrides(raw_value: object, path: str) -> CableVisualOverrides:
    """
    Parse optional branch overrides from current or migrated data.
    """
    value = _require_mapping(raw_value, path)
    raw_color = value.get("main_color")
    raw_stripes = value.get("stripes")
    try:
        return CableVisualOverrides(
            diameter_mm=_optional_float(value.get("diameter_mm"), f"{path}.diameter_mm"),
            insulation_material=_optional_str(
                value.get("insulation_material"), f"{path}.insulation_material"
            ),
            conductor_material=_optional_str(
                value.get("conductor_material"), f"{path}.conductor_material"
            ),
            shielding=_optional_str(value.get("shielding"), f"{path}.shielding"),
            dielectric_material=_optional_str(
                value.get("dielectric_material"), f"{path}.dielectric_material"
            ),
            manufacturer=_optional_str(value.get("manufacturer"), f"{path}.manufacturer"),
            part_number=_optional_str(value.get("part_number"), f"{path}.part_number"),
            main_color=None if raw_color is None else _parse_color(raw_color, f"{path}.main_color"),
            appearance=_parse_appearance(value.get("appearance"), f"{path}.appearance"),
            stripes=(
                None if raw_stripes is None else _parse_stripes(raw_stripes, f"{path}.stripes")
            ),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_control(raw_value: object, path: str) -> ControlStructure:
    """
    Parse one routing control reference.
    """
    value = _require_mapping(raw_value, path)
    override = value.get("interpolation_is_override", False)
    if not isinstance(override, bool):
        raise DefinitionParseError(f"{path}.interpolation_is_override", "expected a boolean")
    kind = _require_enum(ControlKind, value, "kind", f"{path}.kind")
    refine_geometry = (
        _parse_refine_geometry(value.get("refine_geometry"), f"{path}.refine_geometry")
        if kind is ControlKind.REFINE
        else None
    )
    control = ControlStructure(
        control_id=_require_uuid(value, "control_id", f"{path}.control_id"),
        name=_require_str(value, "name", f"{path}.name"),
        kind=kind,
        interpolation_is_override=override,
        interpolation=parse_interpolation(value.get("interpolation", {}), f"{path}.interpolation"),
        entity_token=_require_str(
            {"entity_token": "", **value}, "entity_token", f"{path}.entity_token"
        ),
        refine_geometry=refine_geometry,
    )
    return control


def _parse_refine_geometry(raw_value: object, path: str) -> RefineGeometry:
    """
    Parse one host-independent refine frame.
    """
    value = _require_mapping(raw_value, path)

    def vector(key: str) -> tuple[float, float, float]:
        """
        Parse one fixed-length numeric vector.
        """
        items = _require_list(value, key, f"{path}.{key}")
        if len(items) != 3:
            raise DefinitionParseError(f"{path}.{key}", "expected exactly three numbers")
        parsed = tuple(
            _require_float({"value": item}, "value", f"{path}.{key}[{index}]")
            for index, item in enumerate(items)
        )
        return cast(tuple[float, float, float], parsed)

    try:
        return RefineGeometry(
            origin_mm=vector("origin_mm"),
            u_direction=vector("u_direction"),
            v_direction=vector("v_direction"),
            display_radius_mm=_require_float(
                value, "display_radius_mm", f"{path}.display_radius_mm"
            ),
        )
    except ValueError as error:
        raise DefinitionParseError(path, str(error)) from error


def _parse_pathway(raw_value: object, path: str) -> PathwayDefinition:
    """
    Parse one reusable ordered pathway.
    """
    value = _require_mapping(raw_value, path)
    raw_control_ids = _require_list(
        value,
        "ordered_control_ids",
        f"{path}.ordered_control_ids",
    )
    control_ids = tuple(
        _parse_uuid(raw_id, f"{path}.ordered_control_ids[{index}]")
        for index, raw_id in enumerate(raw_control_ids)
    )
    pathway = PathwayDefinition(
        pathway_id=_require_uuid(value, "pathway_id", f"{path}.pathway_id"),
        name=_require_str(value, "name", f"{path}.name"),
        start_name=_require_str({"start_name": "", **value}, "start_name", f"{path}.start_name"),
        end_name=_require_str({"end_name": "", **value}, "end_name", f"{path}.end_name"),
        routing_mode=_require_enum(
            RoutingMode,
            value,
            "routing_mode",
            f"{path}.routing_mode",
        ),
        ordered_control_ids=control_ids,
        metadata=_parse_metadata(value.get("metadata", []), f"{path}.metadata"),
        start_metadata=_parse_metadata(value.get("start_metadata", []), f"{path}.start_metadata"),
        end_metadata=_parse_metadata(value.get("end_metadata", []), f"{path}.end_metadata"),
    )
    return pathway


def _parse_junction(
    raw_value: object,
    path: str,
) -> JunctionDefinition:
    """
    Parse one junction and its endpoint-qualified pathway relationships.
    """
    value = _require_mapping(raw_value, path)
    relationships = tuple(
        _parse_junction_relationship(
            item,
            f"{path}.pathway_relationships[{index}]",
        )
        for index, item in enumerate(
            _require_list(value, "pathway_relationships", f"{path}.pathway_relationships")
        )
    )
    return JunctionDefinition(
        junction_id=_require_uuid(value, "junction_id", f"{path}.junction_id"),
        name=_require_str(value, "name", f"{path}.name"),
        control_id=_require_uuid(value, "control_id", f"{path}.control_id"),
        pathway_relationships=relationships,
        metadata=_parse_metadata(value.get("metadata", []), f"{path}.metadata"),
    )


def _parse_junction_relationship(
    raw_value: object,
    path: str,
) -> JunctionPathwayRelationship:
    """
    Parse one endpoint-qualified junction relationship.
    """
    value = _require_mapping(raw_value, path)
    return JunctionPathwayRelationship(
        pathway_id=_require_uuid(value, "pathway_id", f"{path}.pathway_id"),
        endpoint=_require_enum(PathwayEndpoint, value, "endpoint", f"{path}.endpoint"),
    )


def _parse_standalone_end(
    raw_value: object,
    path: str,
    *,
    require_controls: bool,
) -> StandaloneEndDefinition:
    """
    Parse one pathway-end definition independently of cable assignment.
    """
    value = _require_mapping(raw_value, path)
    raw_control_ids = _require_list(
        value if require_controls else {"ordered_control_ids": [], **value},
        "ordered_control_ids",
        f"{path}.ordered_control_ids",
    )
    return StandaloneEndDefinition(
        connection_id=_require_uuid(value, "connection_id", f"{path}.connection_id"),
        pathway_id=_require_uuid(value, "pathway_id", f"{path}.pathway_id"),
        endpoint=_require_enum(PathwayEndpoint, value, "endpoint", f"{path}.endpoint"),
        ordered_control_ids=tuple(
            _parse_uuid(control_id, f"{path}.ordered_control_ids[{index}]")
            for index, control_id in enumerate(raw_control_ids)
        ),
    )


def _parse_cable_group(
    raw_value: object,
    path: str,
) -> CableGroupDefinition:
    """
    Parse one persistent collection of assigned cable ends.
    """
    value = _require_mapping(raw_value, path)
    raw_connection_ids = _require_list(value, "connection_ids", f"{path}.connection_ids")
    name = value.get("name", "")
    if not isinstance(name, str):
        raise DefinitionParseError(f"{path}.name", "expected a string")
    return CableGroupDefinition(
        cable_group_id=_require_uuid(value, "cable_group_id", f"{path}.cable_group_id"),
        connection_ids=tuple(
            _parse_uuid(raw_id, f"{path}.connection_ids[{index}]")
            for index, raw_id in enumerate(raw_connection_ids)
        ),
        diameter_mm=_require_float(value, "diameter_mm", f"{path}.diameter_mm"),
        material_overrides=parse_material_overrides(
            value.get("material_overrides"), f"{path}.material_overrides"
        ),
        metadata_overrides=_parse_metadata(
            value.get("metadata_overrides", []), f"{path}.metadata_overrides"
        ),
        name=name,
    )
