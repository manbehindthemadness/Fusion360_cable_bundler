"""
Fusion UI services for palette state.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from time import perf_counter
from typing import Any, Callable, Optional, cast
from uuid import UUID, uuid4

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import (
    CableGroupRouteLeg,
    HarnessLoadResult,
    delete_damaged_harness,
    load_cable_material_catalog,
    load_harnesses,
    plan_cable_group_routes,
)
from ...domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndShape,
    CableGroupType,
    HarnessDefinition,
)
from ...domain.ffc import resolve_ffc_dimensions
from ..attachment_targets import attachment_display_name, resolve_attachment_target
from ..cable_solid_parts.constants import FINALIZED_OUTPUT_MODE
from ..cable_solids import (
    generated_cable_group_occurrences,
    generated_cable_group_output_mode,
)
from ..ffc_dimensions import ffc_contact_geometry
from ..interface_targets import resolve_interface_target
from ..route_preview import has_route_preview_for_harness
from .constants import PALETTE_ID
from .constants import ROUTING_MODE_LABELS as _ROUTING_MODE_LABELS
from .palette_geometry import PaletteEntityLookup
from .palette_material_payloads import (
    _color_payload,
    _material_overrides_payload,
    _material_settings_payload,
    _metadata_payload,
    _visual_overrides_payload,
)
from .payloads import (
    _read_palette_payload,
)
from .runtime import _contact_document_identity, _contact_document_key
from .runtime import runtime as _runtime
from .support import (
    _create_harness_gateway,
    _log_to_fusion,
)


def _contact_palette_document_scope(
    application: adsk.core.Application, design: Optional[adsk.fusion.Design]
) -> str:
    """
    Identify the active document without changing identity on every save.
    """
    identity = _contact_document_identity(application)
    if identity is not None:
        source = json.dumps(("saved", identity), separators=(",", ":"))
    else:
        token = getattr(getattr(design, "rootComponent", None), "entityToken", "")
        if not isinstance(token, str) or not token:
            return ""
        source = token
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _contact_palette_cache_scope(
    application: adsk.core.Application, design: Optional[adsk.fusion.Design]
) -> str:
    """
    Partition rendered contact snapshots by saved file version.
    """
    saved = _contact_document_key(application)
    if saved is None:
        return _contact_palette_document_scope(application, design)
    source = json.dumps(saved, separators=(",", ":"))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _attachment_payload(
    design: Optional[adsk.fusion.Design],
    lookup: PaletteEntityLookup,
    attachment: CableEndAttachment,
    resolved_diameter_mm: Optional[float] = None,
) -> dict[str, object]:
    """
    Serialize one independently addressable cable-end connection node.
    """
    connected = (
        resolve_attachment_target(design, attachment, find_entities=lookup.find_entities)
        is not None
        if design is not None
        else attachment.has_target and lookup.is_resolvable(attachment.entity_token)
    )
    shielding_target = attachment.shielding_target
    shielding_connected = (
        resolve_attachment_target(design, shielding_target, find_entities=lookup.find_entities)
        is not None
        if design is not None and shielding_target is not None
        else shielding_target is not None and lookup.is_resolvable(shielding_target.entity_token)
    )
    return {
        "attachmentId": str(attachment.attachment_id),
        "parentAttachmentId": (
            str(attachment.parent_attachment_id)
            if attachment.parent_attachment_id is not None
            else None
        ),
        "name": attachment_display_name(design, attachment, find_entities=lookup.find_entities),
        "nameOverride": attachment.name,
        "pinNumber": attachment.pin_number,
        "targetKind": attachment.target_kind.value if attachment.target_kind is not None else None,
        "metadata": _metadata_payload(attachment.metadata),
        "connected": connected,
        "shieldingTarget": (
            None
            if shielding_target is None
            else {
                "targetKind": shielding_target.target_kind.value,
                "name": attachment_display_name(
                    design, shielding_target, find_entities=lookup.find_entities
                ),
                "connected": shielding_connected,
            }
        ),
        "orderedControlIds": [str(control_id) for control_id in attachment.ordered_control_ids],
        "visualOverrides": _visual_overrides_payload(attachment.visual_overrides),
        "resolvedDiameterMm": resolved_diameter_mm,
    }


def _connected_interface_connections(
    definition: HarnessDefinition,
    design: Optional[adsk.fusion.Design],
    lookup: PaletteEntityLookup,
) -> dict[UUID, tuple[UUID, ...]]:
    """
    Project resolved contact-target matches without adding a persisted relationship.

    A connection can target several contacts on one Interface; its identity is
    returned once, in saved connection order. Pin labels do not establish links.
    """
    interfaces_by_target: dict[tuple[AttachmentTargetKind, str], set[UUID]] = {}
    for interface in definition.interfaces:
        for contact in interface.contacts:
            interfaces_by_target.setdefault((contact.kind, contact.entity_token), set()).add(
                interface.interface_id
            )
    connected: dict[UUID, list[UUID]] = {
        interface.interface_id: [] for interface in definition.interfaces
    }
    for connection in definition.connections:
        matched: set[UUID] = set()
        for attachment in connection.attachments:
            interface_ids = interfaces_by_target.get(
                (attachment.target_kind, attachment.entity_token), set()
            )
            if not interface_ids or not attachment.has_target:
                continue
            resolved = (
                resolve_attachment_target(design, attachment, find_entities=lookup.find_entities)
                is not None
                if design is not None
                else lookup.is_resolvable(attachment.entity_token)
            )
            if resolved:
                matched.update(interface_ids)
        for interface_id in matched:
            connected[interface_id].append(connection.connection_id)
    return {
        interface_id: tuple(connection_ids) for interface_id, connection_ids in connected.items()
    }


def _send_palette_state(
    application: adsk.core.Application,
    notice: str = "",
) -> None:
    """
    Push the current harness library to an existing palette.
    """
    palette = application.userInterface.palettes.itemById(PALETTE_ID)
    if palette is None:
        return
    started = perf_counter()
    serialized = serialize_palette_state(application, notice)
    serialized_at = perf_counter()
    palette.sendInfoToHTML("state", serialized)
    sent_at = perf_counter()
    if _runtime.developer_mode_enabled and sent_at - started >= 0.25:
        _log_to_fusion(
            "Harness Builder slow palette state: "
            f"serializeMs={(serialized_at - started) * 1000:.0f} "
            f"sendMs={(sent_at - serialized_at) * 1000:.0f} "
            f"bytes={len(serialized)}"
        )


def _harness_render_state(
    application: adsk.core.Application,
    gateway: object,
    definition: HarnessDefinition,
) -> tuple[bool, bool, bool]:
    """
    Discover mutually exclusive preview, solid, and finalized output for one harness.

    A solid wins during the brief interval before post-command preview cleanup,
    preserving the Render menu's NAND contract throughout palette refreshes.
    """
    active_product = getattr(application, "activeProduct", None)
    design_type = getattr(adsk.fusion, "Design", None)
    component_reader = getattr(gateway, "harness_component", None)
    if active_product is None or design_type is None or component_reader is None:
        return False, False, False
    design = cast(Any, design_type).cast(active_product)
    if design is None:
        return False, False, False
    read_harness_component = cast(
        Callable[[UUID], object],
        component_reader,
    )
    harness_component = read_harness_component(definition.harness_id)
    occurrences = generated_cable_group_occurrences(harness_component)
    has_finalized = bool(occurrences) and all(
        generated_cable_group_output_mode(occurrence) == FINALIZED_OUTPUT_MODE
        for occurrence in occurrences
    )
    has_solids = bool(occurrences) and not has_finalized
    has_preview = not occurrences and has_route_preview_for_harness(design, definition)
    return has_preview, has_solids, has_finalized


def _palette_theme_payload(application: adsk.core.Application) -> dict[str, str]:
    """
    Resolve Fusion's configured and currently active UI themes for the palette.

    Older Fusion builds without theme access fall back to the light palette.
    Device mode remains explicit so the HTML webview can react immediately to
    operating-system theme rollovers during an open Fusion session.
    """
    preferences = getattr(application, "preferences", None)
    general_preferences = getattr(preferences, "generalPreferences", None)
    configured_theme = getattr(general_preferences, "userInterfaceTheme", None)
    active_theme = getattr(
        general_preferences,
        "activeUserInterfaceTheme",
        configured_theme,
    )
    themes = getattr(adsk.core, "UserInterfaceThemes", None)
    device_theme = getattr(themes, "DeviceUserInterfaceTheme", None)
    dark_themes = {
        getattr(themes, "DarkBlueUserInterfaceTheme", None),
        getattr(themes, "DarkGrayUserInterfaceTheme", None),
    }
    dark_themes.discard(None)
    return {
        "mode": "device"
        if device_theme is not None and configured_theme == device_theme
        else "fixed",
        "active": "dark" if active_theme in dark_themes else "light",
    }


def _length_units_payload(design: Optional[adsk.fusion.Design]) -> dict[str, object]:
    """
    Describe the active design length unit as a millimeter conversion scale.

    Millimeters remain the persistence boundary when Fusion has no active
    design or does not expose a usable length-unit conversion.
    """
    fallback: dict[str, object] = {"symbol": "mm", "millimetersPerUnit": 1.0}
    if design is None:
        return fallback
    units_manager = getattr(design, "unitsManager", None)
    symbol = getattr(units_manager, "defaultLengthUnits", None)
    convert = getattr(units_manager, "convert", None)
    if not isinstance(symbol, str) or not symbol or not callable(convert):
        return fallback
    convert_units = cast(Callable[[float, str, str], float], convert)
    try:
        millimeters_per_unit = float(convert_units(1.0, symbol, "mm"))
    except (RuntimeError, TypeError, ValueError):
        return fallback
    if not math.isfinite(millimeters_per_unit) or millimeters_per_unit <= 0.0:
        return fallback
    return {"symbol": symbol, "millimetersPerUnit": millimeters_per_unit}


def serialize_palette_state(
    application: adsk.core.Application,
    notice: str = "",
) -> str:
    """
    Serialize discovered harness summaries for the palette boundary.
    """
    started = perf_counter()
    gateway = _create_harness_gateway(application)
    results = load_harnesses(gateway)
    has_contacts = any(
        result.definition is not None
        and any(interface.contacts for interface in result.definition.interfaces)
        for result in results
    )
    contact_revision = _runtime.contact_cache_revision(application) if has_contacts else 0
    catalog = load_cable_material_catalog()
    design_type = getattr(adsk.fusion, "Design", None)
    design = (
        cast(Any, design_type).cast(getattr(application, "activeProduct", None))
        if design_type is not None
        else None
    )
    length_units = _length_units_payload(design)
    lookup = PaletteEntityLookup(design, gateway, measure_lookups=_runtime.developer_mode_enabled)
    prepared_at = perf_counter()
    route_seconds = 0.0
    diameter_seconds = 0.0
    connection_seconds = 0.0
    render_seconds = 0.0
    member_links_seconds = 0.0
    payload_seconds = 0.0
    harnesses: list[dict[str, object]] = []
    for result in results:
        definition = result.definition
        if definition is None:
            deletion_token = _register_damaged_harness(result)
            harnesses.append(
                {
                    "componentName": result.component_name,
                    "deletionToken": deletion_token,
                    "error": result.error,
                    "status": "damaged",
                }
            )
            continue
        phase_started = perf_counter()
        cable_groups, cable_group_route_error = _cable_group_payloads(definition, design)
        route_seconds += perf_counter() - phase_started
        phase_started = perf_counter()
        resolved_attachment_diameters = {
            attachment.attachment_id: definition.cable_end_attachment_diameter(
                group, connection.connection_id, attachment.attachment_id
            )
            for group in definition.cable_groups
            for connection in definition.connections
            if connection.connection_id in group.connection_ids
            for attachment in connection.attachments
        }
        diameter_seconds += perf_counter() - phase_started
        phase_started = perf_counter()
        connected_interface_connections = _connected_interface_connections(
            definition, design, lookup
        )
        connection_seconds += perf_counter() - phase_started
        phase_started = perf_counter()
        has_route_preview, has_generated_solids, has_finalized_geometry = _harness_render_state(
            application,
            gateway,
            definition,
        )
        render_seconds += perf_counter() - phase_started
        phase_started = perf_counter()
        member_links = {
            connection.connection_id: tuple(
                lookup.is_resolvable(token) for token in connection.member_tokens
            )
            for connection in definition.connections
        }
        end_shapes = {end.connection_id: end.shape for end in definition.standalone_ends}
        member_links_seconds += perf_counter() - phase_started
        phase_started = perf_counter()
        harnesses.append(
            {
                "componentName": result.component_name,
                "definitionName": definition.name,
                "harnessId": str(definition.harness_id),
                "schemaVersion": definition.schema_version,
                "lengthUnits": length_units,
                "routingMode": _ROUTING_MODE_LABELS[definition.routing_mode],
                "gateDefaults": asdict(definition.gate_defaults),
                "endDefaults": asdict(definition.end_defaults),
                "minimumClearanceMm": definition.minimum_clearance_mm,
                "autoTransitionPreset": definition.auto_transition_preset.value,
                "hasRoutePreview": has_route_preview,
                "hasGeneratedSolids": has_generated_solids,
                "hasFinalizedGeometry": has_finalized_geometry,
                "materialDefaults": _material_settings_payload(definition.material_defaults),
                "metadata": _metadata_payload(definition.metadata),
                "connections": [
                    {
                        "interpolation": asdict(connection.interpolation),
                        "connectionId": str(connection.connection_id),
                        "name": connection.name,
                        "metadata": _metadata_payload(connection.metadata),
                        "attachment": (
                            _attachment_payload(
                                design,
                                lookup,
                                connection.attachment,
                                resolved_attachment_diameters.get(
                                    connection.attachment.attachment_id
                                ),
                            )
                            if connection.attachment is not None
                            else None
                        ),
                        "attachments": [
                            _attachment_payload(
                                design,
                                lookup,
                                attachment,
                                resolved_attachment_diameters.get(attachment.attachment_id),
                            )
                            for attachment in connection.attachments
                        ],
                        "hasLinkedGeometry": all(member_links[connection.connection_id]),
                        "members": [
                            {
                                "index": index,
                                "memberId": str(connection.member_identities[index]),
                                "interpolation": asdict(connection.member_settings[index]),
                                "usesDefaults": not connection.member_interpolations
                                or connection.member_interpolations[index] is None,
                                **(
                                    {
                                        "alignment": connection.resolved_member_alignments[
                                            index
                                        ].value
                                    }
                                    if end_shapes.get(connection.connection_id)
                                    is CableEndShape.OPEN
                                    else {}
                                ),
                                "hasLinkedGeometry": member_links[connection.connection_id][index],
                            }
                            for index in range(len(connection.member_tokens))
                        ],
                    }
                    for connection in definition.connections
                ],
                "controls": [
                    {
                        "interpolation": asdict(control.interpolation),
                        "usesDefaults": not control.interpolation_is_override,
                        "controlId": str(control.control_id),
                        "name": control.name,
                        "kind": control.kind.value,
                        "hasLinkedGeometry": (
                            control.refine_geometry is not None
                            if control.kind.value == "refine"
                            else lookup.is_resolvable(control.entity_token)
                        ),
                        "displayRadiusMm": (
                            control.refine_geometry.display_radius_mm
                            if control.refine_geometry is not None
                            else None
                        ),
                    }
                    for control in definition.controls
                ],
                "pathways": [
                    {
                        "pathwayId": str(pathway.pathway_id),
                        "name": pathway.name,
                        "startName": pathway.start_name,
                        "endName": pathway.end_name,
                        "routingMode": _ROUTING_MODE_LABELS[pathway.routing_mode],
                        "orderedControlIds": [
                            str(control_id) for control_id in pathway.ordered_control_ids
                        ],
                        "metadata": _metadata_payload(pathway.metadata),
                        "startMetadata": _metadata_payload(pathway.start_metadata),
                        "endMetadata": _metadata_payload(pathway.end_metadata),
                    }
                    for pathway in definition.pathways
                ],
                "junctions": [
                    {
                        "junctionId": str(junction.junction_id),
                        "name": junction.name,
                        "controlId": str(junction.control_id),
                        "pathwayRelationships": [
                            {
                                "pathwayId": str(relationship.pathway_id),
                                "endpoint": relationship.endpoint.value,
                            }
                            for relationship in junction.pathway_relationships
                        ],
                        "metadata": _metadata_payload(junction.metadata),
                    }
                    for junction in definition.junctions
                ],
                "interfaces": [
                    {
                        "interfaceId": str(interface.interface_id),
                        "name": interface.name,
                        "connectedConnectionIds": [
                            str(connection_id)
                            for connection_id in connected_interface_connections[
                                interface.interface_id
                            ]
                        ],
                        "targets": [
                            {
                                "kind": target.kind.value,
                                "hasLinkedGeometry": design is not None
                                and resolve_interface_target(
                                    design, target, find_entities=lookup.find_entities
                                )
                                is not None,
                            }
                            for target in interface.targets
                        ],
                        "contacts": [
                            {
                                "contactId": str(contact.contact_id),
                                "kind": contact.kind.value,
                                "name": contact.name or contact.kind.value,
                                "assignedName": contact.name,
                                "pin": contact.pin,
                                "orientationName": contact.orientation_name,
                                "geometryRevision": contact_revision,
                            }
                            for contact in interface.contacts
                        ],
                    }
                    for interface in definition.interfaces
                ],
                "standaloneEnds": [
                    {
                        "connectionId": str(end.connection_id),
                        "pathwayId": str(end.pathway_id),
                        "endpoint": end.endpoint.value,
                        "shape": end.shape.value,
                        "orderedControlIds": [
                            str(control_id) for control_id in end.ordered_control_ids
                        ],
                    }
                    for end in definition.standalone_ends
                ],
                "cableGroups": cable_groups,
                "attachmentAssociations": [
                    {
                        "associationId": str(association.association_id),
                        "attachmentIds": [
                            str(attachment_id) for attachment_id in association.attachment_ids
                        ],
                    }
                    for association in definition.attachment_associations
                ],
                "cableGroupRouteError": cable_group_route_error,
                "status": "draft" if result.validation_messages else "valid",
                "validationMessages": result.validation_messages,
            }
        )
        payload_seconds += perf_counter() - phase_started
    payload = {
        "catalog": {
            "insulationMaterials": list(catalog.insulation_materials),
            "conductorMaterials": list(catalog.conductor_materials),
            "colors": [_color_payload(color) for color in catalog.colors],
            "stripePatterns": [pattern.value for pattern in catalog.stripe_patterns],
        },
        "harnesses": harnesses,
        "contactDocumentScope": _contact_palette_document_scope(application, design),
        "contactCacheScope": _contact_palette_cache_scope(application, design),
        "notice": notice or _runtime.last_command_error,
        "ok": True,
        "theme": _palette_theme_payload(application),
    }
    payload_built_at = perf_counter()
    serialized = json.dumps(payload, sort_keys=True)
    finished = perf_counter()
    if _runtime.developer_mode_enabled and finished - started >= 0.25:
        measured_seconds = (
            route_seconds
            + diameter_seconds
            + connection_seconds
            + render_seconds
            + member_links_seconds
            + payload_seconds
        )
        other_seconds = payload_built_at - prepared_at - measured_seconds
        _log_to_fusion(
            "Harness Builder slow state construction: "
            f"prepareMs={(prepared_at - started) * 1000:.0f} "
            f"routesMs={route_seconds * 1000:.0f} "
            f"diametersMs={diameter_seconds * 1000:.0f} "
            f"connectionsMs={connection_seconds * 1000:.0f} "
            f"renderStateMs={render_seconds * 1000:.0f} "
            f"memberLinksMs={member_links_seconds * 1000:.0f} "
            f"membersMs={payload_seconds * 1000:.0f} "
            f"tokenQueries={lookup.query_count} "
            f"emptyTokens={lookup.empty_count} "
            f"tokenCacheHits={lookup.cache_hit_count} "
            f"persistentHits={lookup.persistent_hit_count} "
            f"tokenQueryMs={lookup.query_seconds * 1000:.0f} "
            f"otherMs={other_seconds * 1000:.0f} "
            f"jsonMs={(finished - payload_built_at) * 1000:.0f}"
        )
    return serialized


def _cable_group_payloads(
    definition: HarnessDefinition,
    design: Optional[adsk.fusion.Design] = None,
) -> tuple[list[dict[str, object]], Optional[str]]:
    """
    Project persistent cable groups and their planned route legs for the palette.

    A route-planning failure must not make the harness editor unavailable. The
    palette can still show group membership and explain why its graphic is absent.
    """
    try:
        planned_legs = plan_cable_group_routes(definition)
        route_error = None
    except ValueError as error:
        planned_legs = ()
        route_error = str(error)
    legs_by_group: dict[UUID, list[CableGroupRouteLeg]] = {}
    for leg in planned_legs:
        legs_by_group.setdefault(leg.cable_group_id, []).append(leg)
    payloads = [
        {
            "cableGroupId": str(group.cable_group_id),
            "name": group.name,
            "groupType": group.group_type.value,
            **(
                {
                    "ribbonLines": group.ribbon_lines,
                    "ribbonGeometry": group.ribbon_geometry.value,
                    "ribbonBodyType": group.ribbon_body_type.value,
                    "interfaceBehavior": group.interface_behavior.value,
                    "traceWidthMm": group.trace_width_mm,
                    "traceSpacingMm": group.trace_spacing_mm,
                    "ribbonLineColors": [
                        None if color is None else _color_payload(color)
                        for color in group.ribbon_line_colors
                    ],
                }
                if group.group_type is CableGroupType.RIBBON
                else {}
            ),
            "connectionIds": [str(connection_id) for connection_id in group.connection_ids],
            "diameterMm": group.diameter_mm,
            "conductorDiameterMm": group.conductor_diameter_mm,
            "resolvedConductorDiameterMm": group.resolved_conductor_diameter_mm,
            "materials": _material_settings_payload(definition.cable_group_materials(group)),
            "materialOverrides": _material_overrides_payload(group.material_overrides),
            "metadata": _metadata_payload(definition.cable_group_metadata(group)),
            "metadataOverrides": _metadata_payload(group.metadata_overrides),
            "routeLegs": [
                {
                    "routeId": str(leg.route_id),
                    "label": leg.label,
                    "startConnectionId": (
                        str(leg.start_connection_id)
                        if leg.start_connection_id is not None
                        else None
                    ),
                    "endConnectionId": (
                        str(leg.end_connection_id) if leg.end_connection_id is not None else None
                    ),
                    "controlSteps": [
                        {"controlId": str(step.control_id), "reversed": step.reversed}
                        for step in leg.control_steps
                    ],
                    "pathwayIds": [str(pathway_id) for pathway_id in leg.pathway_ids],
                }
                for leg in legs_by_group.get(group.cable_group_id, ())
            ],
        }
        for group in definition.cable_groups
    ]
    if design is not None:
        for group, payload in zip(definition.cable_groups, payloads):
            if group.group_type is not CableGroupType.RIBBON or group.ribbon_lines < 2:
                continue
            try:
                pitch, widths = ffc_contact_geometry(design, definition, group)
                dimensions = resolve_ffc_dimensions(pitch, widths, None, None)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            payload["ffcPitchMm"] = pitch
            payload["ffcAutoTraceWidthMm"] = dimensions.trace_width_mm
    return payloads, route_error


def _register_damaged_harness(result: HarnessLoadResult) -> Optional[str]:
    """
    Retain a refresh-stable token for one damaged component during this add-in session.

    Results without a component handle cannot be registered and return ``None``.
    """
    if result.component_handle is None:
        return None
    for deletion_token, registered in _runtime.damaged_harness_results.items():
        if registered.component_handle is result.component_handle:
            _runtime.damaged_harness_results[deletion_token] = result
            return deletion_token
    deletion_token = str(uuid4())
    _runtime.damaged_harness_results[deletion_token] = result
    return deletion_token


def _delete_damaged_harness(
    application: adsk.core.Application,
    serialized_data: str,
) -> str:
    """
    Delete one exact unreadable harness component selected from the current palette state.
    """
    payload = _read_palette_payload(serialized_data)
    deletion_token = payload.get("deletionToken")
    if not isinstance(deletion_token, str) or not deletion_token:
        raise ValueError("Damaged harness deletion requires a current deletion token.")
    result = _runtime.damaged_harness_results.get(deletion_token)
    if result is None:
        raise ValueError("The damaged harness selection is stale; refresh and try again.")
    gateway = _create_harness_gateway(application)
    delete_damaged_harness(result, gateway)
    del _runtime.damaged_harness_results[deletion_token]
    return f"Deleted damaged harness {result.component_name}."
