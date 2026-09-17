"""
Fusion UI services for lifecycle.
"""

from __future__ import annotations

from typing import Optional

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ...application import load_harnesses
from .. import clear_route_previews
from ..refine_graphics import clear_refine_graphics, clear_refine_spine, has_refine_graphics
from ..route_preview import has_route_previews, reconcile_preview_history, reset_preview_history
from .commands.refines import (
    RefineActiveSelectionHandler,
    reconcile_active_refines,
)
from .constants import (
    ADD_END_COMMAND_ID,
    ADD_JUNCTION_COMMAND_ID,
    ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
    ADD_PATHWAY_COMMAND_ID,
    ADD_REFINE_COMMAND_ID,
    APPEND_GATES_COMMAND_ID,
    COMMAND_ID,
    COMMAND_RESOURCE_FOLDER,
    CREATE_COMMAND_ID,
    EDIT_REFINE_COMMAND_ID,
    PALETTE_ID,
    PANEL_IDS,
    SEGMENT_PATHWAY_COMMAND_ID,
    WORKSPACE_ID,
)
from .constants import (
    PALETTE_EDIT_NAMES as _PALETTE_EDIT_NAMES,
)
from .palette import (
    _PaletteEditCreatedHandler,
)
from .palette_state import (
    _send_palette_state,
)
from .registration import register_commands
from .runtime import runtime as _runtime
from .support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
)


class _HistoryChangedHandler(adsk.core.ApplicationCommandEventHandler):
    """
    Re-read restored state after commands, including native Undo and Redo.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, _args: adsk.core.ApplicationCommandEventArgs) -> None:
        """
        Synchronize only UI and Python caches so Redo history remains intact.
        """
        application = adsk.core.Application.get()
        try:
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is None:
                return
            results = load_harnesses(_create_harness_gateway(application))
            definitions = tuple(
                result.definition for result in results if result.definition is not None
            )
            reconcile_preview_history(design, definitions)
            _send_palette_state(application)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            _log_to_fusion(f"Could not synchronize harness history: {error}")


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


def _remove_document_handlers(application: adsk.core.Application) -> None:
    """
    Remove save guards and restore any compatibility preference they changed.
    """
    if _runtime.document_saving_handler is not None:
        application.documentSaving.remove(_runtime.document_saving_handler)
        _runtime.document_saving_handler = None
    if _runtime.document_saved_handler is not None:
        application.documentSaved.remove(_runtime.document_saved_handler)
        _runtime.document_saved_handler = None
    _restore_graphics_cache_preference(application)


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
        _remove_user_interface(user_interface)
        _register_palette_edit_commands(user_interface)

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

        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            reconcile_active_refines(application)
    except Exception:
        if application is not None:
            try:
                active_application = application
                _remove_document_handlers(active_application)
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

    try:
        application = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            clear_route_previews(design)
            clear_refine_spine(design)
            clear_refine_graphics(design)
        _remove_document_handlers(application)
        _remove_user_interface(application.userInterface)
        _runtime.handler_registry.clear()
        reset_preview_history()
        _runtime.reset_pending_requests()
        _runtime.damaged_harness_results.clear()
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
        COMMAND_ID,
        CREATE_COMMAND_ID,
        ADD_PATHWAY_COMMAND_ID,
        ADD_JUNCTION_COMMAND_ID,
        ADD_JUNCTION_RELATIONSHIP_COMMAND_ID,
        ADD_END_COMMAND_ID,
        APPEND_GATES_COMMAND_ID,
        ADD_REFINE_COMMAND_ID,
        SEGMENT_PATHWAY_COMMAND_ID,
        EDIT_REFINE_COMMAND_ID,
    ):
        command_definition = user_interface.commandDefinitions.itemById(command_id)
        if command_definition:
            command_definition.deleteMe()
    palette = user_interface.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()
