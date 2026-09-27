"""
Native picker for copying projected fields from another saved Interface.
"""

from __future__ import annotations

import json
import traceback
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

from ....domain import InterfaceDefinition, loads
from ...interface_contact_projection_copy import (
    copy_projected_interface_details,
    picked_source_interface,
)
from ..constants import PALETTE_ID, SOURCE_INTERFACE_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design


def _selected_entity(inputs: adsk.core.CommandInputs) -> object:
    """
    Require exactly one clicked Interface target.
    """
    picker = adsk.core.SelectionCommandInput.cast(inputs.itemById(SOURCE_INTERFACE_INPUT_ID))
    if picker is None or picker.selectionCount != 1:
        raise ValueError("Select one other Interface target.")
    selection = picker.selection(0)
    entity = getattr(selection, "entity", None)
    if entity is None:
        raise ValueError("Select one other Interface target.")
    return entity


class _PreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Offer only geometry already owned by another saved Interface.
    """

    def __init__(
        self, design: object, interfaces: tuple[InterfaceDefinition, ...], destination_id: UUID
    ) -> None:
        """
        Retain the saved source identities for hover filtering.
        """
        super().__init__()
        self.design = design
        self.interfaces = interfaces
        self.destination_id = destination_id

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Reject arbitrary model geometry before it enters the picker.
        """
        try:
            picked_source_interface(
                self.design,
                self.interfaces,
                self.destination_id,
                args.selection.entity,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            args.isSelectable = False
            return
        args.isSelectable = True


class _ValidateHandler(adsk.core.ValidateInputsEventHandler):
    """
    Keep OK disabled without one unambiguous saved source Interface.
    """

    def __init__(
        self, design: object, interfaces: tuple[InterfaceDefinition, ...], destination_id: UUID
    ) -> None:
        """
        Retain the same selection scope as preselection.
        """
        super().__init__()
        self.design = design
        self.interfaces = interfaces
        self.destination_id = destination_id

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Recheck the complete picker selection before enabling execution.
        """
        try:
            picked_source_interface(
                self.design,
                self.interfaces,
                self.destination_id,
                _selected_entity(args.inputs),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _ExecuteHandler(adsk.core.CommandEventHandler):
    """
    Resolve the source again and copy projected fields transactionally.
    """

    def __init__(
        self,
        harness_id: UUID,
        destination_id: UUID,
        selected_ids: tuple[UUID, ...],
        copy_pins: bool,
        document: object,
    ) -> None:
        """
        Keep the initiating document and explicit contact scope.
        """
        super().__init__()
        self.harness_id = harness_id
        self.destination_id = destination_id
        self.selected_ids = selected_ids
        self.copy_pins = copy_pins
        self.document = document

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Persist only a uniquely projected copy within the original document.
        """
        application = adsk.core.Application.get()
        try:
            if application.activeDocument != self.document:
                raise ValueError("The active document changed; reopen Geo Import.")
            design = _require_active_design(application)
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(self.harness_id))
            source = picked_source_interface(
                design,
                definition.interfaces,
                self.destination_id,
                _selected_entity(args.command.commandInputs),
            )
            notice, conflicts = copy_projected_interface_details(
                application,
                self.harness_id,
                self.destination_id,
                source.interface_id,
                self.selected_ids,
                self.copy_pins,
            )
            _send_palette_state(application, notice)
            if conflicts:
                palette = application.userInterface.palettes.itemById(PALETTE_ID)
                if palette is None:
                    raise RuntimeError("Fusion could not show Interface projection conflicts.")
                palette.sendInfoToHTML(
                    "interface_projection_conflicts",
                    json.dumps(
                        {
                            "harnessId": str(self.harness_id),
                            "interfaceId": str(self.destination_id),
                            "sourceId": str(source.interface_id),
                            "contactIds": [str(item) for item in self.selected_ids],
                            "copyPins": self.copy_pins,
                            "conflicts": conflicts,
                        }
                    ),
                )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Geo Import Interface failed: {error}\n{traceback.format_exc()}")


class SelectSourceInterfaceCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build a single-target mouse picker restricted to saved Interfaces.
    """

    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the destination and install command-lifetime selection handlers.
        """
        request = _runtime.pending_source_interface.consume()
        if request is None:
            raise RuntimeError("No destination Interface was selected for Geo Import.")
        harness_id, destination_id, selected_ids, copy_pins, document = request
        application = adsk.core.Application.get()
        design = _require_active_design(application)
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        if all(item.interface_id != destination_id for item in definition.interfaces):
            raise ValueError("Destination Interface no longer exists.")
        picker = args.command.commandInputs.addSelectionInput(
            SOURCE_INTERFACE_INPUT_ID,
            "Source Interface",
            "Pick a saved target of another Interface in this harness",
        )
        if picker is None or not all(
            picker.addSelectionFilter(item) for item in ("Bodies", "Sketches", "Occurrences")
        ):
            raise RuntimeError("Fusion could not configure source Interface selection.")
        if not picker.setSelectionLimits(1, 1):
            raise RuntimeError("Fusion could not limit source Interface selection.")
        handlers = (
            _PreSelectHandler(design, definition.interfaces, destination_id),
            _ValidateHandler(design, definition.interfaces, destination_id),
            _ExecuteHandler(harness_id, destination_id, selected_ids, copy_pins, document),
        )
        for event, handler in zip(
            (args.command.preSelect, args.command.validateInputs, args.command.execute),
            handlers,
        ):
            if not event.add(handler):
                raise RuntimeError("Fusion could not attach source Interface selection.")
        _runtime.retain_command_handlers(args.command, *handlers)
