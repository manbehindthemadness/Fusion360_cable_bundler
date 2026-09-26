"""
Fusion UI services for lifecycle.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import HarnessLoadResult, load_harnesses
from .. import clear_route_previews
from ..cable_solids import (
    has_finalized_cable_group_output,
    restore_cable_group_stripe_graphics,
)
from ..harness_gateway import ATTRIBUTE_GROUP, DEFINITION_ATTRIBUTE_NAME
from ..hover_graphics import clear_hover_widgets
from ..interface_contact_cache import clear_contact_resolutions
from ..refine_graphics import clear_refine_graphics, clear_refine_spine, has_refine_graphics
from ..route_preview import (
    has_route_previews,
    hide_route_preview_for_harness,
    reconcile_preview_history,
    reset_preview_history,
)
from .commands.refines import (
    RefineActiveSelectionHandler,
    reconcile_active_refines,
)
from .constants import (
    COMMAND_ID,
    COMMAND_RESOURCE_FOLDER,
    PALETTE_ID,
    PANEL_IDS,
    SELECT_INTERFACE_CONTACTS_COMMAND_ID,
    WORKSPACE_ID,
)
from .constants import (
    PALETTE_EDIT_NAMES as _PALETTE_EDIT_NAMES,
)
from .palette import (
    _PaletteEditCreatedHandler,
    _register_deferred_palette_launch,
    _remove_deferred_palette_launch,
)
from .palette_state import (
    _send_palette_state,
)
from .registration import COMMAND_SPECS, register_commands
from .runtime import register_custom_event, remove_custom_event
from .runtime import runtime as _runtime
from .support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
)

_HISTORY_NAVIGATION_COMMAND_IDS = frozenset(("UndoCommand", "RedoCommand"))
_VIEW_COMMAND_IDS = frozenset(
    (
        "PanCommand",
        "OrbitCommand",
        "ZoomCommand",
        "ZoomWindowCommand",
        "FitCommand",
        "SelectCommand",
        "ClearSelectionCommand",
    )
)
_NON_MODEL_COMMAND_IDS = _VIEW_COMMAND_IDS | frozenset(("ScriptsManagerCommand", COMMAND_ID))
_DEFERRED_STRIPE_RESTORE_EVENT_ID = f"{COMMAND_ID}_deferred_stripe_restore"


def _log_document_checkpoint(application: adsk.core.Application, stage: str) -> None:
    """
    Record read-only document state around reload without exposing design contents.

    A changed definition digest indicates persisted harness content changed; a
    changed modified flag with stable digest and model counts points to a host
    graphics or other non-harness side effect. Diagnostic failures never block startup.
    """
    snapshot: dict[str, object] = {"stage": stage}
    try:
        document = application.activeDocument
        snapshot["modified"] = document.isModified if document is not None else None
        data_file = document.dataFile if document is not None else None
        snapshot["savedVersion"] = data_file.versionNumber if data_file is not None else None
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        snapshot["documentError"] = type(error).__name__
    try:
        design = adsk.fusion.Design.cast(application.activeProduct)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        snapshot["designError"] = type(error).__name__
        design = None
    if design is not None:
        try:
            snapshot["components"] = design.allComponents.count
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            snapshot["componentsError"] = type(error).__name__
        try:
            snapshot["timeline"] = design.timeline.count
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            snapshot["timelineError"] = type(error).__name__
        try:
            definitions = sorted(
                attribute.value
                for attribute in design.findAttributes(ATTRIBUTE_GROUP, DEFINITION_ATTRIBUTE_NAME)
            )
            encoded = json.dumps(definitions, separators=(",", ":")).encode("utf-8")
            snapshot["harnessDefinitions"] = len(definitions)
            snapshot["harnessDigest"] = hashlib.sha256(encoded).hexdigest()[:16]
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            snapshot["harnessError"] = type(error).__name__
    try:
        _log_to_fusion(f"Harness lifecycle checkpoint: {json.dumps(snapshot, sort_keys=True)}")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass


class _HistoryChangedHandler(adsk.core.ApplicationCommandEventHandler):
    """
    Re-read restored state after commands, including native Undo and Redo.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ApplicationCommandEventArgs) -> None:
        """
        Synchronize caches and recreate session-only decorations after history travel.

        Command termination must remain read-only. Fusion has already committed a
        native command at this point, so model or Custom Graphics writes here would
        create a second undo entry in front of the command the user just completed.
        """
        application = adsk.core.Application.get()
        try:
            reason = getattr(args, "terminationReason", None)
            if (
                reason is not None
                and reason != adsk.core.CommandTerminationReason.CompletedTerminationReason
            ):
                return
            if args.commandId in _NON_MODEL_COMMAND_IDS or args.commandId.startswith("ViewCube"):
                return
            metadata_commands = {
                f"{COMMAND_ID}_{action}"
                for action in (
                    "pos_import_interface_contacts",
                    "load_brd_interface_contacts",
                    "set_interface_contact_name",
                    "set_interface_contact_details",
                    "rename_interface",
                )
            }
            metadata_commands.add(SELECT_INTERFACE_CONTACTS_COMMAND_ID)
            if args.commandId not in metadata_commands:
                _runtime.contact_geometry_revision += 1
                clear_contact_resolutions()
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is None:
                return
            results = load_harnesses(_create_harness_gateway(application))
            definitions = tuple(
                result.definition for result in results if result.definition is not None
            )
            reconcile_preview_history(design, definitions)
            if args.commandId in _HISTORY_NAVIGATION_COMMAND_IDS:
                _request_deferred_stripe_restore(application)
            _send_palette_state(application)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Could not synchronize harness history: {error}")


class _DeferredStripeRestoreHandler(adsk.core.CustomEventHandler):
    """
    Recreate session-only stripes once Fusion has settled restored components.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, _args: adsk.core.CustomEventArgs) -> None:
        """
        Restore the latest active history state on Fusion's next idle event turn.
        """
        _runtime.stripe_restore_pending = False
        application = adsk.core.Application.get()
        try:
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is not None:
                _restore_active_stripe_graphics(application)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Could not restore stripe decorations after history change: {error}")


def _request_deferred_stripe_restore(application: adsk.core.Application) -> None:
    """
    Queue one coalesced stripe rebuild after Fusion finishes history navigation.
    """
    if _runtime.stripe_restore_pending:
        return
    _runtime.stripe_restore_pending = True
    if not application.fireCustomEvent(_DEFERRED_STRIPE_RESTORE_EVENT_ID):
        _runtime.stripe_restore_pending = False
        raise RuntimeError("Fusion could not queue stripe restoration.")


def _register_deferred_stripe_restore(application: adsk.core.Application) -> None:
    """
    Register the idle-queued event used to restore undo/redo decorations.
    """
    _remove_deferred_stripe_restore(application)
    handler = _DeferredStripeRestoreHandler()
    event = register_custom_event(
        application,
        _DEFERRED_STRIPE_RESTORE_EVENT_ID,
        handler,
        "deferred stripe restoration",
    )
    _runtime.deferred_stripe_restore_event = event
    _runtime.deferred_stripe_restore_handler = handler


def _remove_deferred_stripe_restore(application: adsk.core.Application) -> None:
    """
    Remove the deferred restoration event and discard any queued request.
    """
    event = _runtime.deferred_stripe_restore_event
    handler = _runtime.deferred_stripe_restore_handler
    remove_custom_event(
        application,
        _DEFERRED_STRIPE_RESTORE_EVENT_ID,
        event,
        handler,
    )
    _runtime.deferred_stripe_restore_event = None
    _runtime.deferred_stripe_restore_handler = None
    _runtime.stripe_restore_pending = False


class _DocumentSavingHandler(adsk.core.DocumentEventHandler):
    """
    Prevent live route previews from entering Fusion's saved OGS scene cache.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.DocumentEventArgs) -> None:
        """
        Disable graphics caching only for a save containing an active preview.
        """
        application = adsk.core.Application.get()
        try:
            design = _document_design(args.document)
            if design is None or not (has_route_previews(design) or has_refine_graphics(design)):
                return
            compatibility = application.preferences.compatibilityPreferences
            _runtime.capture_graphics_cache_preference(compatibility.isCacheGraphicsOnDocumentSave)
            _runtime.graphics_cache_save_document = args.document
            compatibility.isCacheGraphicsOnDocumentSave = False
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Could not protect route previews during save: {error}")


class _DocumentSavedHandler(adsk.core.DocumentEventHandler):
    """
    Restore the user's graphics-cache preference after a protected save.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.DocumentEventArgs) -> None:
        """
        Restore only after the document whose save disabled graphics caching.
        """
        if args.document != _runtime.graphics_cache_save_document:
            return
        _restore_graphics_cache_preference(adsk.core.Application.get())


def _document_design(document: adsk.core.Document) -> Optional[adsk.fusion.Design]:
    """
    Resolve the Design product owned by a document event.
    """
    product = document.products.itemByProductType("DesignProductType")
    return adsk.fusion.Design.cast(product)


def _restore_graphics_cache_preference(application: adsk.core.Application) -> None:
    """
    Restore the compatibility preference captured before a protected save.
    """
    if _runtime.graphics_cache_restore_value is None:
        return
    restore_value = _runtime.graphics_cache_restore_value
    _runtime.graphics_cache_restore_value = None
    _runtime.graphics_cache_save_document = None
    application.preferences.compatibilityPreferences.isCacheGraphicsOnDocumentSave = restore_value


def _register_document_handlers(application: adsk.core.Application) -> None:
    """
    Register save guards that keep transient previews out of saved documents.
    """
    _remove_document_handlers(application)
    saving_handler = _DocumentSavingHandler()
    if not application.documentSaving.add(saving_handler):
        raise RuntimeError("Fusion could not register route-preview save protection.")
    saved_handler = _DocumentSavedHandler()
    if not application.documentSaved.add(saved_handler):
        application.documentSaving.remove(saving_handler)
        raise RuntimeError("Fusion could not register graphics-cache restoration.")
    _runtime.document_saving_handler = saving_handler
    _runtime.document_saved_handler = saved_handler
    handler = _ContactDocumentChangedHandler()
    for event_name in ("documentActivated", "documentClosing"):
        event = getattr(application, event_name, None)
        if event is not None:
            if not event.add(handler):
                raise RuntimeError("Fusion could not register contact cache cleanup.")
            _runtime.contact_document_handler = handler


class _ContactDocumentChangedHandler(adsk.core.DocumentEventHandler):
    """
    Release native references before closing or changing the active document.
    """

    def notify(self, _args: adsk.core.DocumentEventArgs) -> None:
        """
        Invalidate geometry without performing geometry work during a document event.
        """
        clear_contact_resolutions()
        _runtime.contact_geometry_revision += 1


def _remove_document_handlers(application: adsk.core.Application) -> None:
    """
    Remove save guards and contact cleanup, restoring changed preferences.
    """
    clear_contact_resolutions()
    if _runtime.contact_document_handler is not None:
        for event_name in ("documentActivated", "documentClosing"):
            event = getattr(application, event_name, None)
            if event is not None:
                event.remove(_runtime.contact_document_handler)
        _runtime.contact_document_handler = None
    if _runtime.document_saving_handler is not None:
        application.documentSaving.remove(_runtime.document_saving_handler)
        _runtime.document_saving_handler = None
    if _runtime.document_saved_handler is not None:
        application.documentSaved.remove(_runtime.document_saved_handler)
        _runtime.document_saved_handler = None
    _restore_graphics_cache_preference(application)


def _restore_loaded_stripe_graphics(
    application: adsk.core.Application,
    results: tuple[HarnessLoadResult, ...],
) -> int:
    """
    Restore transient decorations for the supplied readable harnesses.

    One damaged generated component must not prevent other harnesses or the add-in
    itself from loading.
    """
    restored = 0
    for result in results:
        if result.definition is None or result.component_handle is None:
            continue
        try:
            restored += restore_cable_group_stripe_graphics(
                result.component_handle,
                result.definition,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(
                f"Could not restore stripe decorations for {result.component_name}: {error}"
            )
    if restored:
        application.activeViewport.refresh()
    return restored


def _restore_active_stripe_graphics(
    application: adsk.core.Application,
) -> int:
    """
    Load active harnesses and restore their transient stripe decorations.
    """
    results = load_harnesses(_create_harness_gateway(application))
    return _restore_loaded_stripe_graphics(application, results)


def _hide_loaded_finalized_previews(
    design: adsk.fusion.Design,
    results: tuple[HarnessLoadResult, ...],
) -> int:
    """
    Hide restored route graphics only for harnesses with finalized output.
    """
    hidden_count = 0
    for result in results:
        if result.definition is None or result.component_handle is None:
            continue
        if has_finalized_cable_group_output(result.component_handle):
            hidden_count += hide_route_preview_for_harness(design, result.definition)
    return hidden_count


def _register_palette_edit_commands(
    user_interface: adsk.core.UserInterface,
) -> None:
    """
    Register dialog-free command transactions used by palette edits.
    """
    for action, name in _PALETTE_EDIT_NAMES.items():
        definition = user_interface.commandDefinitions.addButtonDefinition(
            f"{COMMAND_ID}_{action}",
            name,
            name,
            COMMAND_RESOURCE_FOLDER,
        )
        handler = _PaletteEditCreatedHandler()
        if definition is None or not definition.commandCreated.add(handler):
            raise RuntimeError(f"Fusion could not register {name}.")
        _runtime.handler_registry.retain(handler)


def start(_context: object) -> None:
    """
    Register the Harness Builder commands and session event handlers with Fusion.
    """
    application = None
    user_interface = None
    try:
        application = adsk.core.Application.get()
        user_interface = application.userInterface
        _log_document_checkpoint(application, "start:entry")
        _remove_user_interface(user_interface)
        _register_palette_edit_commands(user_interface)
        _register_deferred_stripe_restore(application)
        _register_deferred_palette_launch(application)

        _runtime.history_handler = _HistoryChangedHandler()
        if not user_interface.commandTerminated.add(_runtime.history_handler):
            raise RuntimeError("Fusion could not register history synchronization.")
        _runtime.active_selection_handler = RefineActiveSelectionHandler()
        if not user_interface.activeSelectionChanged.add(_runtime.active_selection_handler):
            raise RuntimeError("Fusion could not register refine selection editing.")
        _register_document_handlers(application)

        workspace = user_interface.workspaces.itemById(WORKSPACE_ID)
        if workspace is None:
            raise RuntimeError(f"Fusion workspace is unavailable: {WORKSPACE_ID}")
        command_definitions = register_commands(user_interface)
        launcher_definition = command_definitions[COMMAND_ID]

        registered_panel_ids: list[str] = []
        for panel_id in PANEL_IDS:
            panel = workspace.toolbarPanels.itemById(panel_id)
            if panel is None:
                continue
            control = panel.controls.addCommand(launcher_definition)
            if control is None:
                raise RuntimeError(f"Fusion did not add Harness Builder to panel: {panel_id}")
            control.isPromotedByDefault = True
            control.isPromoted = True
            registered_panel_ids.append(panel_id)
        if not registered_panel_ids:
            raise RuntimeError(f"Fusion toolbar panels are unavailable: {', '.join(PANEL_IDS)}")

        _log_document_checkpoint(application, "start:ui_registered")
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            results = load_harnesses(_create_harness_gateway(application))
            _log_document_checkpoint(application, "start:harnesses_loaded")
            _restore_loaded_stripe_graphics(application, results)
            _log_document_checkpoint(application, "start:stripes_restored")
            reconcile_active_refines(application)
            _log_document_checkpoint(application, "start:refines_reconciled")
            if _hide_loaded_finalized_previews(design, results):
                application.activeViewport.refresh()
            _log_document_checkpoint(application, "start:previews_hidden")
    except Exception:
        if application is not None:
            try:
                active_application = application
                _remove_document_handlers(active_application)
                _remove_deferred_stripe_restore(active_application)
                _remove_deferred_palette_launch(active_application)
                if user_interface is not None:
                    _remove_user_interface(user_interface)
            except (AttributeError, RuntimeError, TypeError, ValueError) as cleanup_error:
                _log_to_fusion(f"Could not fully clean up failed add-in startup: {cleanup_error}")
        _runtime.handler_registry.clear()
        _runtime.reset_pending_requests()
        _report_failure("start")
        raise


def stop(_context: object) -> None:
    """
    Remove the command and release retained Fusion event handlers.
    """

    clear_contact_resolutions()
    try:
        application = adsk.core.Application.get()
        _log_document_checkpoint(application, "stop:entry")
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            clear_hover_widgets(design)
            _log_document_checkpoint(application, "stop:hover_cleared")
            clear_route_previews(design)
            _log_document_checkpoint(application, "stop:previews_cleared")
            clear_refine_spine(design)
            _log_document_checkpoint(application, "stop:spine_cleared")
            clear_refine_graphics(design)
            _log_document_checkpoint(application, "stop:refines_cleared")
        _remove_document_handlers(application)
        _remove_deferred_stripe_restore(application)
        _remove_deferred_palette_launch(application)
        _remove_user_interface(application.userInterface)
        _runtime.handler_registry.clear()
        reset_preview_history()
        _runtime.reset_pending_requests()
        _runtime.damaged_harness_results.clear()
        _log_document_checkpoint(application, "stop:done")
    except Exception:
        _report_failure("stop")
        raise


def _remove_user_interface(user_interface: adsk.core.UserInterface) -> None:
    """
    Remove stale command controls and definitions if they exist.
    """
    if _runtime.history_handler is not None:
        user_interface.commandTerminated.remove(_runtime.history_handler)
        _runtime.history_handler = None
    if _runtime.active_selection_handler is not None:
        user_interface.activeSelectionChanged.remove(_runtime.active_selection_handler)
        _runtime.active_selection_handler = None
    workspace = user_interface.workspaces.itemById(WORKSPACE_ID)
    if workspace is not None:
        for panel_id in PANEL_IDS:
            panel = workspace.toolbarPanels.itemById(panel_id)
            if panel is not None:
                control = panel.controls.itemById(COMMAND_ID)
                if control is not None:
                    control.deleteMe()

    for command_id in (
        *(f"{COMMAND_ID}_{action}" for action in _PALETTE_EDIT_NAMES),
        *(spec.command_id for spec in COMMAND_SPECS),
    ):
        command_definition = user_interface.commandDefinitions.itemById(command_id)
        if command_definition:
            command_definition.deleteMe()
    palette = user_interface.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()
