"""
Fusion UI services for palette.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...domain import loads
from .. import highlight_route_preview
from ..cable_solids import refresh_generated_cable_groups_for_connection
from ..interface_contact_cache import clear_contact_resolutions
from ..interface_contact_disk_cache import (
    clear_interface_contact_snapshot,
    describe_interface_contact_cache,
    disk_cache_available,
    project_cached_contact_batch,
    read_complete_cached_contacts,
)
from ..interface_contact_projection import project_interface_contact
from ..interface_contact_source import contact_source_signature
from .commands.refines import reconcile_active_refines
from .constants import (
    COMMAND_ID,
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
)
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


@dataclass(frozen=True)
class PaletteEditPolicy:
    """
    Describe post-transaction viewport work for one palette edit.
    """

    reconcile_refines: bool = False
    apply_generated_materials: bool = False
    ensure_preview_visible: bool = False
    refresh_connection_geometry: bool = False


_DEFAULT_EDIT_POLICY = PaletteEditPolicy()
_PALETTE_EDIT_POLICIES = {action: _DEFAULT_EDIT_POLICY for action in _PALETTE_EDIT_NAMES}
_PALETTE_EDIT_POLICIES["remove_pathway_gate"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_end_control"] = PaletteEditPolicy(reconcile_refines=True)
_CONNECTION_GEOMETRY_EDIT_POLICY = PaletteEditPolicy(refresh_connection_geometry=True)
_PALETTE_EDIT_POLICIES["add_cable_end_connection"] = _CONNECTION_GEOMETRY_EDIT_POLICY
_PALETTE_EDIT_POLICIES["disconnect_cable_end_relationship"] = PaletteEditPolicy(
    reconcile_refines=True,
    refresh_connection_geometry=True,
)
_PALETTE_EDIT_POLICIES["set_cable_end_attachment_properties"] = _CONNECTION_GEOMETRY_EDIT_POLICY
_PALETTE_EDIT_POLICIES["remove_cable_end_attachment"] = PaletteEditPolicy(
    reconcile_refines=True,
    refresh_connection_geometry=True,
)
_PALETTE_EDIT_POLICIES["remove_pathway"] = PaletteEditPolicy(reconcile_refines=True)
_PALETTE_EDIT_POLICIES["remove_junction"] = PaletteEditPolicy(reconcile_refines=True)
_MATERIAL_EDIT_POLICY = PaletteEditPolicy(
    apply_generated_materials=True,
    ensure_preview_visible=True,
)
_PALETTE_EDIT_POLICIES["set_harness_material_defaults"] = _MATERIAL_EDIT_POLICY
_GROUP_APPEARANCE_EDIT_POLICY = PaletteEditPolicy(ensure_preview_visible=True)
_PALETTE_EDIT_POLICIES["set_cable_group_properties"] = _GROUP_APPEARANCE_EDIT_POLICY
_PALETTE_EDIT_POLICIES["set_cable_group_material_overrides"] = _MATERIAL_EDIT_POLICY
_PALETTE_EDIT_POLICIES["set_cable_end_attachment_visual_overrides"] = _MATERIAL_EDIT_POLICY
_DEFERRED_PALETTE_LAUNCH_EVENT_ID = f"{COMMAND_ID}_deferred_palette_launch"


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
        launcher = _NATIVE_DIALOG_ACTIONS.get(action)
        if launcher is None:
            _log_to_fusion(f"Deferred palette launch is unsupported: {action}")
            return
        try:
            launcher(adsk.core.Application.get(), data)
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
    launcher = _NATIVE_DIALOG_ACTIONS[action]
    launcher(application, data)


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
            policy = _PALETTE_EDIT_POLICIES.get(action)
            if policy is None:
                raise ValueError(f"Unsupported harness edit: {action}")
            notice = _apply_palette_edit(application, action, data)
            if action in (
                "pos_import_interface_contacts",
                "load_brd_interface_contacts",
                "set_interface_contact_name",
                "set_interface_contact_details",
                "rename_interface",
            ):
                _send_palette_state(application, notice)
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
                ""
                if is_data_only_disconnect
                else _refresh_active_preview(
                    application,
                    harness_id,
                    ensure_visible=policy.ensure_preview_visible,
                )
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
            _runtime.contact_geometry_revision,
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
            geometry_revision=_runtime.contact_geometry_revision,
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
    launcher = _NATIVE_DIALOG_ACTIONS.get(action)
    if launcher is not None:
        if action == "connect_cable_end":
            launcher(application, data)
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
