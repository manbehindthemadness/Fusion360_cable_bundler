"""
Fusion UI services for palette state.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Optional
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
    CableAppearanceReference,
    CableColor,
    CableMaterialOverrides,
    CableMaterialSettings,
    CableStripe,
    HarnessDefinition,
)
from ..cable_solids import generated_cable_group_occurrences
from ..route_preview import has_route_preview_for_harness
from .constants import PALETTE_ID
from .constants import ROUTING_MODE_LABELS as _ROUTING_MODE_LABELS
from .payloads import (
    _read_palette_payload,
)
from .runtime import runtime as _runtime
from .support import (
    _create_harness_gateway,
)


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
    palette.sendInfoToHTML("state", serialize_palette_state(application, notice))


def _harness_render_state(
    application: adsk.core.Application,
    gateway: object,
    definition: HarnessDefinition,
) -> tuple[bool, bool]:
    """
    Discover mutually exclusive preview and solid output for one harness.

    A solid wins during the brief interval before post-command preview cleanup,
    preserving the Render menu's NAND contract throughout palette refreshes.
    """
    active_product = getattr(application, "activeProduct", None)
    design_type = getattr(adsk.fusion, "Design", None)
    component_reader = getattr(gateway, "harness_component", None)
    if active_product is None or design_type is None or component_reader is None:
        return False, False
    design = design_type.cast(active_product)
    if design is None:
        return False, False
    harness_component = component_reader(definition.harness_id)
    has_solids = bool(generated_cable_group_occurrences(harness_component))
    has_preview = not has_solids and has_route_preview_for_harness(design, definition)
    return has_preview, has_solids


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


def serialize_palette_state(
    application: adsk.core.Application,
    notice: str = "",
) -> str:
    """
    Serialize discovered harness summaries for the palette boundary.
    """
    gateway = _create_harness_gateway(application)
    results = load_harnesses(gateway)
    catalog = load_cable_material_catalog()
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
        cable_groups, cable_group_route_error = _cable_group_payloads(definition)
        has_route_preview, has_generated_solids = _harness_render_state(
            application,
            gateway,
            definition,
        )
        harnesses.append(
            {
                "componentName": result.component_name,
                "definitionName": definition.name,
                "harnessId": str(definition.harness_id),
                "schemaVersion": definition.schema_version,
                "routingMode": _ROUTING_MODE_LABELS[definition.routing_mode],
                "gateDefaults": asdict(definition.gate_defaults),
                "endDefaults": asdict(definition.end_defaults),
                "minimumClearanceMm": definition.minimum_clearance_mm,
                "autoTransitionPreset": definition.auto_transition_preset.value,
                "hasRoutePreview": has_route_preview,
                "hasGeneratedSolids": has_generated_solids,
                "materialDefaults": _material_settings_payload(definition.material_defaults),
                "connections": [
                    {
                        "interpolation": asdict(connection.interpolation),
                        "connectionId": str(connection.connection_id),
                        "name": connection.name,
                        "hasLinkedGeometry": all(
                            gateway.is_entity_token_resolvable(token)
                            for token in connection.member_tokens
                        ),
                        "members": [
                            {
                                "index": index,
                                "memberId": str(connection.member_identities[index]),
                                "interpolation": asdict(connection.member_settings[index]),
                                "usesDefaults": not connection.member_interpolations
                                or connection.member_interpolations[index] is None,
                                "hasLinkedGeometry": gateway.is_entity_token_resolvable(token),
                            }
                            for index, token in enumerate(connection.member_tokens)
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
                            else gateway.is_entity_token_resolvable(control.entity_token)
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
                    }
                    for junction in definition.junctions
                ],
                "standaloneEnds": [
                    {
                        "connectionId": str(end.connection_id),
                        "pathwayId": str(end.pathway_id),
                        "endpoint": end.endpoint.value,
                        "orderedControlIds": [
                            str(control_id) for control_id in end.ordered_control_ids
                        ],
                    }
                    for end in definition.standalone_ends
                ],
                "cableGroups": cable_groups,
                "cableGroupRouteError": cable_group_route_error,
                "status": "draft" if result.validation_messages else "valid",
                "validationMessages": result.validation_messages,
            }
        )
    payload = {
        "catalog": {
            "insulationMaterials": list(catalog.insulation_materials),
            "conductorMaterials": list(catalog.conductor_materials),
            "colors": [_color_payload(color) for color in catalog.colors],
            "stripePatterns": [pattern.value for pattern in catalog.stripe_patterns],
        },
        "harnesses": harnesses,
        "notice": notice or _runtime.last_command_error,
        "ok": True,
        "theme": _palette_theme_payload(application),
    }
    return json.dumps(payload, sort_keys=True)


def _cable_group_payloads(
    definition: HarnessDefinition,
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
            "connectionIds": [str(connection_id) for connection_id in group.connection_ids],
            "diameterMm": group.diameter_mm,
            "materials": _material_settings_payload(definition.cable_group_materials(group)),
            "materialOverrides": _material_overrides_payload(group.material_overrides),
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


def _color_payload(color: CableColor) -> dict[str, object]:
    """
    Convert a stored cable color for the HTML palette.
    """
    return {
        "name": color.name,
        "red": color.red,
        "green": color.green,
        "blue": color.blue,
        "hex": color.hex_rgb,
    }


def _appearance_reference_payload(
    appearance: Optional[CableAppearanceReference],
) -> Optional[dict[str, str]]:
    """
    Convert an optional stored Fusion appearance reference for the palette.
    """
    if appearance is None:
        return None
    return {
        "libraryId": appearance.library_id,
        "libraryName": appearance.library_name,
        "appearanceId": appearance.appearance_id,
        "appearanceName": appearance.appearance_name,
    }


def _appearance_libraries_payload(
    application: adsk.core.Application,
) -> list[dict[str, str]]:
    """
    List installed Fusion appearance libraries without loading their contents.
    """
    return _named_collection_payload(application.materialLibraries)


def _library_appearances_payload(
    application: adsk.core.Application,
    library_id: str,
) -> list[dict[str, str]]:
    """
    List appearances from one explicitly selected installed Fusion library.
    """
    library = application.materialLibraries.itemById(library_id)
    if library is None:
        raise ValueError("The selected Fusion appearance library is unavailable.")
    return _named_collection_payload(library.appearances)


def _named_collection_payload(collection: Any) -> list[dict[str, str]]:
    """
    Serialize and sort one Fusion collection whose members expose IDs and names.
    """
    result: list[dict[str, str]] = []
    for index in range(collection.count):
        item = collection.item(index)
        if item is not None:
            result.append({"id": item.id, "name": item.name})
    result.sort(key=lambda entry: entry["name"].casefold())
    return result


def _stripe_payload(stripe: CableStripe) -> dict[str, object]:
    """
    Convert one ordered procedural stripe for the HTML palette.
    """
    return {
        "color": _color_payload(stripe.color),
        "widthMm": stripe.width_mm,
        "pattern": stripe.pattern.value,
        "angleDeg": stripe.angle_deg,
        "repeatMm": stripe.repeat_mm,
    }


def _material_settings_payload(settings: CableMaterialSettings) -> dict[str, object]:
    """
    Convert resolved material settings for editing and display.
    """
    return {
        "insulationMaterial": settings.insulation_material,
        "mainColor": _color_payload(settings.main_color),
        "appearance": _appearance_reference_payload(settings.appearance),
        "stripes": [_stripe_payload(stripe) for stripe in settings.stripes],
        "conductorMaterial": settings.conductor_material,
        "manufacturer": settings.manufacturer,
        "partNumber": settings.part_number,
        "notes": settings.notes,
    }


def _material_overrides_payload(overrides: CableMaterialOverrides) -> dict[str, object]:
    """
    Preserve null inheritance markers at the palette boundary.
    """
    return {
        "insulationMaterial": overrides.insulation_material,
        "mainColor": (
            None if overrides.main_color is None else _color_payload(overrides.main_color)
        ),
        "appearance": _appearance_reference_payload(overrides.appearance),
        "stripes": (
            None
            if overrides.stripes is None
            else [_stripe_payload(stripe) for stripe in overrides.stripes]
        ),
        "conductorMaterial": overrides.conductor_material,
        "manufacturer": overrides.manufacturer,
        "partNumber": overrides.part_number,
        "notes": overrides.notes,
    }
