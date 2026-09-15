"""
Fusion UI services for viewport.
"""

from __future__ import annotations

import json
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import ControlKind, HarnessDefinition, loads
from .. import clear_route_previews, highlight_route_preview, show_route_previews
from ..refine_graphics import highlight_refine_graphics
from ..route_preview import highlight_route_members, refresh_route_previews
from ..wire_solids import (
    apply_wire_materials,
    clear_wire_solids,
    generate_wire_solids,
    generated_wire_bodies,
)
from .palette_state import (
    _send_palette_state,
)
from .payloads import (
    _read_palette_payload,
    _read_payload_uuid,
)
from .support import (
    _create_harness_gateway,
    _log_to_fusion,
    _require_active_design,
)


def _refresh_active_preview(
    application: adsk.core.Application,
    harness_id: UUID,
    *,
    ensure_visible: bool = False,
) -> str:
    """
    Refresh a harness preview after its edit has been saved.

    Material edits can request a visible preview so their stripe presentation is
    immediate even when Preview Routes was not already active. Preview failures
    are notices, not failures of the persisted edit itself.
    """
    design = _require_active_design(application)
    definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
    if ensure_visible and definition.wire_groups and definition.material_defaults.stripes:
        warnings: tuple[str, ...] = ()
        show_route_previews(design, definition)
    else:
        warnings = refresh_route_previews(design, definition)
    for warning in warnings:
        _log_to_fusion(warning)
    return " ".join(warnings)


def _apply_generated_materials(application: adsk.core.Application, harness_id: UUID) -> str:
    """
    Update existing generated bodies after a material definition is saved.
    """
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    count = apply_wire_materials(
        design,
        gateway.harness_component(harness_id),
        definition,
    )
    return f"Applied materials to {count} generated wire{'s' if count != 1 else ''}."


def _highlight_member(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Emphasize linked profiles, route previews, and generated wire bodies.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    member_type = payload.get("memberType")
    if not isinstance(member_type, str):
        raise ValueError("Highlight request is missing a member type.")
    member_id = _read_payload_uuid(payload, "memberId", "member")
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    wire_ids: tuple[UUID, ...] = ()
    refine_ids: tuple[UUID, ...] = ()
    preview_connection_ids: tuple[UUID, ...] = ()
    preview_pathway_ids: tuple[UUID, ...] = ()
    preview_control_ids: tuple[UUID, ...] = ()
    if member_type == "junction":
        junction = next(
            (item for item in definition.junctions if item.junction_id == member_id),
            None,
        )
        if junction is None:
            raise ValueError("Selected junction no longer exists.")
        control = next(
            (item for item in definition.controls if item.control_id == junction.control_id),
            None,
        )
        if control is None:
            raise ValueError("Selected junction has a missing routing control.")
        refine_ids = (control.control_id,) if control.kind is ControlKind.REFINE else ()
        preview_control_ids = (control.control_id,)
        tokens = (control.entity_token,) if control.entity_token else ()
    elif member_type in {"pathway", "pathway_gates", "pathway_wires"}:
        pathway = next((item for item in definition.pathways if item.pathway_id == member_id), None)
        if pathway is None:
            raise ValueError("Selected pathway no longer exists.")
        wire_ids = (
            tuple(
                wire.wire_id for wire in definition.wires if member_id in wire.ordered_pathway_ids
            )
            if member_type != "pathway_gates"
            else ()
        )
        preview_pathway_ids = (member_id,)
        control_ids = pathway.ordered_control_ids if member_type != "pathway_wires" else ()
        controls = {control.control_id: control for control in definition.controls}
        refine_ids = tuple(
            control_id
            for control_id in control_ids
            if control_id in controls and controls[control_id].kind is ControlKind.REFINE
        )
        tokens = tuple(
            controls[control_id].entity_token
            for control_id in control_ids
            if control_id in controls and controls[control_id].entity_token
        )
    elif member_type == "preview_wire":
        if all(wire.wire_id != member_id for wire in definition.wires):
            raise ValueError("Selected wire no longer exists.")
        wire_ids = (member_id,)
        tokens = ()
    else:
        tokens = _member_entity_tokens(definition, member_type, member_id)
        if member_type == "wire":
            wire_ids = (member_id,)
        elif member_type == "connection":
            preview_connection_ids = (member_id,)
            wire_ids = tuple(
                wire.wire_id
                for wire in definition.wires
                if member_id in {wire.start_connection_id, wire.end_connection_id}
            )
        elif member_type == "control":
            preview_control_ids = (member_id,)
            wire_ids = tuple(
                wire.wire_id for wire in definition.wires if member_id in wire.ordered_control_ids
            )
            control = next(
                (item for item in definition.controls if item.control_id == member_id),
                None,
            )
            if control is not None and control.kind is ControlKind.REFINE:
                refine_ids = (member_id,)
        if member_type == "connection" and "memberIndex" in payload:
            index = payload["memberIndex"]
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 0 <= index < len(tokens)
            ):
                raise ValueError("Selected connection member no longer exists.")
            tokens = (tokens[index],)
    preview_count = highlight_route_members(
        design,
        wire_ids,
        connection_ids=preview_connection_ids,
        pathway_ids=preview_pathway_ids,
        control_ids=preview_control_ids,
    )
    refine_count = highlight_refine_graphics(design, refine_ids)
    profiles: list[adsk.fusion.Profile] = []
    for token in tokens:
        entities = design.findEntityByToken(token)
        profile = adsk.fusion.Profile.cast(entities[0] if entities else None)
        if profile is None:
            raise ValueError("The selected item no longer resolves to a sketch profile.")
        profiles.append(profile)

    selections = application.userInterface.activeSelections
    if not selections.clear():
        raise RuntimeError("Fusion could not clear the prior viewport selection.")
    bodies = generated_wire_bodies(
        design.rootComponent,
        gateway.harness_component(harness_id),
        wire_ids,
    )
    for entity in (*profiles, *bodies):
        if not selections.add(entity):
            selections.clear()
            highlight_route_preview(design, None)
            raise RuntimeError("Fusion could not highlight the selected harness geometry.")
    application.activeViewport.refresh()
    return preview_count + refine_count + len(profiles) + len(bodies)


def _clear_highlight(application: adsk.core.Application) -> None:
    """
    Clear palette-driven viewport selection.
    """
    highlight_route_preview(_require_active_design(application), None)
    highlight_refine_graphics(_require_active_design(application), ())
    if not application.userInterface.activeSelections.clear():
        raise RuntimeError("Fusion could not clear the viewport selection.")
    application.activeViewport.refresh()


def _member_entity_tokens(
    definition: HarnessDefinition,
    member_type: str,
    member_id: UUID,
) -> tuple[str, ...]:
    """
    Resolve a stable palette member identity to persisted entity tokens.

    Controls and connections yield their members; wires yield both endpoint stacks.
    """
    if member_type == "control":
        control = next(
            (item for item in definition.controls if item.control_id == member_id),
            None,
        )
        if control is None:
            raise ValueError("Selected routing gate no longer exists.")
        return (control.entity_token,) if control.entity_token else ()
    connections = {item.connection_id: item for item in definition.connections}
    if member_type == "connection":
        connection = connections.get(member_id)
        if connection is None:
            raise ValueError("Selected connection no longer exists.")
        return connection.member_tokens
    if member_type == "wire":
        wire = next((item for item in definition.wires if item.wire_id == member_id), None)
        if wire is None:
            raise ValueError("Selected wire no longer exists.")
        start_connection = connections.get(wire.start_connection_id)
        end_connection = connections.get(wire.end_connection_id)
        if start_connection is None or end_connection is None:
            raise ValueError("Selected wire has a missing connection reference.")
        tokens = (*start_connection.member_tokens, *end_connection.member_tokens)
        return tokens
    raise ValueError(f"Unsupported highlight member type: {member_type}")


def _preview_routes(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Solve and display route previews for the palette-selected harness.
    """
    payload = json.loads(serialized_data)
    if not isinstance(payload, dict):
        raise ValueError("Preview Routes request must be a JSON object.")
    raw_harness_id = payload.get("harnessId")
    if not isinstance(raw_harness_id, str):
        raise ValueError("Preview Routes request is missing a harness identity.")
    harness_id = UUID(raw_harness_id)
    design = _require_active_design(application)
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    notices: list[str] = []
    routes = show_route_previews(design, definition, notices=notices)
    application.activeViewport.refresh()
    summary = f"Previewing {len(routes)} wire-group route legs."
    _send_palette_state(application, "\n".join((summary, *notices)))
    return len(routes)


def _clear_preview(application: adsk.core.Application) -> int:
    """
    Remove transient route graphics outside a Fusion model-edit transaction.
    """
    _clear_highlight(application)
    count = clear_route_previews(_require_active_design(application))
    application.activeViewport.refresh()
    return count


def _generate_solids(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Generate persistent wire bodies inside the palette command transaction.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    replace_existing = payload.get("replaceExisting", False)
    if not isinstance(replace_existing, bool):
        raise ValueError("Rebuild confirmation must be a boolean.")
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    notices: list[str] = []
    count = generate_wire_solids(
        _require_active_design(application),
        gateway.harness_component(harness_id),
        definition,
        replace_existing,
        notices,
    )
    application.activeViewport.refresh()
    summary = f"Generated {count} wire solids."
    _send_palette_state(application, "\n".join((summary, *notices)))
    return count


def _clear_solids(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Remove marked wire bodies inside the palette command transaction.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    gateway = _create_harness_gateway(application)
    count = clear_wire_solids(gateway.harness_component(harness_id))
    application.activeViewport.refresh()
    _send_palette_state(application, f"Cleared {count} wire solids.")
    return count
