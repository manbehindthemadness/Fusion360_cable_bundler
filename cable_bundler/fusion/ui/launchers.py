"""
Fusion UI services for launchers.
"""

from __future__ import annotations

import json
import math
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application.interface_contact_rows import ContactSelectionMode
from .auto_connect_requests import AutoConnectApplyRequest, AutoConnectPickRequest
from .constants import (
    ADD_END_COMMAND_ID,
    ADD_INTERFACE_COMMAND_ID,
    ADD_JUNCTION_COMMAND_ID,
    ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
    ADD_PATHWAY_COMMAND_ID,
    ADD_REFINE_COMMAND_ID,
    APPEND_GATES_COMMAND_ID,
    ATTACH_CABLE_END_COMMAND_ID,
    AUTO_CONNECT_COMMAND_ID,
    COMMAND_ID,
    EDIT_REFINE_COMMAND_ID,
    PALETTE_ID,
    SEGMENT_PATHWAY_COMMAND_ID,
    SELECT_INTERFACE_CONTACTS_COMMAND_ID,
    SELECT_SOURCE_INTERFACE_COMMAND_ID,
)
from .payloads import (
    _read_palette_payload,
    _read_payload_uuid,
)
from .runtime import runtime as _runtime


def _open_palette_edit(application: adsk.core.Application, action: str, data: str) -> None:
    """
    Queue one palette request for a named, dialog-free Fusion command.
    """
    definition = application.userInterface.commandDefinitions.itemById(f"{COMMAND_ID}_{action}")
    if definition is None:
        raise RuntimeError("The harness edit command is unavailable; restart the add-in.")
    try:
        _runtime.pending_palette_edit.prepare((action, data, application.activeDocument))
    except RuntimeError as error:
        raise RuntimeError("Another harness edit is starting; retry after it completes.") from error
    try:
        if not definition.execute():
            raise RuntimeError("Fusion could not execute the harness edit command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_palette_edit.clear()
        raise


def _open_add_pathway_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open the native pathway command for the harness selected in the palette.

    Raises:
        RuntimeError: If Fusion cannot open the command.
        ValueError: If the palette payload is malformed.
    """

    payload = json.loads(serialized_data)
    if not isinstance(payload, dict):
        raise ValueError("Add Pathway request must be a JSON object.")
    raw_harness_id = payload.get("harnessId")
    if not isinstance(raw_harness_id, str):
        raise ValueError("Add Pathway request is missing a harness identity.")
    harness_id = UUID(raw_harness_id)
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_PATHWAY_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Pathway command is unavailable.")

    _runtime.pending_pathway.prepare(harness_id)
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Pathway command.")
    except Exception:
        _runtime.pending_pathway.clear()
        raise


def _open_add_junction_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open the native isolated-junction command for the palette-selected harness.

    Raises:
        RuntimeError: If Fusion cannot open the command.
        ValueError: If the palette payload is malformed.
    """

    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_JUNCTION_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Junction command is unavailable.")
    _runtime.pending_junction.prepare(harness_id)
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Junction command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_junction.clear()
        raise


def _open_add_interface_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open the native Interface picker for the palette-selected harness.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_INTERFACE_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Interface command is unavailable.")
    _runtime.pending_interface.prepare(harness_id)
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Interface command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_interface.clear()
        raise


def _open_select_interface_contacts_command(
    application: adsk.core.Application, serialized_data: str
) -> None:
    """
    Open the native multi-target picker for one persisted Interface.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
    mode = ContactSelectionMode(payload.get("mode", "manual"))
    definition = application.userInterface.commandDefinitions.itemById(
        SELECT_INTERFACE_CONTACTS_COMMAND_ID
    )
    if definition is None:
        raise RuntimeError("Fusion Select Interface Contacts command is unavailable.")
    _runtime.pending_interface_contacts.prepare((harness_id, interface_id, mode))
    try:
        if not definition.execute():
            raise RuntimeError("Fusion did not open the Interface contact picker.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_interface_contacts.clear()
        raise


def _open_select_source_interface_command(
    application: adsk.core.Application, serialized_data: str
) -> None:
    """
    Open a picker limited to another saved Interface in the same harness.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
    raw_ids = payload.get("contactIds")
    copy_values = payload.get("copyValues", True)
    copy_pins = payload.get("copyPins", False)
    if (
        not isinstance(raw_ids, list)
        or len(raw_ids) > 1024
        or not all(isinstance(item, str) for item in raw_ids)
        or not isinstance(copy_values, bool)
        or not isinstance(copy_pins, bool)
        or not (copy_values or copy_pins)
    ):
        raise ValueError("Geo Import requires contact identities and Values or Pins.")
    contact_ids = tuple(UUID(item) for item in raw_ids)
    definition = application.userInterface.commandDefinitions.itemById(
        SELECT_SOURCE_INTERFACE_COMMAND_ID
    )
    if definition is None:
        raise RuntimeError("Fusion Select Source Interface command is unavailable.")
    _runtime.pending_source_interface.prepare(
        (harness_id, interface_id, contact_ids, copy_values, copy_pins, application.activeDocument)
    )
    try:
        if not definition.execute():
            raise RuntimeError("Fusion did not open the source Interface picker.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_source_interface.clear()
        raise


def _open_auto_connect_picker(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open one grouped-ending picker without connecting any contacts.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    side = payload.get("side")
    request_id = payload.get("requestId")
    if (
        side not in ("source", "target")
        or not isinstance(request_id, str)
        or not (1 <= len(request_id) <= 100)
    ):
        raise ValueError("Auto Connect picker needs a side and request identity.")
    try:
        definition = application.userInterface.commandDefinitions.itemById(AUTO_CONNECT_COMMAND_ID)
        if definition is None:
            raise RuntimeError("Fusion Auto Connect command is unavailable; restart the add-in.")
        _runtime.pending_auto_connect.prepare(
            AutoConnectPickRequest(harness_id, side, request_id, application.activeDocument)
        )
        if not definition.execute():
            raise RuntimeError("Fusion did not open the Auto Connect picker.")
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        _runtime.pending_auto_connect.clear()
        palette = application.userInterface.palettes.itemById(PALETTE_ID)
        if palette is not None:
            palette.sendInfoToHTML(
                "auto_connect_ending_selected",
                json.dumps(
                    {
                        "harnessId": str(harness_id),
                        "side": side,
                        "requestId": request_id,
                        "cancelled": True,
                        "error": str(error),
                    }
                ),
            )
        raise


def _open_auto_connect_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Apply previously selected cable endings to the chosen Interface contacts.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
    raw_ids = payload.get("contactIds")
    include_pins = payload.get("includePins")
    include_values = payload.get("includeValues")
    diameter = payload.get("diameterMm")
    if (
        not isinstance(raw_ids, list)
        or not raw_ids
        or len(raw_ids) > 1024
        or any(not isinstance(item, str) for item in raw_ids)
        or not isinstance(include_pins, bool)
        or not isinstance(include_values, bool)
        or diameter is not None
        and (
            isinstance(diameter, bool)
            or not isinstance(diameter, (int, float))
            or not math.isfinite(diameter)
            or diameter <= 0
        )
    ):
        raise ValueError("Auto Connect needs contacts, options, and a positive optional diameter.")
    contact_ids = tuple(UUID(item) for item in raw_ids)
    connection_id = _read_payload_uuid(payload, "connectionId", "cable ending")
    parent_attachment_id = (
        _read_payload_uuid(payload, "parentAttachmentId", "parent attachment")
        if payload.get("parentAttachmentId") is not None
        else None
    )
    raw_target_ids = payload.get("targetContactIds", [])
    target_interface_raw = payload.get("targetInterfaceId")
    target_include_pins = payload.get("targetIncludePins", True)
    target_include_values = payload.get("targetIncludeValues", True)
    target_diameter = payload.get("targetDiameterMm")
    if (
        not isinstance(raw_target_ids, list)
        or len(raw_target_ids) > 1024
        or any(not isinstance(item, str) for item in raw_target_ids)
        or (target_interface_raw is None) != (len(raw_target_ids) == 0)
        or not isinstance(target_include_pins, bool)
        or not isinstance(target_include_values, bool)
        or target_diameter is not None
        and (
            isinstance(target_diameter, bool)
            or not isinstance(target_diameter, (int, float))
            or not math.isfinite(target_diameter)
            or target_diameter <= 0
        )
    ):
        raise ValueError(
            "Auto Connect target needs contacts, options, and a positive optional diameter."
        )
    target_interface_id = (
        _read_payload_uuid(payload, "targetInterfaceId", "target Interface")
        if target_interface_raw is not None
        else None
    )
    target_contact_ids = tuple(UUID(item) for item in raw_target_ids)
    target_connection_raw = payload.get("targetConnectionId")
    if (target_interface_id is None) != (target_connection_raw is None):
        raise ValueError("A target Interface needs its selected cable ending.")
    target_connection_id = (
        _read_payload_uuid(payload, "targetConnectionId", "target cable ending")
        if target_connection_raw is not None
        else None
    )
    target_parent_attachment_id = (
        _read_payload_uuid(payload, "targetParentAttachmentId", "target parent attachment")
        if payload.get("targetParentAttachmentId") is not None
        else None
    )
    if target_connection_id is None and target_parent_attachment_id is not None:
        raise ValueError("A target parent needs a selected cable ending.")
    definition = application.userInterface.commandDefinitions.itemById(AUTO_CONNECT_COMMAND_ID)
    if definition is None:
        raise RuntimeError("Fusion Auto Connect command is unavailable; restart the add-in.")
    _runtime.pending_auto_connect.prepare(
        AutoConnectApplyRequest(
            harness_id,
            interface_id,
            contact_ids,
            connection_id,
            parent_attachment_id,
            include_pins,
            include_values,
            diameter,
            application.activeDocument,
            target_interface_id,
            target_contact_ids,
            target_connection_id,
            target_parent_attachment_id,
            target_include_pins,
            target_include_values,
            target_diameter,
        )
    )
    try:
        if not definition.execute():
            raise RuntimeError("Fusion did not execute Auto Connect.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_auto_connect.clear()
        raise


def _open_add_junction_relationship_command(
    application: adsk.core.Application,
    serialized_data: str,
) -> None:
    """
    Open the native pathway-end selector for one palette-selected junction.
    """

    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    junction_id = _read_payload_uuid(payload, "junctionId", "junction")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_JUNCTION_RELATIONSHIP_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Junction Relationship command is unavailable.")
    _runtime.pending_junction_relationship.prepare((harness_id, junction_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the junction relationship command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_junction_relationship.clear()
        raise


def _open_append_gates_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open native profile selection for the palette-selected pathway.
    """

    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    pathway_id = _read_payload_uuid(payload, "pathwayId", "pathway")
    command_definition = application.userInterface.commandDefinitions.itemById(
        APPEND_GATES_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Gates command is unavailable.")
    _runtime.pending_append_gates.prepare(("pathway", harness_id, pathway_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Gates command.")
    except Exception:
        _runtime.pending_append_gates.clear()
        raise


def _open_refine_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open interactive refine placement for the palette-selected pathway.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    pathway_id = _read_payload_uuid(payload, "pathwayId", "pathway")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_REFINE_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Refine Point command is unavailable.")
    _runtime.pending_refine.prepare(("pathway", harness_id, pathway_id, None))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Refine Point command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_refine.clear()
        raise


def _open_append_end_guides_command(
    application: adsk.core.Application,
    serialized_data: str,
) -> None:
    """
    Open native profile selection for one palette-selected end.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    connection_id = _read_payload_uuid(payload, "connectionId", "standalone end")
    command_definition = application.userInterface.commandDefinitions.itemById(
        APPEND_GATES_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Guides command is unavailable.")
    _runtime.pending_append_gates.prepare(("end", harness_id, connection_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Guides command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_append_gates.clear()
        raise


def _open_end_refine_command(
    application: adsk.core.Application,
    serialized_data: str,
) -> None:
    """
    Open interactive refine placement for one palette-selected end.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    connection_id = _read_payload_uuid(payload, "connectionId", "standalone end")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_REFINE_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Refine Point command is unavailable.")
    _runtime.pending_refine.prepare(("end", harness_id, connection_id, None))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Refine Point command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_refine.clear()
        raise


def _open_connection_refine_command(
    application: adsk.core.Application,
    serialized_data: str,
) -> None:
    """
    Open interactive refine placement for one external connection span.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    connection_id = _read_payload_uuid(payload, "connectionId", "cable end")
    attachment_id = _read_payload_uuid(payload, "attachmentId", "connection node")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ADD_REFINE_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Add Refine Point command is unavailable.")
    _runtime.pending_refine.prepare(("connection", harness_id, connection_id, attachment_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add Refine Point command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_refine.clear()
        raise


def _open_segment_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open interactive segmentation for the palette-selected pathway.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    pathway_id = _read_payload_uuid(payload, "pathwayId", "pathway")
    command_definition = application.userInterface.commandDefinitions.itemById(
        SEGMENT_PATHWAY_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Segment Pathway command is unavailable.")
    _runtime.pending_segment.prepare((harness_id, pathway_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Segment Pathway command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_segment.clear()
        raise


def _open_refine_edit_command(
    application: adsk.core.Application,
    harness_id: UUID,
    control_id: UUID,
) -> None:
    """
    Open translation, rotation, and radius controls for one saved refine.
    """
    command_definition = application.userInterface.commandDefinitions.itemById(
        EDIT_REFINE_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Edit Refine Point command is unavailable.")
    _runtime.pending_refine_edit.prepare((harness_id, control_id))
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Edit Refine Point command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_refine_edit.clear()
        raise


def _open_add_end_command(application: adsk.core.Application, serialized_data: str) -> None:
    """
    Open native standalone-end selection for the palette-selected harness.
    """

    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    command_definition = application.userInterface.commandDefinitions.itemById(ADD_END_COMMAND_ID)
    if command_definition is None:
        raise RuntimeError("Fusion Add End command is unavailable.")
    _runtime.pending_standalone_end.prepare(harness_id)
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Add End command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_standalone_end.clear()
        raise


def _open_attach_cable_end_command(
    application: adsk.core.Application,
    serialized_data: str,
) -> None:
    """
    Open native target selection for one palette-selected cable end.
    """
    payload = _read_palette_payload(serialized_data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    connection_id = _read_payload_uuid(payload, "connectionId", "cable end")
    attachment_id = _read_payload_uuid(payload, "attachmentId", "connection node")
    relationship = payload.get("relationship", "main")
    if relationship not in {"main", "shielding"}:
        raise ValueError("Connection relationship must be main or shielding.")
    command_definition = application.userInterface.commandDefinitions.itemById(
        ATTACH_CABLE_END_COMMAND_ID
    )
    if command_definition is None:
        raise RuntimeError("Fusion Connect Cable End command is unavailable.")
    _runtime.pending_cable_end_attachment.prepare(
        (harness_id, connection_id, attachment_id, relationship)
    )
    try:
        if not command_definition.execute():
            raise RuntimeError("Fusion did not open the Connect Cable End command.")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _runtime.pending_cable_end_attachment.clear()
        raise
