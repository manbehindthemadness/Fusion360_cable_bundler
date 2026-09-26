"""
Native multi-target selection for contacts on one Interface.
"""

from __future__ import annotations

import traceback
from typing import Any
from uuid import UUID, uuid4

# noinspection PyUnresolvedReferences
import adsk.core

from ....application import add_interface_contacts
from ....application.interface_contact_rows import ContactSelectionMode
from ....domain import InterfaceContact, InterfaceDefinition, loads
from ...attachment_targets import attachment_target_kind
from ...interface_contact_rows import collect_contact_row, validate_row_endpoints
from ..constants import INTERFACE_CONTACTS_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design

_FILTERS = (
    "Profiles",
    "Faces",
    "JointOrigins",
    "CircularEdges",
    "ConstructionPoints",
    "SketchPoints",
)


def _selected_entities(inputs: adsk.core.CommandInputs) -> tuple[Any, ...]:
    """
    Validate all picker selections in their explicit order.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        inputs.itemById(INTERFACE_CONTACTS_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount < 1:
        raise ValueError("Select at least one contact on this Interface.")
    entities: list[Any] = []
    tokens: set[str] = set()
    for index in range(selection_input.selectionCount):
        selection = selection_input.selection(index)
        entity = getattr(selection, "entity", None)
        kind = attachment_target_kind(entity) if entity is not None else None
        token = getattr(entity, "entityToken", "")
        if kind is None or not isinstance(token, str) or not token.strip():
            raise ValueError("Selected contact is not a supported persistent connection target.")
        if token.strip() in tokens:
            raise ValueError("Select each contact only once.")
        tokens.add(token.strip())
        entities.append(entity)
    return tuple(entities)


def _selected_contacts(
    inputs: adsk.core.CommandInputs,
    mode: ContactSelectionMode = ContactSelectionMode.MANUAL,
) -> tuple[InterfaceContact, ...]:
    """
    Collect manual picks or the matching finite row before assigning new identities.
    """
    entities = _selected_entities(inputs)
    if mode is ContactSelectionMode.ROW:
        if len(entities) != 2:
            raise ValueError("Pick the first and last targets in the row.")
        row = collect_contact_row(*entities)
        return tuple(InterfaceContact(uuid4(), item.kind, item.token) for item in row)
    contacts = []
    for entity in entities:
        kind = attachment_target_kind(entity)
        if kind is None:
            raise ValueError("Selected contact is no longer available.")
        contacts.append(InterfaceContact(uuid4(), kind, entity.entityToken.strip()))
    return tuple(contacts)


class _ValidateHandler(adsk.core.ValidateInputsEventHandler):
    """
    Keep completion disabled until at least one valid contact is selected.
    """

    def __init__(self, mode: ContactSelectionMode = ContactSelectionMode.MANUAL) -> None:
        """
        Retain the picker policy for endpoint-only row validation.
        """
        super().__init__()
        self._mode = mode

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Validate the complete current selection.
        """
        try:
            entities = _selected_entities(args.inputs)
            if self._mode is ContactSelectionMode.ROW:
                if len(entities) != 2:
                    raise ValueError("Pick the first and last targets in the row.")
                validate_row_endpoints(*entities)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _ExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist selected contacts in Fusion's command transaction.
    """

    def __init__(
        self,
        harness_id: UUID,
        interface_id: UUID,
        mode: ContactSelectionMode = ContactSelectionMode.MANUAL,
    ) -> None:
        """
        Retain the selected Interface identity.
        """
        super().__init__()
        self._harness_id = harness_id
        self._interface_id = interface_id
        self._mode = mode

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Append picked targets and refresh the palette projection.
        """
        application = adsk.core.Application.get()
        try:
            contacts = _selected_contacts(args.command.commandInputs, self._mode)
            add_interface_contacts(
                self._harness_id, self._interface_id, contacts, _create_harness_gateway(application)
            )
            _send_palette_state(application, f"Added {len(contacts)} Interface contacts.")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Select Interface Contacts failed: {error}\n{traceback.format_exc()}")


class SelectInterfaceContactsCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the Fusion picker for every connection-compatible target type.
    """

    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the Interface and wire command-lifetime handlers.
        """
        request = _runtime.pending_interface_contacts.consume()
        if request is None:
            raise RuntimeError("No Interface was selected for contact selection.")
        harness_id, interface_id, mode = request
        application = adsk.core.Application.get()
        _require_active_design(application)
        gateway = _create_harness_gateway(application)
        definition = loads(gateway.read_harness_definition(harness_id))
        interface: InterfaceDefinition | None = next(
            (item for item in definition.interfaces if item.interface_id == interface_id), None
        )
        if interface is None:
            raise ValueError("Selected Interface no longer exists.")
        picker = args.command.commandInputs.addSelectionInput(
            INTERFACE_CONTACTS_INPUT_ID,
            "Row endpoints" if mode is ContactSelectionMode.ROW else "Interface Contacts",
            "Select the first and last targets; OK collects matching targets between them"
            if mode is ContactSelectionMode.ROW
            else "Select one or more connection-compatible targets",
        )
        if picker is None or not all(picker.addSelectionFilter(item) for item in _FILTERS):
            raise RuntimeError("Fusion could not configure Interface contact selection.")
        limits = (2, 2) if mode is ContactSelectionMode.ROW else (1, 0)
        if not picker.setSelectionLimits(*limits):
            raise RuntimeError("Fusion could not allow multiple Interface contacts.")
        handlers = (
            _ValidateHandler(mode),
            _ExecuteHandler(harness_id, interface_id, mode),
        )
        for event, handler in zip(
            (args.command.validateInputs, args.command.execute),
            handlers,
        ):
            if not event.add(handler):
                raise RuntimeError("Fusion could not attach an Interface contact handler.")
        _runtime.retain_command_handlers(args.command, *handlers)
