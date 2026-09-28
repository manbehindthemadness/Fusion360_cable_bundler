"""
Pick an existing grouped cable end for batch contact connection.
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

from ....application.batch_connect_interface_contacts import batch_connect_interface_contacts
from ....domain import AttachmentTargetKind, CableEndTarget, HarnessDefinition, loads
from ...attachment_targets import attachment_target_kind, attachment_target_name
from ...cable_solids import refresh_generated_cable_groups_for_connection
from ..constants import AUTO_CONNECT_END_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design
from ..viewport import _refresh_active_preview
from .attachments import _read_face_parameters
from .pathways import _native_fusion_entity


@dataclass(frozen=True)
class _AutoConnectRequest:
    """
    Retain the palette selection until the native picker transaction finishes.
    """

    harness_id: UUID
    interface_id: UUID
    contact_ids: tuple[UUID, ...]
    include_pins: bool
    include_values: bool
    diameter_mm: Optional[float]
    document: object


def _grouped_end_profiles(
    definition: HarnessDefinition, design: adsk.fusion.Design
) -> tuple[tuple[UUID, Optional[UUID], object], ...]:
    """
    Resolve grouped end guides and connected profile nodes eligible as parents.
    """
    grouped_ids = {
        connection_id for group in definition.cable_groups for connection_id in group.connection_ids
    }
    result: list[tuple[UUID, Optional[UUID], object]] = []
    for connection in definition.connections:
        if connection.connection_id not in grouped_ids:
            continue
        candidates = ((None, connection.member_tokens[0]),) + tuple(
            (item.attachment_id, item.entity_token)
            for item in connection.attachments
            if item.target_kind is AttachmentTargetKind.PROFILE
        )
        for parent_id, token in candidates:
            for entity in design.findEntityByToken(token) or ():
                profile = adsk.fusion.Profile.cast(entity)
                if profile is not None:
                    result.append(
                        (connection.connection_id, parent_id, _native_fusion_entity(profile))
                    )
                    break
    return tuple(result)


def _picked_ending(
    entity: object, candidates: tuple[tuple[UUID, Optional[UUID], object], ...]
) -> tuple[UUID, Optional[UUID]]:
    """
    Match one mouse selection to a grouped end or its connected profile node.
    """
    profile = adsk.fusion.Profile.cast(entity)
    native = _native_fusion_entity(profile) if profile is not None else None
    matches = tuple(
        (connection_id, parent_id)
        for connection_id, parent_id, candidate in candidates
        if native == candidate
    )
    if len(matches) != 1:
        raise ValueError("Select one ending profile on an existing cable group.")
    return matches[0]


def _selected_ending(
    inputs: adsk.core.CommandInputs,
    candidates: tuple[tuple[UUID, Optional[UUID], object], ...],
) -> tuple[UUID, Optional[UUID]]:
    """
    Read one eligible profile from the native picker.
    """
    picker = adsk.core.SelectionCommandInput.cast(inputs.itemById(AUTO_CONNECT_END_INPUT_ID))
    if picker is None or picker.selectionCount != 1:
        raise ValueError("Select one grouped cable ending.")
    selection = picker.selection(0)
    return _picked_ending(getattr(selection, "entity", None), candidates)


class _PreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Reject profiles outside grouped ends and their connected profile nodes.
    """

    def __init__(self, candidates: tuple[tuple[UUID, Optional[UUID], object], ...]) -> None:
        """
        Retain eligible profile identities.
        """
        super().__init__()
        self.candidates = candidates

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Filter mouse-hover selection before it enters the picker.
        """
        try:
            _picked_ending(args.selection.entity, self.candidates)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            args.isSelectable = False
            return
        args.isSelectable = True


class _ValidateHandler(adsk.core.ValidateInputsEventHandler):
    """
    Enable completion only with one eligible grouped end.
    """

    def __init__(self, candidates: tuple[tuple[UUID, Optional[UUID], object], ...]) -> None:
        """
        Retain the same selection scope as preselection.
        """
        super().__init__()
        self.candidates = candidates

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Recheck selection before enabling OK.
        """
        try:
            _selected_ending(args.inputs, self.candidates)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _ExecuteHandler(adsk.core.CommandEventHandler):
    """
    Resolve contact geometry and save the batch in one transaction.
    """

    def __init__(
        self,
        request: _AutoConnectRequest,
        candidates: tuple[tuple[UUID, Optional[UUID], object], ...],
    ) -> None:
        """
        Retain the initiating document and eligible ends.
        """
        super().__init__()
        self.request = request
        self.candidates = candidates

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Revalidate the saved contacts and update affected cable geometry.
        """
        application = adsk.core.Application.get()
        try:
            if application.activeDocument != self.request.document:
                raise ValueError("The active document changed; reopen Auto Connect.")
            design = _require_active_design(application)
            connection_id, parent_attachment_id = _selected_ending(
                args.command.commandInputs, self.candidates
            )
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(self.request.harness_id))
            interface = next(
                (
                    item
                    for item in definition.interfaces
                    if item.interface_id == self.request.interface_id
                ),
                None,
            )
            if interface is None:
                raise ValueError("The selected Interface no longer exists.")
            contacts = {item.contact_id: item for item in interface.contacts}
            targets = []
            for contact_id in self.request.contact_ids:
                contact = contacts.get(contact_id)
                if contact is None:
                    raise ValueError("Selected contacts changed; reopen Auto Connect.")
                entity = next(
                    (
                        item
                        for item in design.findEntityByToken(contact.entity_token) or ()
                        if attachment_target_kind(item) is contact.kind
                    ),
                    None,
                )
                if entity is None:
                    raise ValueError("A selected contact's Fusion geometry is unavailable.")
                targets.append(
                    CableEndTarget(
                        contact.kind,
                        contact.entity_token,
                        attachment_target_name(entity, contact.kind),
                        parameters=(
                            _read_face_parameters(entity)
                            if contact.kind is AttachmentTargetKind.FACE
                            else ()
                        ),
                    )
                )
            count = batch_connect_interface_contacts(
                self.request.harness_id,
                self.request.interface_id,
                connection_id,
                self.request.contact_ids,
                tuple(targets),
                self.request.include_pins,
                self.request.include_values,
                self.request.diameter_mm,
                gateway,
                parent_attachment_id=parent_attachment_id,
            )
            refreshed = loads(gateway.read_harness_definition(self.request.harness_id))
            refresh_generated_cable_groups_for_connection(
                design,
                gateway.harness_component(self.request.harness_id),
                refreshed,
                connection_id,
            )
            warning = _refresh_active_preview(application, self.request.harness_id)
            application.activeViewport.refresh()
            _send_palette_state(application, f"Connected {count} contacts. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Auto Connect failed: {error}\n{traceback.format_exc()}")


class AutoConnectCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the grouped-end mouse picker for Auto Connect.
    """

    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Install picker filters and command-lifetime handlers.
        """
        request = _runtime.pending_auto_connect.consume()
        if request is None:
            raise RuntimeError("No contacts were selected for Auto Connect.")
        request = _AutoConnectRequest(*request)
        application = adsk.core.Application.get()
        design = _require_active_design(application)
        definition = loads(
            _create_harness_gateway(application).read_harness_definition(request.harness_id)
        )
        candidates = _grouped_end_profiles(definition, design)
        if not candidates:
            raise ValueError("No grouped cable ending profiles are available.")
        picker = args.command.commandInputs.addSelectionInput(
            AUTO_CONNECT_END_INPUT_ID,
            "Cable Ending",
            "Pick a grouped cable end guide or connected profile node",
        )
        if picker is None or not picker.addSelectionFilter("Profiles"):
            raise RuntimeError("Fusion could not configure cable-ending selection.")
        if not picker.setSelectionLimits(1, 1):
            raise RuntimeError("Fusion could not limit cable-ending selection.")
        handlers = (
            _PreSelectHandler(candidates),
            _ValidateHandler(candidates),
            _ExecuteHandler(request, candidates),
        )
        for event, handler in zip(
            (args.command.preSelect, args.command.validateInputs, args.command.execute),
            handlers,
        ):
            if not event.add(handler):
                raise RuntimeError("Fusion could not attach Auto Connect selection.")
        _runtime.retain_command_handlers(args.command, *handlers)
