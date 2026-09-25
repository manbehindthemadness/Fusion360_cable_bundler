"""
Fusion UI services for launchers.
"""

from __future__ import annotations

import json
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .constants import (
    ADD_END_COMMAND_ID,
    ADD_INTERFACE_COMMAND_ID,
    ADD_JUNCTION_COMMAND_ID,
    ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
    ADD_PATHWAY_COMMAND_ID,
    ADD_REFINE_COMMAND_ID,
    APPEND_GATES_COMMAND_ID,
    ATTACH_CABLE_END_COMMAND_ID,
    COMMAND_ID,
    EDIT_REFINE_COMMAND_ID,
    SEGMENT_PATHWAY_COMMAND_ID,
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
