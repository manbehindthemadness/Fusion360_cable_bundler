"""
Fusion command controllers for refines.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import add_pathway_refine, load_harnesses, update_pathway_refine
from ....domain import ControlKind, RefineGeometry, loads
from ....routing import Vector3
from ....routing.geometry import cross, unit
from ...refine_graphics import (
    DEFAULT_REFINE_RADIUS_MM,
    REFINE_GRAPHICS_GROUP_ID,
    REFINE_SPINE_ENTITY_ID,
    PathwaySpine,
    RefinePlacement,
    build_pathway_spine,
    clear_candidate_refine,
    clear_refine_spine,
    draw_candidate_refine,
    draw_pathway_spine,
    draw_refine_editor,
    place_refine,
    reconcile_refine_graphics,
    update_candidate_refine,
    update_refine_editor,
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


@dataclass
class _RefineCommandState:
    """
    Share the temporary spine and current placement across command handlers.
    """

    harness_id: UUID
    pathway_id: UUID
    spine: PathwaySpine
    group: adsk.fusion.CustomGraphicsGroup
    placement: Optional[RefinePlacement] = None
    candidate: Optional[adsk.fusion.CustomGraphicsLines] = None


class _RefinePreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Restrict Custom Graphics selection to the command-owned pathway spine.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Reject persistent markers and unrelated selectable graphics.
        """
        selection = args.selection
        entity = selection.entity if selection is not None else None
        args.isSelectable = getattr(entity, "id", None) == REFINE_SPINE_ENTITY_ID


def _update_refine_placement(
    state: _RefineCommandState,
    command_inputs: adsk.core.CommandInputs,
    *,
    position_manipulator: bool = True,
) -> None:
    """
    Synchronize selection, radius input, and the transformable candidate marker.
    """
    radius_input = adsk.core.DistanceValueCommandInput.cast(
        command_inputs.itemById(REFINE_RADIUS_INPUT_ID)
    )
    if radius_input is None:
        raise RuntimeError("Refine radius input is unavailable.")
    try:
        placement = _read_refine_placement(command_inputs, state.spine)
    except ValueError:
        state.placement = None
        state.candidate = None
        radius_input.isEnabled = False
        radius_input.isVisible = False
        clear_candidate_refine(state.group)
        adsk.core.Application.get().activeViewport.refresh()
        return
    state.placement = placement
    radius_input.isEnabled = True
    radius_input.isVisible = True
    if position_manipulator:
        origin = placement.geometry.origin_mm
        direction = placement.geometry.u_direction
        if not radius_input.setManipulator(
            adsk.core.Point3D.create(*(coordinate / 10.0 for coordinate in origin)),
            adsk.core.Vector3D.create(*direction),
        ):
            raise RuntimeError("Fusion could not position the refine-radius manipulator.")
    if state.candidate is None or not state.candidate.isValid:
        state.candidate = draw_candidate_refine(state.group, placement.geometry)
    else:
        update_candidate_refine(state.candidate, placement.geometry)
    adsk.core.Application.get().activeViewport.refresh()


class _RefineInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Project the selected Custom Graphics point and redraw its marker.
    """

    def __init__(self, state: _RefineCommandState) -> None:
        """
        Retain the command-local placement state.
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
    ) -> None:
        """
        Retain placement state and its command inputs for drag notifications.
        """
        super().__init__()
        self._state = state
        self._command_inputs = command_inputs

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
        try:
            self._state.placement = _read_refine_placement(args.inputs, self._state.spine)
        except (AttributeError, TypeError, ValueError):
            self._state.placement = None
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
            placement = _read_refine_placement(args.command.commandInputs, self._state.spine)
            add_pathway_refine(
                self._state.harness_id,
                self._state.pathway_id,
                placement.insertion_index,
                placement.geometry,
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._state.harness_id)
            _reconcile_active_refines(application)
            application.activeViewport.refresh()
            _send_palette_state(application, f"Added refine point. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add refine point failed: {error}\n{traceback.format_exc()}")


class _RefineDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Remove command-only graphics and release its short-lived handlers.
    """

    def __init__(self, handlers: list[object]) -> None:
        """
        Retain the handlers that must remain alive until destruction.
        """
        super().__init__()
        self._command_handlers = handlers

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Clear the temporary spine for Save and Cancel alike.
        """
        application = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            clear_refine_spine(design)
            application.activeViewport.refresh()
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
        try:
            if pending_ids is None:
                raise RuntimeError("No pathway was selected for refine placement.")
            harness_id, pathway_id = pending_ids
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            definition = loads(
                _create_harness_gateway(application).read_harness_definition(harness_id)
            )
            spine = build_pathway_spine(design, definition, pathway_id)
            group, _lines = draw_pathway_spine(design, spine)
            selection_input = args.command.commandInputs.addSelectionInput(
                REFINE_SPINE_INPUT_ID,
                "Pathway Point",
                "Select a point on the cyan pathway spine",
            )
            if selection_input is None or not selection_input.addSelectionFilter("CustomGraphics"):
                raise RuntimeError("Fusion could not configure refine-path selection.")
            if not selection_input.setSelectionLimits(1, 1):
                raise RuntimeError("Fusion could not limit refine-path selection.")
            radius_input = args.command.commandInputs.addDistanceValueCommandInput(
                REFINE_RADIUS_INPUT_ID,
                "Marker Radius",
                adsk.core.ValueInput.createByString(f"{DEFAULT_REFINE_RADIUS_MM:g} mm"),
            )
            if radius_input is None:
                raise RuntimeError("Fusion could not create the refine-radius input.")
            radius_input.isVisible = False
            radius_input.isEnabled = False
            state = _RefineCommandState(harness_id, pathway_id, spine, group)
            preselect_handler = _RefinePreSelectHandler()
            input_handler = _RefineInputChangedHandler(state)
            drag_handler = _RefineMouseDragHandler(state, args.command.commandInputs)
            validate_handler = _RefineValidateInputsHandler(state)
            execute_handler = _RefineExecuteHandler(state)
            command_handlers: list[object] = [
                preselect_handler,
                input_handler,
                drag_handler,
                validate_handler,
                execute_handler,
            ]
            destroyed = _RefineDestroyedHandler(command_handlers)
            if not args.command.preSelect.add(preselect_handler):
                raise RuntimeError("Fusion could not filter refine-path selection.")
            if not args.command.inputChanged.add(input_handler):
                raise RuntimeError("Fusion could not watch refine placement.")
            if not args.command.mouseDrag.add(drag_handler):
                raise RuntimeError("Fusion could not watch refine radius dragging.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate refine placement.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save refine placement.")
            if not args.command.destroy.add(destroyed):
                raise RuntimeError("Fusion could not register refine cleanup.")
            _runtime.handler_registry.retain(*command_handlers, destroyed)
            application.activeViewport.refresh()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            application = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(application.activeProduct)
            if design is not None:
                clear_refine_spine(design)
            _report_failure("open Add Refine Point")
            raise


@dataclass
class _EditRefineCommandState:
    """
    Share the edited refine identity and temporary marker across handlers.
    """

    harness_id: UUID
    control_id: UUID
    group: adsk.fusion.CustomGraphicsGroup
    geometry: RefineGeometry


def _preview_edited_refine(
    state: _EditRefineCommandState,
    command_inputs: adsk.core.CommandInputs,
) -> None:
    """
    Apply current triad and radius values to the live editor marker.
    """
    geometry = _read_edited_refine_geometry(command_inputs)
    state.geometry = geometry
    update_refine_editor(state.group, geometry)
    adsk.core.Application.get().activeViewport.refresh()


class _EditRefineInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Update the editor marker throughout graphical and typed manipulation.
    """

    def __init__(self, state: _EditRefineCommandState) -> None:
        """
        Retain the command-local edit state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Apply the changed command values directly to the existing marker.
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
        Reapply current geometry when Fusion requests a command preview.
        """
        try:
            _preview_edited_refine(self._state, args.command.commandInputs)
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
            _send_palette_state(application, f"Updated refine point. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Edit refine point failed: {error}\n{traceback.format_exc()}")


class _EditRefineDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Restore persistent refine graphics after Save or Cancel.
    """

    def __init__(self, handlers: list[object]) -> None:
        """
        Retain the command handlers until destruction.
        """
        super().__init__()
        self._command_handlers = handlers

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Remove the editor marker and redraw all saved refine geometry.
        """
        application = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(application.activeProduct)
        if design is not None:
            clear_refine_spine(design)
            _reconcile_active_refines(application)
            application.activeViewport.refresh()
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
            design = _require_active_design(application)
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
            group = draw_refine_editor(design, control_id, geometry)
            triad = _add_refine_transform_input(args.command.commandInputs, geometry)
            triad.hideAllScaling()
            triad.setTranslateVisibility(True)
            triad.setPlanarMoveVisibility(True)
            triad.setRotateVisibility(True)
            triad.isOriginTranslationVisible = True
            triad.isVisible = True
            radius = args.command.commandInputs.addDistanceValueCommandInput(
                REFINE_RADIUS_INPUT_ID,
                "Marker Radius",
                adsk.core.ValueInput.createByString(f"{geometry.display_radius_mm:g} mm"),
            )
            if radius is None:
                raise RuntimeError("Fusion could not create the refine-radius input.")
            state = _EditRefineCommandState(harness_id, control_id, group, geometry)
            input_handler = _EditRefineInputChangedHandler(state)
            preview_handler = _EditRefineExecutePreviewHandler(state)
            validate_handler = _EditRefineValidateInputsHandler()
            execute_handler = _EditRefineExecuteHandler(state)
            command_handlers: list[object] = [
                input_handler,
                preview_handler,
                validate_handler,
                execute_handler,
            ]
            destroyed = _EditRefineDestroyedHandler(command_handlers)
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
    if radius_input is None or not radius_input.isValidExpression or radius_input.value <= 0.0:
        raise ValueError("Refine marker radius must be positive.")
    selection = selection_input.selection(0)
    if selection is None:
        raise ValueError("Select a point on the displayed pathway spine.")
    entity = selection.entity
    point = selection.point
    if getattr(entity, "id", None) != REFINE_SPINE_ENTITY_ID:
        raise ValueError("Select a point on the displayed pathway spine.")
    if point is None:
        raise ValueError("Select a point on the displayed pathway spine.")
    selected_point = Vector3(
        point.x * 10.0,
        point.y * 10.0,
        point.z * 10.0,
    )
    return place_refine(spine, selected_point, radius_input.value * 10.0)


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
    if radius is None or not radius.isValidExpression or radius.value <= 0.0:
        raise ValueError("Refine marker radius must be positive.")
    origin, u_direction, v_direction, _tangent = triad.transform.getAsCoordinateSystem()
    return RefineGeometry(
        origin_mm=(origin.x * 10.0, origin.y * 10.0, origin.z * 10.0),
        u_direction=(u_direction.x, u_direction.y, u_direction.z),
        v_direction=(v_direction.x, v_direction.y, v_direction.z),
        display_radius_mm=radius.value * 10.0,
    )


def _reconcile_active_refines(application: adsk.core.Application) -> None:
    """
    Recreate persistent refine markers from every healthy active definition.
    """
    design = _require_active_design(application)
    results = load_harnesses(_create_harness_gateway(application))
    definitions = tuple(result.definition for result in results if result.definition is not None)
    reconcile_refine_graphics(design, definitions)


EditRefineCreatedHandler = _EditRefineCreatedHandler
RefineActiveSelectionHandler = _RefineActiveSelectionHandler
RefineCreatedHandler = _RefineCreatedHandler
reconcile_active_refines = _reconcile_active_refines
