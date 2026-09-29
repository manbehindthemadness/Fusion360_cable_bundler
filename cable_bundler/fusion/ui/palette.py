"""
Fusion UI services for palette.
"""

from __future__ import annotations

import json
import traceback
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import loads
from .. import highlight_route_preview
from ..cable_solids import refresh_generated_cable_groups_for_connection
from ..interface_board_source import linked_interface_boards, read_linked_board_pads
from ..interface_contact_cache import clear_contact_resolutions
from ..interface_contact_disk_cache import (
    clear_interface_contact_snapshot,
    describe_interface_contact_cache,
    disk_cache_available,
    project_cached_contact_batch,
    read_complete_cached_contacts,
)
from ..interface_contact_naming import (
    preview_board_file_contact_names,
    preview_interface_contact_names,
)
from ..interface_contact_projection import project_interface_contact
from ..interface_contact_source import contact_source_signature
from .commands.refines import reconcile_active_refines
from .constants import (
    COMMAND_ID,
    COMMAND_NAME,
    PALETTE_HTML_URL,
    PALETTE_ID,
    PALETTE_INITIAL_HEIGHT,
    PALETTE_INITIAL_WIDTH,
    PALETTE_RESOURCE_FILES,
)
from .constants import PALETTE_EDIT_NAMES as _PALETTE_EDIT_NAMES
from .edits import (
    _apply_palette_edit,
)
from .launchers import (
    _open_palette_edit,
)
from .palette_edit_policy import _PALETTE_EDIT_POLICIES
from .palette_native_dialogs import _NATIVE_DIALOG_ACTIONS, _NATIVE_DIALOG_COMMAND_IDS
from .palette_request_scope import _stale_palette_document_request
from .palette_state import (
    _appearance_libraries_payload,
    _delete_damaged_harness,
    _library_appearances_payload,
    _palette_theme_payload,
    _send_palette_state,
    serialize_palette_state,
)
from .payloads import (
    _read_palette_payload,
    _read_payload_uuid,
    read_diagram_qa_observation,
)
from .runtime import register_custom_event, remove_custom_event
from .runtime import runtime as _runtime
from .support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from .viewport import (
    _apply_generated_materials,
    _clear_highlight,
    _clear_preview,
    _clear_solids,
    _finalize_solids,
    _generate_solids,
    _highlight_member,
    _preview_routes,
    _refresh_active_preview,
)

_DEFERRED_PALETTE_LAUNCH_EVENT_ID = f"{COMMAND_ID}_deferred_palette_launch"


def _restore_native_dialog_palette(
    application: adsk.core.Application, command_id: str | None = None
) -> None:
    """
    Reveal the palette after its native command ends or fails to launch.
    """
    expected_id = _runtime.palette_restore_command_id
    if expected_id is None or (command_id is not None and command_id != expected_id):
        return
    _runtime.palette_restore_command_id = None
    palette = application.userInterface.palettes.itemById(PALETTE_ID)
    if palette is not None:
        palette.isVisible = True


def _launch_native_dialog(application: adsk.core.Application, action: str, data: str) -> None:
    """
    Hide the palette for opted-in native dialogs until command termination.
    """
    auto_hide = _read_palette_payload(data).get("autoHide", True)
    if not isinstance(auto_hide, bool):
        raise ValueError("Auto hide must be enabled or disabled.")
    palette = application.userInterface.palettes.itemById(PALETTE_ID)
    if auto_hide and palette is not None and palette.isVisible:
        if _runtime.palette_restore_command_id is not None:
            raise RuntimeError("Another Harness Builder dialog is already open.")
        _runtime.palette_restore_command_id = _NATIVE_DIALOG_COMMAND_IDS[action]
        try:
            palette.isVisible = False
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _runtime.palette_restore_command_id = None
            raise
    try:
        _NATIVE_DIALOG_ACTIONS[action](application, data)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        _restore_native_dialog_palette(application)
        raise


class _DeferredPaletteLaunchHandler(adsk.core.CustomEventHandler):
    """
    Open a native command after the palette bridge callback has returned.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, _args: adsk.core.CustomEventArgs) -> None:
        """
        Consume and launch one queued native-dialog request.
        """
        request = _runtime.pending_native_dialog.consume()
        if request is None:
            return
        action, data = request
        if action not in _NATIVE_DIALOG_ACTIONS:
            _log_to_fusion(f"Deferred palette launch is unsupported: {action}")
            return
        try:
            _launch_native_dialog(adsk.core.Application.get(), action, data)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Could not open deferred Harness Builder command: {error}")


def _request_deferred_palette_launch(
    application: adsk.core.Application,
    action: str,
    data: str,
) -> None:
    """
    Queue a native dialog for Fusion's next event turn.
    """
    try:
        _runtime.pending_native_dialog.prepare((action, data))
    except RuntimeError as error:
        raise RuntimeError("Another Harness Builder dialog is already opening.") from error
    if application.fireCustomEvent(_DEFERRED_PALETTE_LAUNCH_EVENT_ID):
        return

    # Fusion can reject the custom-event queue from a palette callback. Launch the
    # command through the original palette path instead of losing the request.
    _runtime.pending_native_dialog.clear()
    _launch_native_dialog(application, action, data)


def _register_deferred_palette_launch(application: adsk.core.Application) -> None:
    """
    Register the idle-queued native-dialog launcher.
    """
    _remove_deferred_palette_launch(application)
    handler = _DeferredPaletteLaunchHandler()
    event = register_custom_event(
        application,
        _DEFERRED_PALETTE_LAUNCH_EVENT_ID,
        handler,
        "deferred palette dialogs",
    )
    _runtime.deferred_palette_launch_event = event
    _runtime.deferred_palette_launch_handler = handler


def _remove_deferred_palette_launch(application: adsk.core.Application) -> None:
    """
    Remove the deferred native-dialog launcher and discard queued work.
    """
    event = _runtime.deferred_palette_launch_event
    handler = _runtime.deferred_palette_launch_handler
    remove_custom_event(
        application,
        _DEFERRED_PALETTE_LAUNCH_EVENT_ID,
        event,
        handler,
    )
    _runtime.deferred_palette_launch_event = None
    _runtime.deferred_palette_launch_handler = None
    _runtime.pending_native_dialog.clear()


def _send_board_file_preview(application: adsk.core.Application, data: str) -> None:
    """
    Return a local board's read-only name preview to the active palette form.
    """
    payload = _read_palette_payload(data)
    harness_id = _read_payload_uuid(payload, "harnessId", "harness")
    interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
    project = payload.get("project", False)
    if not isinstance(project, bool):
        raise ValueError("Project must be a boolean.")
    response: dict[str, object] = {
        "harnessId": str(harness_id),
        "interfaceId": str(interface_id),
    }
    try:
        preview = preview_board_file_contact_names(application, harness_id, interface_id, project)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        response["error"] = str(error)
    else:
        if preview is None:
            response["cancelled"] = True
        else:
            response.update(preview)
    palette = application.userInterface.palettes.itemById(PALETTE_ID)
    if palette is None:
        raise RuntimeError("Fusion could not return the board preview to the palette.")
    palette.sendInfoToHTML("board_file_preview", json.dumps(response))


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
        self.execute_finished_at: float | None = None

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
            if action == "finalize_solids":
                _finalize_solids(application, data)
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
            if action == "load_brd_interface_contacts":
                _send_board_file_preview(application, data)
                return
            policy = _PALETTE_EDIT_POLICIES.get(action)
            if policy is None:
                raise ValueError(f"Unsupported harness edit: {action}")
            edit_started = perf_counter()
            notice = _apply_palette_edit(application, action, data)
            edit_finished = perf_counter()
            if action in (
                "pos_import_interface_contacts",
                "geo_import_interface_contacts",
                "resolve_projected_interface_contacts",
                "set_interface_contact_name",
                "set_interface_contact_details",
                "auto_pin_interface_contacts",
                "name_interface_contact_locals",
                "clear_interface_contact_pins",
                "clear_interface_contact_values",
                "rename_interface_contact_orientation",
                "rename_interface",
            ):
                _send_palette_state(application, notice)
                _log_slow_palette_edit(action, edit_started, edit_finished)
                self.execute_finished_at = perf_counter()
                return
            payload = _read_palette_payload(data)
            harness_id = _read_payload_uuid(payload, "harnessId", "harness")
            is_data_only_disconnect = (
                action == "disconnect_cable_end_relationship"
                and payload.get("relationship") == "shielding"
            )
            if policy.reconcile_refines and not is_data_only_disconnect:
                reconcile_active_refines(application)
            if policy.apply_generated_materials:
                notice = f"{notice} {_apply_generated_materials(application, harness_id)}".strip()
            refreshes_connection_geometry = (
                policy.refresh_connection_geometry
                and not is_data_only_disconnect
                and (action != "set_cable_end_attachment_properties" or "diameterMm" in payload)
            )
            if refreshes_connection_geometry:
                connection_id = _read_payload_uuid(payload, "connectionId", "cable end")
                gateway = _create_harness_gateway(application)
                definition = loads(gateway.read_harness_definition(harness_id))
                updated_count = refresh_generated_cable_groups_for_connection(
                    _require_active_design(application),
                    gateway.harness_component(harness_id),
                    definition,
                    connection_id,
                )
                if updated_count:
                    notice = (
                        f"{notice} Updated {updated_count} generated cable "
                        f"group{'s' if updated_count != 1 else ''}."
                    )
            warning = (
                _refresh_active_preview(
                    application,
                    harness_id,
                    ensure_visible=policy.ensure_preview_visible,
                )
                if policy.refresh_preview and not is_data_only_disconnect
                else ""
            )
            if policy.refresh_preview:
                application.activeViewport.refresh()
            _send_palette_state(application, f"{notice} {warning}".strip())
            _log_slow_palette_edit(action, edit_started, edit_finished)
            self.execute_finished_at = perf_counter()
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _runtime.last_command_error = str(error)
            _log_to_fusion(f"Harness command failed: {error}\n{traceback.format_exc()}")


def _log_slow_palette_edit(action: str, started: float, applied_at: float) -> None:
    """
    Record slow edit persistence separately from subsequent preview and palette work.
    """
    finished = perf_counter()
    if not _runtime.developer_mode_enabled or finished - started < 0.25:
        return
    _log_to_fusion(
        f"Harness Builder slow edit {action}: "
        f"applyMs={(applied_at - started) * 1000:.0f} "
        f"postMs={(finished - applied_at) * 1000:.0f}"
    )


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
        finished_at = self.execute_handler.execute_finished_at
        if finished_at is not None:
            elapsed = perf_counter() - finished_at
            if _runtime.developer_mode_enabled and elapsed >= 0.25:
                _log_to_fusion(
                    "Harness Builder slow command completion "
                    f"{self.execute_handler.request[0]}: afterExecuteMs={elapsed * 1000:.0f}"
                )
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
    if _stale_palette_document_request(application, action, data):
        return json.dumps({"ok": False, "stale": True})
    if action == "get_state":
        return serialize_palette_state(application)
    if action in (
        "get_pos_import_boards",
        "preview_pos_import_interface_contacts",
        "pos_import_interface_contacts",
    ):
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        interface = next(
            (item for item in definition.interfaces if item.interface_id == interface_id), None
        )
        if interface is None:
            raise ValueError("Selected Interface no longer exists.")
        boards = linked_interface_boards(_require_active_design(application), interface)
        if action == "get_pos_import_boards":
            return json.dumps(
                {
                    "ok": True,
                    "boards": [
                        {"name": board.name, "versionId": board.version_id} for board in boards
                    ],
                }
            )
        if action == "pos_import_interface_contacts":
            _open_palette_edit(application, action, data)
            return json.dumps({"ok": True})
        version_id = payload.get("boardVersionId")
        matches = [board for board in boards if board.version_id == version_id]
        if len(matches) != 1:
            raise ValueError("The selected linked PCB changed; reopen Pos Import.")
        pads = read_linked_board_pads(application, matches[0])
        project = payload.get("project", False)
        if not isinstance(project, bool):
            raise ValueError("Project must be a boolean.")
        preview = preview_interface_contact_names(
            application, harness_id, interface_id, pads, project
        )
        return json.dumps({"ok": True, **preview})
    if action == "get_interface_contact_signatures":
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        requested_ids = payload.get("contactIds")
        if (
            not isinstance(requested_ids, list)
            or len(requested_ids) > 1024
            or not all(isinstance(value, str) for value in requested_ids)
        ):
            raise ValueError("Request at most 1024 contact identities for validation.")
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        interface = next(
            (item for item in definition.interfaces if item.interface_id == interface_id), None
        )
        if interface is None:
            raise ValueError("Selected Interface no longer exists.")
        by_id = {str(contact.contact_id): contact for contact in interface.contacts}
        if len(requested_ids) != len(set(requested_ids)) or any(
            contact_id not in by_id for contact_id in requested_ids
        ):
            raise ValueError("Contact identities no longer match the saved Interface.")
        design = _require_active_design(application)
        signatures = {
            contact_id: contact_source_signature(design, by_id[contact_id])
            for contact_id in requested_ids
        }
        return json.dumps({"ok": True, "signatures": signatures})
    if action == "get_interface_contacts_cached":
        started = perf_counter()
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        requested_ids = payload.get("contactIds")
        if (
            not isinstance(requested_ids, list)
            or len(requested_ids) > 1024
            or not all(isinstance(value, str) for value in requested_ids)
        ):
            raise ValueError("Request at most 1024 contact identities for a warm-cache read.")
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        interface = next(
            (item for item in definition.interfaces if item.interface_id == interface_id), None
        )
        if interface is None:
            raise ValueError("Selected Interface no longer exists.")
        by_id = {str(contact.contact_id): contact for contact in interface.contacts}
        if len(requested_ids) != len(set(requested_ids)) or any(
            contact_id not in by_id for contact_id in requested_ids
        ):
            raise ValueError("Contact identities no longer match the saved Interface.")
        contacts = [by_id[contact_id] for contact_id in requested_ids]
        projections = read_complete_cached_contacts(
            application,
            harness_id,
            interface_id,
            contacts,
            _runtime.contact_cache_revision(application),
        )
        return json.dumps(
            {
                "ok": True,
                "cacheComplete": projections is not None,
                "contacts": projections if projections is not None else [],
                "serverMs": round((perf_counter() - started) * 1000),
            }
        )
    if action == "get_interface_contacts":
        started = perf_counter()
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        interface = next(
            (item for item in definition.interfaces if item.interface_id == interface_id), None
        )
        if interface is None:
            raise ValueError("Selected Interface no longer exists.")
        requested_ids = payload.get("contactIds")
        if (
            not isinstance(requested_ids, list)
            or len(requested_ids) > 8
            or not all(isinstance(value, str) for value in requested_ids)
        ):
            raise ValueError("Request at most eight contact identities per geometry batch.")
        requested = set(requested_ids)
        design = _require_active_design(application)
        selected = [
            contact for contact in interface.contacts if str(contact.contact_id) in requested
        ]
        diagnostic_request = payload.get("diagnostics") is True
        cache_before = (
            describe_interface_contact_cache(application, harness_id, interface_id)
            if diagnostic_request and payload.get("diagnosticFirstBatch") is True
            else None
        )
        cache_stats: dict[str, int] | None = {} if diagnostic_request else None
        projections = project_cached_contact_batch(
            application,
            design,
            harness_id,
            interface_id,
            selected,
            project_interface_contact,
            diagnostics=cache_stats,
            geometry_revision=_runtime.contact_cache_revision(application),
        )
        for contact, projection in zip(selected, projections):
            projection["sourceSignature"] = contact_source_signature(design, contact)
        result: dict[str, object] = {
            "ok": True,
            "contacts": projections,
            "geometryRevision": _runtime.contact_geometry_revision,
        }
        if cache_before is not None:
            result["cacheBefore"] = cache_before
        if cache_stats is not None:
            result["cacheStats"] = cache_stats
            result["serverMs"] = round((perf_counter() - started) * 1000)
        return json.dumps(result)
    if action == "get_interface_contact_cache_status":
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        return json.dumps(
            {
                "ok": True,
                "cache": describe_interface_contact_cache(application, harness_id, interface_id),
            }
        )
    if action == "rebuild_interface_contacts_cache":
        payload = _read_palette_payload(data)
        harness_id = _read_payload_uuid(payload, "harnessId", "harness")
        interface_id = _read_payload_uuid(payload, "interfaceId", "Interface")
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        if not any(item.interface_id == interface_id for item in definition.interfaces):
            raise ValueError("Selected Interface no longer exists.")
        try:
            cleared = clear_interface_contact_snapshot(application, harness_id, interface_id)
        except OSError as error:
            raise RuntimeError("Could not clear the Interface contact disk cache.") from error
        clear_contact_resolutions()
        return json.dumps(
            {
                "ok": True,
                "diskCacheAvailable": disk_cache_available(application, harness_id, interface_id),
                "diskCacheCleared": cleared,
            }
        )
    if action == "get_theme":
        return json.dumps(
            {"ok": True, "theme": _palette_theme_payload(application)},
            sort_keys=True,
        )
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
    if action in _NATIVE_DIALOG_ACTIONS:
        if action == "connect_cable_end":
            _launch_native_dialog(application, action, data)
        else:
            _request_deferred_palette_launch(application, action, data)
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
    if action == "set_developer_mode":
        enabled = _read_palette_payload(data).get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("Developer Mode must be enabled or disabled.")
        _runtime.developer_mode_enabled = enabled
        return json.dumps({"ok": True})
    if action == "palette_performance":
        payload = _read_palette_payload(data)
        metrics = ("keyMs", "prepareMs", "libraryMs", "editorMs", "totalMs")
        values = tuple(payload.get(metric) for metric in metrics)
        if not isinstance(payload.get("rebuilt"), bool) or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 60000
            for value in values
        ):
            raise ValueError("Palette performance report is malformed.")
        if _runtime.developer_mode_enabled:
            _log_to_fusion(
                "Harness Builder slow browser render: "
                f"rebuilt={payload['rebuilt']} "
                + " ".join(f"{metric}={value:.0f}" for metric, value in zip(metrics, values))
            )
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
        palette.isDockedInCanvas = True
    except (AttributeError, RuntimeError) as error:
        _log_to_fusion(f"Harness Builder could not restore in-canvas docking: {error}")
    try:
        palette.dockingOption = adsk.core.PaletteDockingOptions.PaletteDockOptionsToVerticalOnly
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    except (AttributeError, RuntimeError) as error:
        _log_to_fusion(f"Harness Builder could not restore right docking: {error}")
    palette.isVisible = True
    _send_palette_state(application)


PaletteEditCreatedHandler = _PaletteEditCreatedHandler
ShowPaletteCreatedHandler = _ShowPaletteCreatedHandler
