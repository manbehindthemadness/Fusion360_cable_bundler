"""
Fusion UI services for palette.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from typing import Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from .. import highlight_route_preview
from .commands.refines import reconcile_active_refines
from .constants import (
    COMMAND_NAME,
    CREATE_COMMAND_ID,
    PALETTE_HTML_URL,
    PALETTE_ID,
    PALETTE_INITIAL_HEIGHT,
    PALETTE_INITIAL_WIDTH,
    PALETTE_RESOURCE_FILES,
)
from .constants import (
    PALETTE_EDIT_NAMES as _PALETTE_EDIT_NAMES,
)
from .edits import (
    _apply_palette_edit,
)
from .launchers import (
    _open_add_end_command,
    _open_add_junction_command,
    _open_add_junction_relationship_command,
    _open_add_pathway_command,
    _open_add_wires_command,
    _open_append_gates_command,
    _open_end_member_edit,
    _open_palette_edit,
    _open_refine_command,
    _open_refine_edit_command,
    _open_segment_command,
)
from .palette_state import (
    _appearance_libraries_payload,
    _delete_damaged_harness,
    _library_appearances_payload,
    _send_palette_state,
    serialize_palette_state,
)
from .payloads import (
    _read_palette_payload,
    _read_payload_uuid,
    read_diagram_qa_observation,
)
from .runtime import runtime as _runtime
from .support import (
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from .viewport import (
    _apply_generated_materials,
    _clear_highlight,
    _clear_preview,
    _clear_solids,
    _generate_solids,
    _highlight_member,
    _preview_routes,
    _refresh_active_preview,
)


@dataclass(frozen=True)
class PaletteEditPolicy:
    """
    Describe post-transaction viewport work for one palette edit.
    """

    reconcile_refines: bool = False
    apply_generated_materials: bool = False
    ensure_preview_visible: bool = False


_DEFAULT_EDIT_POLICY = PaletteEditPolicy()
_PALETTE_EDIT_POLICIES = {action: _DEFAULT_EDIT_POLICY for action in _PALETTE_EDIT_NAMES}
_PALETTE_EDIT_POLICIES["remove_pathway_gate"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_pathway"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_junction"] = PaletteEditPolicy(reconcile_refines=True)
_MATERIAL_EDIT_POLICY = PaletteEditPolicy(
    apply_generated_materials=True,
    ensure_preview_visible=True,
)
_PALETTE_EDIT_POLICIES["set_harness_material_defaults"] = _MATERIAL_EDIT_POLICY
_PALETTE_EDIT_POLICIES["set_wire_material_overrides"] = _MATERIAL_EDIT_POLICY


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
    "add_junction_relationship": lambda application, data: _open_add_junction_relationship_command(
        application, data
    ),
    "add_end": lambda application, data: _open_add_end_command(application, data),
    "edit_end_members": lambda application, data: _open_end_member_edit(application, data),
    "append_pathway_gates": lambda application, data: _open_append_gates_command(application, data),
    "add_pathway_refine": lambda application, data: _open_refine_command(application, data),
    "segment_pathway": lambda application, data: _open_segment_command(application, data),
    "edit_pathway_refine": _launch_refine_edit,
    "add_wires": lambda application, data: _open_add_wires_command(application, data),
}


class _PaletteEditExecuteHandler(adsk.core.CommandEventHandler):
    """
    Apply a palette edit and its preview inside one Fusion command transaction.
    """

    def __init__(self, request: tuple[str, str, object]) -> None:
        """
        Capture the immutable request and its originating document.
        """
        super().__init__()
        self.request = request
        self.clear_preview_after_destroy = False

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Execute against the original document or fail the command without editing.
        """
        _runtime.last_command_error = ""
        action, data, document = self.request
        application = adsk.core.Application.get()
        try:
            if application.activeDocument != document:
                raise ValueError(
                    "The active document changed; retry the edit in its original document."
                )
            if action == "preview_routes":
                _preview_routes(application, data)
                return
            if action == "generate_solids":
                _generate_solids(application, data)
                self.clear_preview_after_destroy = True
                return
            if action == "clear_solids":
                _clear_solids(application, data)
                return
            if action == "delete_damaged_harness":
                notice = _delete_damaged_harness(application, data)
                application.activeViewport.refresh()
                _send_palette_state(application, notice)
                return
            policy = _PALETTE_EDIT_POLICIES.get(action)
            if policy is None:
                raise ValueError(f"Unsupported harness edit: {action}")
            notice = _apply_palette_edit(application, action, data)
            harness_id = _read_payload_uuid(_read_palette_payload(data), "harnessId", "harness")
            if policy.reconcile_refines:
                reconcile_active_refines(application)
            if policy.apply_generated_materials:
                notice = f"{notice} {_apply_generated_materials(application, harness_id)}".strip()
            warning = _refresh_active_preview(
                application,
                harness_id,
                ensure_visible=policy.ensure_preview_visible,
            )
            application.activeViewport.refresh()
            _send_palette_state(application, f"{notice} {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _runtime.last_command_error = str(error)
            _log_to_fusion(f"Harness command failed: {error}\n{traceback.format_exc()}")


class _PaletteEditCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Attach execution to a dialog-free command without editing during creation.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Consume the queued request once and let Fusion auto-execute the command.
        """
        request = _runtime.pending_palette_edit.consume()
        if request is None:
            return
        handler = _PaletteEditExecuteHandler(request)
        if not args.command.execute.add(handler):
            raise RuntimeError("Fusion could not attach the palette edit handler.")
        cleanup = _PaletteEditDestroyedHandler(handler)
        if not args.command.destroy.add(cleanup):
            args.command.execute.remove(handler)
            raise RuntimeError("Fusion could not attach edit cleanup.")
        _runtime.handler_registry.retain(handler, cleanup)


class _PaletteEditDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Release per-edit handlers when a short-lived palette command ends.
    """

    def __init__(self, execute_handler: _PaletteEditExecuteHandler) -> None:
        """
        Keep the paired execution handler alive until command destruction.
        """
        super().__init__()
        self.execute_handler = execute_handler

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Clear a completed solid preview, then release the short-lived handlers.
        """
        if self.execute_handler.clear_preview_after_destroy:
            application = adsk.core.Application.get()
            _action, _data, document = self.execute_handler.request
            if application.activeDocument == document:
                try:
                    _clear_preview(application)
                except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                    _log_to_fusion(f"Generated solids, but preview cleanup failed: {error}")
        _runtime.handler_registry.release(self.execute_handler, self)


class _ShowPaletteCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Show the persistent palette when Fusion creates the launcher command.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, _args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Create or reveal the palette immediately for this input-free command.
        """
        try:
            application = adsk.core.Application.get()
            _show_palette(application)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            _report_failure("open Harness Builder")
            raise


def _dispatch_palette_action(
    application: adsk.core.Application,
    action: str,
    data: str,
) -> str:
    """
    Dispatch one palette request while preserving its JSON boundary contract.
    """
    if action == "get_state":
        return serialize_palette_state(application)
    if action == "get_appearance_libraries":
        return json.dumps(
            {"ok": True, "libraries": _appearance_libraries_payload(application)},
            sort_keys=True,
        )
    if action == "get_library_appearances":
        payload = _read_palette_payload(data)
        library_id = payload.get("libraryId")
        if not isinstance(library_id, str) or not library_id.strip():
            raise ValueError("Appearance-library request requires a library ID.")
        return json.dumps(
            {
                "ok": True,
                "appearances": _library_appearances_payload(application, library_id),
            },
            sort_keys=True,
        )
    launcher = _NATIVE_DIALOG_ACTIONS.get(action)
    if launcher is not None:
        launcher(application, data)
        return json.dumps({"ok": True})
    if action == "clear_preview":
        count = _clear_preview(application)
        label = "group" if count == 1 else "groups"
        return json.dumps(
            {
                "ok": True,
                "notice": f"Cleared {count} route-preview graphics {label}.",
            }
        )
    if action in _PALETTE_EDIT_NAMES:
        _open_palette_edit(application, action, data)
        return json.dumps({"ok": True})
    if action == "highlight_member":
        try:
            count = _highlight_member(application, data)
        except (RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Harness highlight rejected: {error}")
            return json.dumps({"ok": False, "error": str(error)})
        return json.dumps({"ok": True, "selectionCount": count})
    if action == "clear_preview_highlight":
        highlight_route_preview(_require_active_design(application), None)
        application.activeViewport.refresh()
        return json.dumps({"ok": True})
    if action == "clear_highlight":
        _clear_highlight(application)
        return json.dumps({"ok": True})
    if action == "qa_diagram_observation":
        _runtime.last_diagram_qa_observation = read_diagram_qa_observation(data)
        return json.dumps({"ok": True})
    return json.dumps({"ok": False, "error": f"Unsupported palette action: {action}"})


class _PaletteIncomingHandler(adsk.core.HTMLEventHandler):
    """
    Handle requests sent by the local Harness Builder palette.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.HTMLEventArgs) -> None:
        """
        Dispatch one request and return its serialized boundary response.
        """
        html_args = None
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            if html_args is None:
                raise TypeError("Fusion did not provide valid palette event arguments.")
            application = adsk.core.Application.get()
            html_args.returnData = _dispatch_palette_action(
                application,
                html_args.action,
                html_args.data,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            if html_args is not None:
                html_args.returnData = json.dumps(
                    {"ok": False, "error": "Harness Builder could not complete the request."}
                )
            _report_failure("handle Harness Builder palette request")


class _PaletteNavigationHandler(adsk.core.NavigationEventHandler):
    """
    Record palette navigation in Fusion's application log.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.NavigationEventArgs) -> None:
        """
        Log the URL Fusion's embedded browser attempts to load.
        """
        try:
            navigation_args = adsk.core.NavigationEventArgs.cast(args)
            if navigation_args is None:
                raise TypeError("Fusion did not provide valid palette navigation arguments.")
            _log_to_fusion(f"Harness Builder navigating to: {navigation_args.navigationURL}")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("record Harness Builder palette navigation")


def _show_palette(application: adsk.core.Application) -> None:
    """
    Create or reveal the persistent Harness Builder palette.
    """
    user_interface = application.userInterface
    palette = user_interface.palettes.itemById(PALETTE_ID)
    if palette is None:
        missing_resources = [path for path in PALETTE_RESOURCE_FILES if not path.is_file()]
        if missing_resources:
            missing_list = ", ".join(str(path) for path in missing_resources)
            raise RuntimeError(f"Harness Builder palette resources are missing: {missing_list}")
        palette = user_interface.palettes.add(
            PALETTE_ID,
            COMMAND_NAME,
            PALETTE_HTML_URL,
            False,
            True,
            True,
            PALETTE_INITIAL_WIDTH,
            PALETTE_INITIAL_HEIGHT,
            True,
        )
        if palette is None:
            raise RuntimeError("Fusion did not create the Harness Builder palette.")
        incoming_handler = _PaletteIncomingHandler()
        if not palette.incomingFromHTML.add(incoming_handler):
            palette.deleteMe()
            raise RuntimeError("Fusion did not register the palette event handler.")
        navigation_handler = _PaletteNavigationHandler()
        if not palette.navigatingURL.add(navigation_handler):
            palette.deleteMe()
            raise RuntimeError("Fusion did not register the palette navigation handler.")
        _runtime.handler_registry.retain(incoming_handler, navigation_handler)
        _log_to_fusion(f"Harness Builder requested palette file: {palette.htmlFileURL}")
    try:
        palette.dockingOption = adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    except (AttributeError, RuntimeError) as error:
        _log_to_fusion(f"Harness Builder could not restore right docking: {error}")
    palette.isVisible = True
    _send_palette_state(application)


PaletteEditCreatedHandler = _PaletteEditCreatedHandler
ShowPaletteCreatedHandler = _ShowPaletteCreatedHandler
