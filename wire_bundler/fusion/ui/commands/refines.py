"""
Fusion command controllers for refines.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, replace
from typing import Optional, Protocol
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import (
    add_end_refine,
    add_pathway_refine,
    load_harnesses,
    update_pathway_refine,
)
from ....domain import ControlKind, RefineGeometry, loads
from ....routing import Vector3
from ....routing.geometry import cross, unit
from ...refine_graphics import (
    REFINE_GRAPHICS_GROUP_ID,
    REFINE_SPINE_ENTITY_ID,
    PathwaySpine,
    RefinePlacement,
    build_end_spine,
    build_pathway_spine,
    clear_refine_spine,
    draw_candidate_refine,
    draw_pathway_spine,
    draw_refine_editor,
    place_refine,
    reconcile_refine_graphics,
)
from ...wire_solids import (
    WireSolidVisibilityState,
    hide_generated_wire_group_solids,
    restore_generated_wire_group_visibility,
)
from ..constants import REFINE_RADIUS_INPUT_ID, REFINE_SPINE_INPUT_ID, REFINE_TRANSFORM_INPUT_ID
from ..launchers import _open_refine_edit_command
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from ..viewport import _refresh_active_preview

MINIMUM_REFINE_RADIUS_MM = 0.5


@dataclass
class _RefineCommandState:
    """
    Share the temporary spine and current placement across command handlers.
    """

    harness_id: UUID
    target_id: UUID
    spine: PathwaySpine
    target_kind: str = "pathway"
    group: Optional[adsk.fusion.CustomGraphicsGroup] = None
    placement: Optional[RefinePlacement] = None
    candidate: Optional[adsk.fusion.CustomGraphicsLines] = None
    preselected_point_mm: Optional[Vector3] = None
    solid_visibility: WireSolidVisibilityState = ()


class _SelectionInput(Protocol):
    """
    Expose selection operations needed around preview-backed graphics.
    """

    # noinspection PyPep8Naming
    def setSelectionLimits(self, minimum: int, maximum: int = 0) -> bool:
        """
        Require a bounded number of selections.
        """
        ...

    # noinspection PyPep8Naming
    def clearSelection(self) -> bool:
        """
        Release the transient graphics selection before preview rollback.
        """
        ...


class _RefinePreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Restrict Custom Graphics selection to the command-owned pathway spine.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain the last valid spine point before preview rollback invalidates it.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Reject persistent markers and unrelated selectable graphics.
        """
        selection = args.selection
        entity = selection.entity if selection is not None else None
        args.isSelectable = getattr(entity, "id", None) == REFINE_SPINE_ENTITY_ID
        point_mm = _refine_spine_selection_point_mm(selection)
        if point_mm is not None:
            self._state.preselected_point_mm = point_mm


def _refine_spine_selection_point_mm(selection: object) -> Optional[Vector3]:
    """
    Convert a valid Custom Graphics spine selection point to millimeters.
    """
    entity = getattr(selection, "entity", None)
    point: Optional[adsk.core.Point3D] = getattr(selection, "point", None)
    if getattr(entity, "id", None) != REFINE_SPINE_ENTITY_ID or point is None:
        return None
    return Vector3(point.x * 10.0, point.y * 10.0, point.z * 10.0)


def _selected_refine_point_mm(
    selection_input: Optional[adsk.core.SelectionCommandInput],
) -> Optional[Vector3]:
    """
    Read a selected spine point, tolerating Fusion-invalidated preview entities.
    """
    if selection_input is None or selection_input.selectionCount != 1:
        return None
    try:
        selection = selection_input.selection(0)
    except (AttributeError, RuntimeError, TypeError):
        return None
    return _refine_spine_selection_point_mm(selection)


def _update_refine_placement(
    state: _RefineCommandState,
    command_inputs: adsk.core.CommandInputs,
    *,
    position_manipulator: bool = True,
) -> None:
    """
    Capture selection and radius inputs without modifying document graphics.
    """
    radius_input = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if radius_input is None:
        raise RuntimeError("Refine radius input is unavailable.")
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(REFINE_SPINE_INPUT_ID)
    )
    if selection_input is not None and selection_input.selectionCount == 1:
        selected_point_mm = _selected_refine_point_mm(selection_input)
        if selected_point_mm is None:
            selected_point_mm = state.preselected_point_mm
        if selected_point_mm is None:
            radius_input.isEnabled = False
            radius_input.isVisible = False
            return
        state.placement = place_refine(
            state.spine,
            selected_point_mm,
            _read_refine_radius_mm(radius_input),
        )
    elif state.placement is not None:
        radius_mm = _read_refine_radius_mm(radius_input)
        state.placement = replace(
            state.placement,
            geometry=replace(
                state.placement.geometry,
                display_radius_mm=radius_mm,
            ),
        )
    else:
        radius_input.isEnabled = False
        radius_input.isVisible = False
        return
    placement = state.placement
    if placement is None:
        raise RuntimeError("Refine placement state was not captured.")
    _show_refine_radius_input(radius_input, placement, position_manipulator=position_manipulator)


def _show_refine_radius_input(
    radius_input: adsk.core.DistanceValueCommandInput,
    placement: RefinePlacement,
    *,
    position_manipulator: bool = True,
) -> None:
    """
    Reveal the radius control and optionally position its canvas manipulator.
    """
    radius_input.isEnabled = True
    radius_input.isVisible = True
    if not position_manipulator:
        return
    origin = placement.geometry.origin_mm
    direction = placement.geometry.u_direction
    if not radius_input.setManipulator(
        adsk.core.Point3D.create(*(coordinate / 10.0 for coordinate in origin)),
        adsk.core.Vector3D.create(*direction),
    ):
        raise RuntimeError("Fusion could not position the refine-radius manipulator.")


def _draw_add_refine_preview(state: _RefineCommandState) -> None:
    """
    Rebuild Add Refine graphics inside Fusion's preview transaction.
    """
    application = adsk.core.Application.get()
    design = _require_active_design(application)
    group, _lines = draw_pathway_spine(design, state.spine)
    state.group = group
    state.candidate = None
    if state.placement is not None:
        state.candidate = draw_candidate_refine(group, state.placement.geometry)
    application.activeViewport.refresh()


class _RefineActivateHandler(adsk.core.CommandEventHandler):
    """
    Request the initial preview after the command becomes interactive.
    """

    def __init__(
        self,
        selection_input: Optional[_SelectionInput] = None,
    ) -> None:
        """
        Optionally require placement selection after the initial preview exists.
        """
        super().__init__()
        self._selection_input = selection_input

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Draw command graphics, then let Fusion disable OK until placement.
        """
        try:
            if not args.command.doExecutePreview():
                raise RuntimeError("Fusion could not start the refine preview.")
            if self._selection_input is not None:
                if not self._selection_input.setSelectionLimits(1, 1):
                    raise RuntimeError("Fusion could not require refine-path selection.")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("start refine preview")


class _RefineSelectHandler(adsk.core.SelectionEventHandler):
    """
    Capture a spine click before Fusion invalidates its preview graphics.
    """

    def __init__(
        self,
        state: _RefineCommandState,
        command: adsk.core.Command,
        command_inputs: adsk.core.CommandInputs,
        selection_input: _SelectionInput,
    ) -> None:
        """
        Retain the placement state and command controls needed after selection.
        """
        super().__init__()
        self._state = state
        self._command = command
        self._command_inputs = command_inputs
        self._selection_input = selection_input

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Store the clicked point, release its transient entity, and redraw.
        """
        try:
            selected_point_mm = _refine_spine_selection_point_mm(args.selection)
            if selected_point_mm is None:
                return
            radius_input = adsk.core.DistanceValueCommandInput.cast(
                self._command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
            )
            if radius_input is None:
                raise RuntimeError("Refine radius input is unavailable.")
            placement = place_refine(
                self._state.spine,
                selected_point_mm,
                _read_refine_radius_mm(radius_input),
            )
            self._state.preselected_point_mm = selected_point_mm
            self._state.placement = placement
            _show_refine_radius_input(radius_input, placement)
            if not self._selection_input.setSelectionLimits(0, 1):
                raise RuntimeError("Fusion could not release refine-path selection.")
            if not self._selection_input.clearSelection():
                raise RuntimeError("Fusion could not clear refine-path selection.")
            if not self._command.doExecutePreview():
                raise RuntimeError("Fusion could not redraw the refine preview.")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("select refine point")


class _RefineExecutePreviewHandler(adsk.core.CommandEventHandler):
    """
    Own all Add Refine document graphics inside a disposable transaction.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain the command-local placement state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Recreate the selectable spine and current candidate marker.
        """
        try:
            _draw_add_refine_preview(self._state)
            args.isValidResult = False
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("preview refine point")


class _RefineInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Capture the selected Custom Graphics point and current radius.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain placement state across input changes.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Update placement after either spine selection or marker-radius changes.
        """
        try:
            _update_refine_placement(self._state, args.inputs)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("place refine point")


class _RefineMouseDragHandler(adsk.core.MouseEventHandler):
    """
    Refresh the placement marker while Fusion's radius manipulator is dragged.
    """

    def __init__(
        self,
        state: _RefineCommandState,
        command_inputs: adsk.core.CommandInputs,
        command: adsk.core.Command,
    ) -> None:
        """
        Retain placement state and its command inputs for drag notifications.
        """
        super().__init__()
        self._state = state
        self._command_inputs = command_inputs
        self._command = command

    def notify(self, _args: adsk.core.MouseEventArgs) -> None:
        """
        Apply the manipulator's current value without repositioning it mid-drag.
        """
        try:
            _update_refine_placement(
                self._state,
                self._command_inputs,
                position_manipulator=False,
            )
            if not self._command.doExecutePreview():
                raise RuntimeError("Fusion could not refresh the refine preview.")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("preview refine radius")


class _RefineValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Enable execution only after a valid point is selected on the pathway spine.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain the command-local placement state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Revalidate the selection and positive display radius.
        """
        if self._state.placement is None:
            args.areInputsValid = True
            return
        try:
            radius_input = adsk.core.DistanceValueCommandInput.cast(
                args.inputs.itemById(REFINE_RADIUS_INPUT_ID)
            )
            _read_refine_radius_mm(radius_input)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = self._state.placement is not None


class _RefineExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one selected refine point inside the Fusion command transaction.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain the command-local placement state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Insert the refine, synchronize occupied wires, and refresh the UI.
        """
        application = adsk.core.Application.get()
        try:
            if self._state.placement is None:
                raise ValueError("Select one point on the pathway spine.")
            radius_input = adsk.core.DistanceValueCommandInput.cast(
                args.command.commandInputs.itemById(REFINE_RADIUS_INPUT_ID)
            )
            placement = replace(
                self._state.placement,
                geometry=replace(
                    self._state.placement.geometry,
                    display_radius_mm=_read_refine_radius_mm(radius_input),
                ),
            )
            gateway = _create_harness_gateway(application)
            if self._state.target_kind == "end":
                add_end_refine(
                    self._state.harness_id,
                    self._state.target_id,
                    placement.insertion_index - 1,
                    placement.geometry,
                    gateway,
                )
            else:
                add_pathway_refine(
                    self._state.harness_id,
                    self._state.target_id,
                    placement.insertion_index,
                    placement.geometry,
                    gateway,
                )
            warning = _refresh_active_preview(application, self._state.harness_id)
            _finalize_refine_graphics(application)
            _send_palette_state(application, f"Added refine point. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add refine point failed: {error}\n{traceback.format_exc()}")


class _RefineDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Release short-lived handlers after Fusion removes preview graphics.
    """

    def __init__(self, state: _RefineCommandState, handlers: list[object]) -> None:
        """
        Retain command visibility state and handlers until destruction.
        """
        super().__init__()
        self._state = state
        self._command_handlers = handlers

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Restore generated solids and release handlers after preview rollback.
        """
        try:
            restore_generated_wire_group_visibility(self._state.solid_visibility)
            application = adsk.core.Application.get()
            application.activeViewport.refresh()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("restore generated wire solids after refine placement")
        finally:
            _runtime.handler_registry.release(*self._command_handlers, self)


class _RefineCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build a selectable pathway spine and radius input for refine placement.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the selected pathway and attach command-lifetime handlers.
        """
        pending_ids = _runtime.pending_refine.consume()
        state: Optional[_RefineCommandState] = None
        try:
            if pending_ids is None:
                raise RuntimeError("No routing span was selected for refine placement.")
            target_kind, harness_id, target_id = pending_ids
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(harness_id))
            spine = (
                build_end_spine(design, definition, target_id)
                if target_kind == "end"
                else build_pathway_spine(design, definition, target_id)
            )
            selection_input = args.command.commandInputs.addSelectionInput(
                REFINE_SPINE_INPUT_ID,
                "Routing Point",
                "Select a point on the cyan routing spine",
            )
            if selection_input is None or not selection_input.addSelectionFilter("CustomGraphics"):
                raise RuntimeError("Fusion could not configure refine-path selection.")
            if not selection_input.setSelectionLimits(0, 1):
                raise RuntimeError("Fusion could not limit refine-path selection.")
            radius_input = _add_refine_radius_input(args.command.commandInputs)
            radius_input.isVisible = False
            radius_input.isEnabled = False
            command_state = _RefineCommandState(harness_id, target_id, spine, target_kind)
            state = command_state
            activate_handler = _RefineActivateHandler(selection_input)
            preselect_handler = _RefinePreSelectHandler(command_state)
            select_handler = _RefineSelectHandler(
                command_state,
                args.command,
                args.command.commandInputs,
                selection_input,
            )
            input_handler = _RefineInputChangedHandler(command_state)
            preview_handler = _RefineExecutePreviewHandler(command_state)
            drag_handler = _RefineMouseDragHandler(
                command_state,
                args.command.commandInputs,
                args.command,
            )
            validate_handler = _RefineValidateInputsHandler(command_state)
            execute_handler = _RefineExecuteHandler(command_state)
            command_handlers: list[object] = [
                activate_handler,
                preselect_handler,
                select_handler,
                input_handler,
                preview_handler,
                drag_handler,
                validate_handler,
                execute_handler,
            ]
            destroyed = _RefineDestroyedHandler(command_state, command_handlers)
            if not args.command.activate.add(activate_handler):
                raise RuntimeError("Fusion could not start the refine preview.")
            if not args.command.preSelect.add(preselect_handler):
                raise RuntimeError("Fusion could not filter refine-path selection.")
            if not args.command.select.add(select_handler):
                raise RuntimeError("Fusion could not capture refine-path selection.")
            if not args.command.inputChanged.add(input_handler):
                raise RuntimeError("Fusion could not watch refine placement.")
            if not args.command.executePreview.add(preview_handler):
                raise RuntimeError("Fusion could not preview refine placement.")
            if not args.command.mouseDrag.add(drag_handler):
                raise RuntimeError("Fusion could not watch refine radius dragging.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate refine placement.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save refine placement.")
            if not args.command.destroy.add(destroyed):
                raise RuntimeError("Fusion could not register refine cleanup.")
            _runtime.handler_registry.retain(*command_handlers, destroyed)
            command_state.solid_visibility = hide_generated_wire_group_solids(
                gateway.harness_component(harness_id)
            )
            application.activeViewport.refresh()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            application = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is not None:
                clear_refine_spine(design)
            if state is not None:
                restore_generated_wire_group_visibility(state.solid_visibility)
            _report_failure("open Add Refine Point")
            raise


@dataclass
class _EditRefineCommandState:
    """
    Share the edited refine identity and temporary marker across handlers.
    """

    harness_id: UUID
    control_id: UUID
    geometry: RefineGeometry
    group: Optional[adsk.fusion.CustomGraphicsGroup] = None


def _preview_edited_refine(
    state: _EditRefineCommandState,
    command_inputs: adsk.core.CommandInputs,
) -> None:
    """
    Capture current triad and radius values without modifying document graphics.
    """
    geometry = _read_edited_refine_geometry(command_inputs)
    state.geometry = geometry


class _EditRefineInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Capture editor geometry throughout graphical and typed manipulation.
    """

    def __init__(self, state: _EditRefineCommandState) -> None:
        """
        Retain the command-local edit state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Capture changed command values for the next preview transaction.
        """
        try:
            _preview_edited_refine(self._state, args.inputs)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("preview edited refine point")


class _EditRefineExecutePreviewHandler(adsk.core.CommandEventHandler):
    """
    Redraw an edited refine in Fusion's command-preview transaction.
    """

    def __init__(self, state: _EditRefineCommandState) -> None:
        """
        Retain the command-local edit state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Recreate the editor marker inside Fusion's preview transaction.
        """
        try:
            _preview_edited_refine(self._state, args.command.commandInputs)
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            self._state.group = draw_refine_editor(
                design,
                self._state.control_id,
                self._state.geometry,
            )
            application.activeViewport.refresh()
            args.isValidResult = False
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("preview edited refine point")


class _EditRefineValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require a valid rigid transform and positive marker radius.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Disable execution while either edit input is invalid.
        """
        try:
            _read_edited_refine_geometry(args.inputs)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _EditRefineExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist an edited refine inside the Fusion command transaction.
    """

    def __init__(self, state: _EditRefineCommandState) -> None:
        """
        Retain the selected harness and refine identities.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Save the final transform and radius, then refresh affected routes.
        """
        application = adsk.core.Application.get()
        try:
            geometry = _read_edited_refine_geometry(args.command.commandInputs)
            update_pathway_refine(
                self._state.harness_id,
                self._state.control_id,
                geometry,
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._state.harness_id)
            _finalize_refine_graphics(application)
            _send_palette_state(application, f"Updated refine point. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Edit refine point failed: {error}\n{traceback.format_exc()}")


class _EditRefineDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Release short-lived handlers after Save or Cancel.
    """

    def __init__(self, handlers: list[object]) -> None:
        """
        Retain command handlers until destruction.
        """
        super().__init__()
        self._command_handlers = handlers

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Release handlers after Fusion rolls back command-preview graphics.
        """
        _runtime.handler_registry.release(*self._command_handlers, self)


class _EditRefineCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build a triad editor for one already-persisted refine marker.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the refine and attach live redraw, validation, and persistence.
        """
        pending_ids = _runtime.pending_refine_edit.consume()
        try:
            if pending_ids is None:
                raise RuntimeError("No refine point was selected for editing.")
            harness_id, control_id = pending_ids
            application = adsk.core.Application.get()
            _require_active_design(application)
            definition = loads(
                _create_harness_gateway(application).read_harness_definition(harness_id)
            )
            control = next(
                (item for item in definition.controls if item.control_id == control_id),
                None,
            )
            if (
                control is None
                or control.kind is not ControlKind.REFINE
                or control.refine_geometry is None
            ):
                raise ValueError("Selected refine point no longer exists.")
            geometry = control.refine_geometry
            triad = _add_refine_transform_input(args.command.commandInputs, geometry)
            triad.hideAllScaling()
            triad.setTranslateVisibility(True)
            triad.setPlanarMoveVisibility(True)
            triad.setRotateVisibility(True)
            triad.isOriginTranslationVisible = True
            triad.isVisible = True
            _add_refine_radius_input(
                args.command.commandInputs,
                geometry.display_radius_mm,
            )
            state = _EditRefineCommandState(harness_id, control_id, geometry)
            activate_handler = _RefineActivateHandler()
            input_handler = _EditRefineInputChangedHandler(state)
            preview_handler = _EditRefineExecutePreviewHandler(state)
            validate_handler = _EditRefineValidateInputsHandler()
            execute_handler = _EditRefineExecuteHandler(state)
            command_handlers: list[object] = [
                activate_handler,
                input_handler,
                preview_handler,
                validate_handler,
                execute_handler,
            ]
            destroyed = _EditRefineDestroyedHandler(command_handlers)
            if not args.command.activate.add(activate_handler):
                raise RuntimeError("Fusion could not start the refine edit preview.")
            if not args.command.inputChanged.add(input_handler):
                raise RuntimeError("Fusion could not watch refine edits.")
            if not args.command.executePreview.add(preview_handler):
                raise RuntimeError("Fusion could not preview refine edits.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate refine edits.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save refine edits.")
            if not args.command.destroy.add(destroyed):
                raise RuntimeError("Fusion could not register refine edit cleanup.")
            _runtime.handler_registry.retain(*command_handlers, destroyed)
            application.activeViewport.refresh()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            application = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is not None:
                clear_refine_spine(design)
                _reconcile_active_refines(application)
            _report_failure("open Edit Refine Point")
            raise


class _RefineActiveSelectionHandler(adsk.core.ActiveSelectionEventHandler):
    """
    Open the transform editor when a persistent refine marker is selected.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ActiveSelectionEventArgs) -> None:
        """
        Resolve one selected marker by its graphics-group and control identities.
        """
        try:
            selections = args.currentSelection
            if len(selections) != 1:
                return
            entity = selections[0].entity
            parent = getattr(entity, "parent", None)
            if getattr(parent, "id", None) != REFINE_GRAPHICS_GROUP_ID:
                return
            control_id = UUID(entity.id)
            application = adsk.core.Application.get()
            results = load_harnesses(_create_harness_gateway(application))
            match = None
            for result in results:
                definition = result.definition
                if definition is None:
                    continue
                if any(
                    control.control_id == control_id and control.kind is ControlKind.REFINE
                    for control in definition.controls
                ):
                    match = (definition.harness_id, control_id)
                    break
            if match is None:
                return
            application.userInterface.activeSelections.clear()
            _open_refine_edit_command(application, *match)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("select refine point")


def _read_refine_placement(
    command_inputs: adsk.core.CommandInputs,
    spine: PathwaySpine,
) -> RefinePlacement:
    """
    Read a selected spine point and marker radius in millimeters.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(REFINE_SPINE_INPUT_ID)
    )
    radius_input = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select one point on the pathway spine.")
    radius_mm = _read_refine_radius_mm(radius_input)
    selected_point = _selected_refine_point_mm(selection_input)
    if selected_point is None:
        raise ValueError("Select a point on the displayed pathway spine.")
    return place_refine(spine, selected_point, radius_mm)


def _add_refine_radius_input(
    command_inputs: adsk.core.CommandInputs,
    initial_radius_mm: float = MINIMUM_REFINE_RADIUS_MM,
) -> adsk.core.DistanceValueCommandInput:
    """
    Add a radius manipulator that starts at or above the supported minimum.
    """
    clamped_radius_mm = max(float(initial_radius_mm), MINIMUM_REFINE_RADIUS_MM)
    radius_input = command_inputs.addDistanceValueCommandInput(
        REFINE_RADIUS_INPUT_ID,
        "Marker Radius",
        adsk.core.ValueInput.createByString(f"{clamped_radius_mm:g} mm"),
    )
    if radius_input is None:
        raise RuntimeError("Fusion could not create the refine-radius input.")
    radius_input.minimumValue = MINIMUM_REFINE_RADIUS_MM / 10.0
    radius_input.isMinimumValueInclusive = True
    return radius_input


def _read_refine_radius_mm(
    radius_input: Optional[adsk.core.DistanceValueCommandInput],
) -> float:
    """
    Read a valid Fusion distance and clamp transient subminimum values.
    """
    if radius_input is None or not radius_input.isValidExpression:
        raise ValueError("Refine marker radius must be valid.")
    return max(radius_input.value * 10.0, MINIMUM_REFINE_RADIUS_MM)


def _refine_geometry_transform(geometry: RefineGeometry) -> adsk.core.Matrix3D:
    """
    Convert saved millimeter geometry into a centimeter-based Fusion triad.
    """
    u_direction = Vector3(*geometry.u_direction)
    v_direction = Vector3(*geometry.v_direction)
    tangent = unit(cross(u_direction, v_direction))
    transform = adsk.core.Matrix3D.create()
    if transform is None or not transform.setWithCoordinateSystem(
        adsk.core.Point3D.create(*(value / 10.0 for value in geometry.origin_mm)),
        adsk.core.Vector3D.create(*geometry.u_direction),
        adsk.core.Vector3D.create(*geometry.v_direction),
        adsk.core.Vector3D.create(tangent.x, tangent.y, tangent.z),
    ):
        raise RuntimeError("Fusion could not orient the refine transform controls.")
    return transform


def _add_refine_transform_input(
    command_inputs: adsk.core.CommandInputs,
    geometry: RefineGeometry,
) -> adsk.core.TriadCommandInput:
    """
    Add a triad and explicitly initialize its writable world transform.

    Fusion can ignore the initial matrix passed to ``addTriadCommandInput``;
    assigning the same matrix to ``transform`` prevents the dialog and the first
    manipulation from falling back to the global origin.
    """
    initial_transform = _refine_geometry_transform(geometry)
    triad = command_inputs.addTriadCommandInput(
        REFINE_TRANSFORM_INPUT_ID,
        initial_transform,
    )
    if triad is None:
        raise RuntimeError("Fusion could not create the refine transform controls.")
    triad.transform = initial_transform
    return triad


def _read_edited_refine_geometry(command_inputs: adsk.core.CommandInputs) -> RefineGeometry:
    """
    Read a rigid triad and marker radius as persistent millimeter geometry.
    """
    triad = adsk.core.TriadCommandInput.cast(command_inputs.itemById(REFINE_TRANSFORM_INPUT_ID))
    radius = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if triad is None or not triad.isValidExpressions:
        raise ValueError("Refine position and rotation must be valid.")
    radius_mm = _read_refine_radius_mm(radius)
    origin, u_direction, v_direction, _tangent = triad.transform.getAsCoordinateSystem()
    return RefineGeometry(
        origin_mm=(origin.x * 10.0, origin.y * 10.0, origin.z * 10.0),
        u_direction=(u_direction.x, u_direction.y, u_direction.z),
        v_direction=(v_direction.x, v_direction.y, v_direction.z),
        display_radius_mm=radius_mm,
    )


def _reconcile_active_refines(application: adsk.core.Application) -> None:
    """
    Recreate persistent refine markers from every healthy active definition.
    """
    design = _require_active_design(application)
    results = load_harnesses(_create_harness_gateway(application))
    definitions = tuple(result.definition for result in results if result.definition is not None)
    reconcile_refine_graphics(design, definitions)


def _finalize_refine_graphics(application: adsk.core.Application) -> None:
    """
    Replace command-only graphics with persistent markers in the active design.
    """
    design = adsk.fusion.Design.cast(application.activeProduct)
    if design is None:
        return
    clear_refine_spine(design)
    _reconcile_active_refines(application)
    application.activeViewport.refresh()


EditRefineCreatedHandler = _EditRefineCreatedHandler
RefineActiveSelectionHandler = _RefineActiveSelectionHandler
RefineCreatedHandler = _RefineCreatedHandler
reconcile_active_refines = _reconcile_active_refines
