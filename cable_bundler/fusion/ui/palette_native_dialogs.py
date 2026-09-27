"""
Native command actions launched from the persistent palette.
"""

from __future__ import annotations

from typing import Callable

# noinspection PyUnresolvedReferences
import adsk.core

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
    CREATE_COMMAND_ID,
    EDIT_REFINE_COMMAND_ID,
    SEGMENT_PATHWAY_COMMAND_ID,
    SELECT_INTERFACE_CONTACTS_COMMAND_ID,
    SELECT_SOURCE_INTERFACE_COMMAND_ID,
)
from .launchers import (
    _open_add_end_command,
    _open_add_interface_command,
    _open_add_junction_command,
    _open_add_junction_relationship_command,
    _open_add_pathway_command,
    _open_append_end_guides_command,
    _open_append_gates_command,
    _open_attach_cable_end_command,
    _open_connection_refine_command,
    _open_end_refine_command,
    _open_palette_edit,
    _open_refine_command,
    _open_refine_edit_command,
    _open_segment_command,
    _open_select_interface_contacts_command,
    _open_select_source_interface_command,
)
from .payloads import _read_palette_payload, _read_payload_uuid


def _launch_create_harness(application: adsk.core.Application, _data: str) -> None:
    """
    Open the native harness-creation command from the palette.
    """
    definition = application.userInterface.commandDefinitions.itemById(CREATE_COMMAND_ID)
    if definition is None or not definition.execute():
        raise RuntimeError("Fusion did not open the Create Harness command.")


def _launch_refine_edit(application: adsk.core.Application, data: str) -> None:
    """
    Parse stable identities before opening the native refine editor.
    """
    payload = _read_palette_payload(data)
    _open_refine_edit_command(
        application,
        _read_payload_uuid(payload, "harnessId", "harness"),
        _read_payload_uuid(payload, "controlId", "refine point"),
    )


_NATIVE_DIALOG_ACTIONS: dict[
    str,
    Callable[[adsk.core.Application, str], None],
] = {
    "create_harness": _launch_create_harness,
    "add_pathway": lambda application, data: _open_add_pathway_command(application, data),
    "add_junction": lambda application, data: _open_add_junction_command(application, data),
    "add_interface": lambda application, data: _open_add_interface_command(application, data),
    "select_interface_contacts": lambda application, data: _open_select_interface_contacts_command(
        application, data
    ),
    "copy_projected_interface_contacts": lambda application, data: (
        _open_select_source_interface_command(application, data)
    ),
    "load_brd_interface_contacts": lambda application, data: _open_palette_edit(
        application, "load_brd_interface_contacts", data
    ),
    "add_junction_relationship": lambda application, data: _open_add_junction_relationship_command(
        application, data
    ),
    "add_end": lambda application, data: _open_add_end_command(application, data),
    "connect_cable_end": lambda application, data: _open_attach_cable_end_command(
        application, data
    ),
    "append_pathway_gates": lambda application, data: _open_append_gates_command(application, data),
    "append_end_guides": lambda application, data: _open_append_end_guides_command(
        application, data
    ),
    "add_pathway_refine": lambda application, data: _open_refine_command(application, data),
    "add_end_refine": lambda application, data: _open_end_refine_command(application, data),
    "add_connection_refine": lambda application, data: _open_connection_refine_command(
        application, data
    ),
    "segment_pathway": lambda application, data: _open_segment_command(application, data),
    "edit_pathway_refine": _launch_refine_edit,
}

_NATIVE_DIALOG_COMMAND_IDS = {
    "create_harness": CREATE_COMMAND_ID,
    "add_pathway": ADD_PATHWAY_COMMAND_ID,
    "add_junction": ADD_JUNCTION_COMMAND_ID,
    "add_interface": ADD_INTERFACE_COMMAND_ID,
    "select_interface_contacts": SELECT_INTERFACE_CONTACTS_COMMAND_ID,
    "copy_projected_interface_contacts": SELECT_SOURCE_INTERFACE_COMMAND_ID,
    "load_brd_interface_contacts": f"{COMMAND_ID}_load_brd_interface_contacts",
    "add_junction_relationship": ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
    "add_end": ADD_END_COMMAND_ID,
    "connect_cable_end": ATTACH_CABLE_END_COMMAND_ID,
    "append_pathway_gates": APPEND_GATES_COMMAND_ID,
    "append_end_guides": APPEND_GATES_COMMAND_ID,
    "add_pathway_refine": ADD_REFINE_COMMAND_ID,
    "add_end_refine": ADD_REFINE_COMMAND_ID,
    "add_connection_refine": ADD_REFINE_COMMAND_ID,
    "segment_pathway": SEGMENT_PATHWAY_COMMAND_ID,
    "edit_pathway_refine": EDIT_REFINE_COMMAND_ID,
}
