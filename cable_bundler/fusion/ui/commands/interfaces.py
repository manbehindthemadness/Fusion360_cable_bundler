"""
Native Fusion selection command for creating reference-only Interfaces.
"""

from __future__ import annotations

import traceback
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import add_interface
from ....domain import InterfaceTarget, InterfaceTargetKind, loads
from ..constants import INTERFACE_NAME_INPUT_ID, INTERFACE_TARGETS_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)


def _interface_kind(entity: object) -> InterfaceTargetKind | None:
    """
    Classify the exact entity selected by Fusion's filtered picker.
    """
    if adsk.fusion.BRepBody.cast(entity) is not None:
        return InterfaceTargetKind.BODY
    if adsk.fusion.Sketch.cast(entity) is not None:
        return InterfaceTargetKind.SKETCH
    if adsk.fusion.Occurrence.cast(entity) is not None:
        return InterfaceTargetKind.OCCURRENCE
    return None


def _selected_entities(command_inputs: adsk.core.CommandInputs) -> tuple[object, ...]:
    """
    Return the picker selections in their user-controlled order.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(INTERFACE_TARGETS_INPUT_ID)
    )
    if selection_input is None:
        return ()
    return tuple(
        selection.entity
        for index in range(selection_input.selectionCount)
        for selection in (selection_input.selection(index),)
        if selection is not None and selection.entity is not None
    )


def _interface_targets(command_inputs: adsk.core.CommandInputs) -> tuple[InterfaceTarget, ...]:
    """
    Validate the complete selected group and return persistent references.
    """
    entities = _selected_entities(command_inputs)
    if not entities:
        raise ValueError("Select at least one body, sketch, or component occurrence.")
    targets: list[InterfaceTarget] = []
    for entity in entities:
        kind = _interface_kind(entity)
        token = getattr(entity, "entityToken", "")
        if kind is None or not isinstance(token, str) or not token.strip():
            raise ValueError("Selected Interface geometry cannot be saved.")
        targets.append(InterfaceTarget(kind, token.strip()))
    if any(target.kind is InterfaceTargetKind.OCCURRENCE for target in targets):
        if len(targets) != 1:
            raise ValueError("Select one component occurrence by itself.")
    if len({target.entity_token for target in targets}) != len(targets):
        raise ValueError("Select each Interface target only once.")
    return tuple(targets)


def _interface_name(command_inputs: adsk.core.CommandInputs) -> str:
    """
    Read a required editable Interface name.
    """
    name_input = adsk.core.StringValueCommandInput.cast(
        command_inputs.itemById(INTERFACE_NAME_INPUT_ID)
    )
    name = getattr(name_input, "value", "")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Interface name must not be empty.")
    return name.strip()


class _AddInterfaceInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Follow the first target's name until the user edits the name manually.
    """

    def __init__(self) -> None:
        """
        Track whether the suggested name remains automatic.
        """
        super().__init__()
        self._suggested_name = "Interface 01"
        self._updating = False
        self._user_named = False

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Update the name only while it still follows picker selection.
        """
        input_id = getattr(args.input, "id", None)
        if input_id == INTERFACE_NAME_INPUT_ID and not self._updating:
            name_input = adsk.core.StringValueCommandInput.cast(
                args.inputs.itemById(INTERFACE_NAME_INPUT_ID)
            )
            self._user_named = name_input is not None and name_input.value != self._suggested_name
        if input_id != INTERFACE_TARGETS_INPUT_ID or self._user_named:
            return
        name_input = adsk.core.StringValueCommandInput.cast(
            args.inputs.itemById(INTERFACE_NAME_INPUT_ID)
        )
        entities = _selected_entities(args.inputs)
        if name_input is None:
            return
        name = getattr(entities[0], "name", "") if entities else ""
        suggested = name.strip() if isinstance(name, str) and name.strip() else "Interface 01"
        self._suggested_name = suggested
        self._updating = True
        try:
            name_input.value = suggested
        finally:
            self._updating = False


class _AddInterfacePreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Keep component occurrences separate from body and sketch groups.
    """

    def __init__(self, command_inputs: adsk.core.CommandInputs) -> None:
        """
        Retain the active selection input for compatibility checks.
        """
        super().__init__()
        self._command_inputs = command_inputs

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Reject unsupported or incompatible additional selections.
        """
        entity = args.selection.entity if args.selection is not None else None
        kind = _interface_kind(entity)
        existing = _selected_entities(self._command_inputs)
        existing_kinds = tuple(_interface_kind(item) for item in existing)
        args.isSelectable = (
            kind is not None
            and not (
                existing
                and (
                    kind is InterfaceTargetKind.OCCURRENCE
                    or InterfaceTargetKind.OCCURRENCE in existing_kinds
                )
            )
            and all(entity != item for item in existing)
        )


class _AddInterfaceValidateHandler(adsk.core.ValidateInputsEventHandler):
    """
    Enable completion only for one valid Interface group.
    """

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Check the current name and selection without changing the design.
        """
        try:
            _interface_name(args.inputs)
            _interface_targets(args.inputs)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddInterfaceExecuteHandler(adsk.core.CommandEventHandler):
    """
    Save one Interface inside Fusion's command transaction.
    """

    def __init__(self, harness_id: UUID) -> None:
        """
        Retain the palette-selected harness.
        """
        super().__init__()
        self._harness_id = harness_id

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Persist the selected references and refresh the palette.
        """
        application = adsk.core.Application.get()
        try:
            interface = add_interface(
                self._harness_id,
                _interface_name(args.command.commandInputs),
                _interface_targets(args.command.commandInputs),
                _create_harness_gateway(application),
            )
            _send_palette_state(application, f"Created Interface {interface.name}.")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add Interface failed: {error}\n{traceback.format_exc()}")


class AddInterfaceCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Create the native multi-selection picker for an Interface.
    """

    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the harness and retain command-lifetime event handlers.
        """
        harness_id = _runtime.pending_interface.consume()
        try:
            if harness_id is None:
                raise RuntimeError("No harness was selected for Interface creation.")
            application = adsk.core.Application.get()
            _require_active_design(application)
            loads(_create_harness_gateway(application).read_harness_definition(harness_id))
            inputs = args.command.commandInputs
            name_input = inputs.addStringValueInput(
                INTERFACE_NAME_INPUT_ID, "Interface Name", "Interface 01"
            )
            selection_input = inputs.addSelectionInput(
                INTERFACE_TARGETS_INPUT_ID,
                "Interface Targets",
                "Select bodies and sketches, or one component occurrence",
            )
            if name_input is None or selection_input is None:
                raise RuntimeError("Fusion could not create Interface command inputs.")
            if not all(
                selection_input.addSelectionFilter(item)
                for item in ("Bodies", "Sketches", "Occurrences")
            ):
                raise RuntimeError("Fusion could not configure Interface selection.")
            if not selection_input.setSelectionLimits(1, 0):
                raise RuntimeError("Fusion could not limit Interface selection.")
            handlers = (
                _AddInterfaceInputChangedHandler(),
                _AddInterfacePreSelectHandler(inputs),
                _AddInterfaceValidateHandler(),
                _AddInterfaceExecuteHandler(harness_id),
            )
            for event, handler in zip(
                (
                    args.command.inputChanged,
                    args.command.preSelect,
                    args.command.validateInputs,
                    args.command.execute,
                ),
                handlers,
            ):
                if not event.add(handler):
                    raise RuntimeError("Fusion could not initialize Interface selection.")
            _runtime.retain_command_handlers(args.command, *handlers)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Interface")
            raise
