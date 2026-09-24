"""
Fusion UI services for viewport.
"""

from __future__ import annotations

import json
from typing import Any, Union, cast
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import plan_cable_group_routes
from ...domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndTarget,
    ControlKind,
    HarnessDefinition,
    loads,
)
from .. import clear_route_previews, highlight_route_preview, show_route_previews
from ..attachment_targets import resolve_attachment_target
from ..cable_solid_parts.constants import FINALIZED_OUTPUT_MODE, SOLID_OUTPUT_MODE
from ..cable_solids import (
    apply_cable_group_materials,
    clear_cable_solids,
    generate_cable_group_solids,
    generated_attachment_bodies,
    generated_cable_group_bodies,
)
from ..refine_graphics import (
    hide_refine_graphics,
    highlight_refine_graphics,
    reveal_refine_graphics,
)
from ..route_preview import (
    hide_route_previews,
    highlight_route_members,
    refresh_route_previews,
    reveal_route_previews,
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
    if ensure_visible and definition.cable_groups and definition.material_defaults.stripes:
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
    count = apply_cable_group_materials(
        design,
        gateway.harness_component(harness_id),
        definition,
    )
    return f"Applied materials to {count} generated cable group{'s' if count != 1 else ''}."


def _highlight_member(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Emphasize linked profiles, route previews, and generated cable bodies.
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
    refine_ids: tuple[UUID, ...] = ()
    preview_connection_ids: tuple[UUID, ...] = ()
    preview_pathway_ids: tuple[UUID, ...] = ()
    preview_control_ids: tuple[UUID, ...] = ()
    generated_group_ids: tuple[UUID, ...] = ()
    generated_attachment_ids: tuple[UUID, ...] = ()
    attachment_entities: tuple[object, ...] = ()
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
    elif member_type in {"pathway", "pathway_gates"}:
        pathway = next((item for item in definition.pathways if item.pathway_id == member_id), None)
        if pathway is None:
            raise ValueError("Selected pathway no longer exists.")
        preview_pathway_ids = (member_id,)
        generated_group_ids = _cable_group_ids_for_member(definition, "pathway", member_id)
        control_ids = pathway.ordered_control_ids
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
    elif member_type == "cable_group":
        if all(group.cable_group_id != member_id for group in definition.cable_groups):
            raise ValueError("Selected cable group no longer exists.")
        generated_group_ids = (member_id,)
        tokens = ()
    elif member_type == "attachment":
        connection_id = _read_payload_uuid(payload, "connectionId", "cable end")
        connections = {item.connection_id: item for item in definition.connections}
        connection = connections.get(connection_id)
        if connection is None:
            raise ValueError("Selected cable end no longer exists.")
        attachment = next(
            (item for item in connection.attachments if item.attachment_id == member_id),
            None,
        )
        if attachment is None:
            raise ValueError("Selected cable-end connection no longer exists.")
        targets = (attachment, attachment.shielding_target)
        attachment_entities = tuple(
            entity
            for target in targets
            if target is not None
            for entity in (resolve_attachment_target(design, target),)
            if entity is not None
        )
        generated_attachment_ids = (member_id,)
        tokens = ()
    else:
        tokens = _member_entity_tokens(definition, member_type, member_id)
        if member_type == "connection":
            preview_connection_ids = (member_id,)
            generated_group_ids = tuple(
                group.cable_group_id
                for group in definition.cable_groups
                if member_id in group.connection_ids
            )
        elif member_type == "control":
            preview_control_ids = (member_id,)
            generated_group_ids = _cable_group_ids_for_member(definition, "control", member_id)
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
        generated_group_ids,
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
    group_bodies = (
        generated_cable_group_bodies(
            design.rootComponent,
            gateway.harness_component(harness_id),
            generated_group_ids,
        )
        if generated_group_ids
        else ()
    )
    attachment_bodies = tuple(
        body
        for attachment_id in generated_attachment_ids
        for body in generated_attachment_bodies(
            design.rootComponent,
            gateway.harness_component(harness_id),
            attachment_id,
        )
    )
    for entity in (*profiles, *attachment_entities, *attachment_bodies, *group_bodies):
        if not selections.add(entity):
            selections.clear()
            highlight_route_preview(design, None)
            raise RuntimeError("Fusion could not highlight the selected harness geometry.")
    application.activeViewport.refresh()
    return (
        preview_count
        + refine_count
        + len(profiles)
        + len(attachment_entities)
        + len(attachment_bodies)
        + len(group_bodies)
    )


def _cable_group_ids_for_member(
    definition: HarnessDefinition,
    member_type: str,
    member_id: UUID,
) -> tuple[UUID, ...]:
    """
    Resolve groups whose planned legs traverse one pathway or control.
    """
    identities: list[UUID] = []
    for leg in plan_cable_group_routes(definition):
        matches = (
            member_id in leg.pathway_ids
            if member_type == "pathway"
            else any(step.control_id == member_id for step in leg.control_steps)
        )
        if matches and leg.cable_group_id not in identities:
            identities.append(leg.cable_group_id)
    return tuple(identities)


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

    Controls and connections yield their linked profile members.
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
    cleared_solids = clear_cable_solids(gateway.harness_component(harness_id))
    routes = show_route_previews(design, definition, notices=notices)
    _show_render_supports(design, definition)
    application.activeViewport.refresh()
    summary = f"Previewing {len(routes)} cable-group route legs."
    if cleared_solids:
        notices.insert(0, f"Cleared {cleared_solids} cable solids.")
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
    Generate persistent cable-group bodies inside the palette command transaction.
    """
    return _generate_cable_geometry(application, serialized_data, SOLID_OUTPUT_MODE)


def _finalize_solids(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Generate persistent cable bodies with renderable decoration geometry.
    """
    return _generate_cable_geometry(application, serialized_data, FINALIZED_OUTPUT_MODE)


def _set_support_sketch_visibility(
    design: adsk.fusion.Design,
    entity_token: str,
    hidden_sketches: set[str],
    *,
    is_visible: bool,
) -> int:
    """
    Set visibility on the valid sketch owning a persisted support entity token.
    """
    hidden_count = 0
    for entity in design.findEntityByToken(entity_token):
        if not getattr(entity, "isValid", True):
            continue
        sketch = cast(Any, getattr(entity, "parentSketch", None))
        if sketch is None or not getattr(sketch, "isValid", True):
            continue
        sketch_token = getattr(sketch, "entityToken", "")
        if not isinstance(sketch_token, str) or not sketch_token:
            continue
        if sketch_token in hidden_sketches:
            continue
        hidden_sketches.add(sketch_token)
        if sketch.isLightBulbOn == is_visible:
            continue
        sketch.isLightBulbOn = is_visible
        hidden_count += 1
    return hidden_count


def _set_attachment_support_visibility(
    design: adsk.fusion.Design,
    target: Union[CableEndAttachment, CableEndTarget],
    hidden_sketches: set[str],
    *,
    is_visible: bool,
) -> int:
    """
    Set one non-body attachment aid while preserving face-connected bodies.
    """
    target_kind = getattr(target, "target_kind", None)
    if target_kind in {AttachmentTargetKind.PROFILE, AttachmentTargetKind.SKETCH_POINT}:
        return _set_support_sketch_visibility(
            design,
            getattr(target, "entity_token", ""),
            hidden_sketches,
            is_visible=is_visible,
        )
    if target_kind in {AttachmentTargetKind.FACE, AttachmentTargetKind.CIRCULAR_EDGE, None}:
        return 0
    entity = resolve_attachment_target(design, target)
    if entity is None or not hasattr(entity, "isLightBulbOn"):
        return 0
    if entity.isLightBulbOn == is_visible:
        return 0
    entity.isLightBulbOn = is_visible
    return 1


def _set_harness_support_visibility(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
    *,
    is_visible: bool,
) -> int:
    """
    Set routing graphics, source sketches, and non-body attachment aids.
    """
    changed_count = (
        reveal_route_previews(design) + reveal_refine_graphics(design)
        if is_visible
        else hide_route_previews(design) + hide_refine_graphics(design)
    )
    hidden_sketches: set[str] = set()
    support_tokens = (
        *(token for connection in definition.connections for token in connection.member_tokens),
        *(control.entity_token for control in definition.controls if control.entity_token),
    )
    for token in support_tokens:
        changed_count += _set_support_sketch_visibility(
            design,
            token,
            hidden_sketches,
            is_visible=is_visible,
        )
    for connection in definition.connections:
        for attachment in connection.attachments:
            changed_count += _set_attachment_support_visibility(
                design,
                attachment,
                hidden_sketches,
                is_visible=is_visible,
            )
            if attachment.shielding_target is not None:
                changed_count += _set_attachment_support_visibility(
                    design,
                    attachment.shielding_target,
                    hidden_sketches,
                    is_visible=is_visible,
                )
    return changed_count


def _hide_finalized_supports(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
) -> int:
    """
    Hide support geometry after finalized output replaces the working view.
    """
    return _set_harness_support_visibility(design, definition, is_visible=False)


def _show_render_supports(
    design: adsk.fusion.Design,
    definition: HarnessDefinition,
) -> int:
    """
    Restore support geometry for route previews and ordinary solid output.
    """
    return _set_harness_support_visibility(design, definition, is_visible=True)


def _generate_cable_geometry(
    application: adsk.core.Application,
    serialized_data: str,
    output_mode: str,
) -> int:
    """
    Generate one selected persistent cable-output strategy from a palette request.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    replace_existing = payload.get("replaceExisting", False)
    if not isinstance(replace_existing, bool):
        raise ValueError("Rebuild confirmation must be a boolean.")
    gateway = _create_harness_gateway(application)
    definition = loads(gateway.read_harness_definition(harness_id))
    notices: list[str] = []
    design = _require_active_design(application)
    count = generate_cable_group_solids(
        design,
        gateway.harness_component(harness_id),
        definition,
        replace_existing,
        notices,
        output_mode,
    )
    if output_mode == FINALIZED_OUTPUT_MODE:
        _hide_finalized_supports(design, definition)
    else:
        _show_render_supports(design, definition)
    application.activeViewport.refresh()
    summary = (
        f"Finalized {count} cable-group geometries."
        if output_mode == FINALIZED_OUTPUT_MODE
        else f"Generated {count} cable-group solids."
    )
    _send_palette_state(application, "\n".join((summary, *notices)))
    return count


def _clear_solids(application: adsk.core.Application, serialized_data: str) -> int:
    """
    Remove marked cable bodies inside the palette command transaction.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    gateway = _create_harness_gateway(application)
    count = clear_cable_solids(gateway.harness_component(harness_id))
    application.activeViewport.refresh()
    _send_palette_state(application, f"Cleared {count} cable solids.")
    return count
