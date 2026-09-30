"""
Pick an existing grouped cable end for batch contact connection.
"""

from __future__ import annotations

import json
import traceback
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application.batch_connect_interface_contacts import (
    batch_connect_and_associate_interface_contacts,
    batch_connect_interface_contacts,
)
from ....domain import (
    AttachmentTargetKind,
    CableEndShape,
    CableEndTarget,
    CableGroupType,
    HarnessDefinition,
    loads,
)
from ...attachment_targets import attachment_target_kind, attachment_target_name
from ...cable_solids import refresh_generated_cable_groups_for_connection
from ...ribbon_connections import number_ribbon_connections
from ..auto_connect_requests import AutoConnectApplyRequest, AutoConnectPickRequest
from ..constants import AUTO_CONNECT_END_INPUT_ID, PALETTE_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design
from ..viewport import _refresh_active_preview
from .attachments import _read_face_parameters
from .end_guides import end_guide_shape
from .pathways import _native_fusion_entity


def _grouped_end_guides(
    definition: HarnessDefinition, design: adsk.fusion.Design
) -> tuple[tuple[UUID, Optional[UUID], object], ...]:
    """
    Resolve grouped closed/open end guides and connected profile nodes.
    """
    groups_by_connection = {
        connection_id: group
        for group in definition.cable_groups
        for connection_id in group.connection_ids
    }
    result: list[tuple[UUID, Optional[UUID], object]] = []
    for connection in definition.connections:
        group = groups_by_connection.get(connection.connection_id)
        if group is None:
            continue
        candidates = ((None, connection.member_tokens[0]),) + tuple(
            (item.attachment_id, item.entity_token)
            for item in connection.attachments
            if item.target_kind is AttachmentTargetKind.PROFILE
        )
        for parent_id, token in candidates:
            for entity in design.findEntityByToken(token) or ():
                expected_shape = (
                    CableEndShape.OPEN
                    if group.group_type is CableGroupType.RIBBON
                    else CableEndShape.CLOSED
                )
                eligible = (
                    end_guide_shape(entity) is expected_shape
                    if parent_id is None
                    else adsk.fusion.Profile.cast(entity) is not None
                )
                if eligible:
                    result.append(
                        (connection.connection_id, parent_id, _native_fusion_entity(entity))
                    )
                    break
    return tuple(result)


def _picked_ending(
    entity: object, candidates: tuple[tuple[UUID, Optional[UUID], object], ...]
) -> tuple[UUID, Optional[UUID]]:
    """
    Match one mouse selection to a grouped guide or connected profile node.
    """
    native = _native_fusion_entity(entity) if end_guide_shape(entity) is not None else None
    matches = tuple(
        (connection_id, parent_id)
        for connection_id, parent_id, candidate in candidates
        if native == candidate
    )
    if len(matches) != 1:
        raise ValueError("Select one ending profile or open curve on an existing cable group.")
    return matches[0]


def _selected_ending(
    inputs: adsk.core.CommandInputs,
    candidates: tuple[tuple[UUID, Optional[UUID], object], ...],
) -> tuple[UUID, Optional[UUID]]:
    """
    Read one eligible end guide from the native picker.
    """
    picker = adsk.core.SelectionCommandInput.cast(inputs.itemById(AUTO_CONNECT_END_INPUT_ID))
    if picker is None or picker.selectionCount != 1:
        raise ValueError("Select one grouped cable ending.")
    selection = picker.selection(0)
    return _picked_ending(getattr(selection, "entity", None), candidates)


class _PreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Reject shapes outside grouped ends and their connected profile nodes.
    """

    def __init__(self, candidates: tuple[tuple[UUID, Optional[UUID], object], ...]) -> None:
        """
        Retain eligible end-guide identities.
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


def _contact_targets(
    definition: HarnessDefinition,
    design: adsk.fusion.Design,
    interface_id: UUID,
    contact_ids: tuple[UUID, ...],
) -> tuple[CableEndTarget, ...]:
    """
    Resolve saved contact identities against the current Fusion geometry.
    """
    interface = next(
        (item for item in definition.interfaces if item.interface_id == interface_id), None
    )
    if interface is None:
        raise ValueError("The selected Interface no longer exists.")
    contacts = {item.contact_id: item for item in interface.contacts}
    targets = []
    for contact_id in contact_ids:
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
    return tuple(targets)


class _PickExecuteHandler(adsk.core.CommandEventHandler):
    """
    Record a valid ending without editing the harness.
    """

    def __init__(
        self,
        request: AutoConnectPickRequest,
        candidates: tuple[tuple[UUID, Optional[UUID], object], ...],
    ) -> None:
        """
        Keep the picker request and eligible profiles until execution.
        """
        super().__init__()
        self.request = request
        self.candidates = candidates
        self.selected: Optional[tuple[UUID, Optional[UUID], str]] = None

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Resolve the selected end guide for the originating document.
        """
        application = adsk.core.Application.get()
        try:
            if application.activeDocument != self.request.document:
                raise ValueError("The active document changed; reopen Auto Connect.")
            connection_id, parent_id = _selected_ending(args.command.commandInputs, self.candidates)
            definition = loads(
                _create_harness_gateway(application).read_harness_definition(
                    self.request.harness_id
                )
            )
            connection = next(
                (item for item in definition.connections if item.connection_id == connection_id),
                None,
            )
            if connection is None:
                raise ValueError("The selected cable ending no longer exists.")
            self.selected = (connection_id, parent_id, connection.name)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Auto Connect ending selection failed: {error}")


class _PickDestroyedHandler(adsk.core.CommandEventHandler):
    """
    Return a picked ending or cancellation after the native picker has finished.
    """

    def __init__(self, execute_handler: _PickExecuteHandler) -> None:
        """
        Retain the pick result until Fusion destroys the command.
        """
        super().__init__()
        self.execute_handler = execute_handler

    def notify(self, _args: adsk.core.CommandEventArgs) -> None:
        """
        Send the final picker result to the matching palette dialog.
        """
        application = adsk.core.Application.get()
        palette = application.userInterface.palettes.itemById(PALETTE_ID)
        if palette is None:
            return
        request = self.execute_handler.request
        result: dict[str, object] = {
            "harnessId": str(request.harness_id),
            "side": request.side,
            "requestId": request.request_id,
            "cancelled": self.execute_handler.selected is None,
        }
        if self.execute_handler.selected is not None:
            connection_id, parent_id, name = self.execute_handler.selected
            result.update(
                connectionId=str(connection_id),
                parentAttachmentId=str(parent_id) if parent_id is not None else None,
                name=name,
            )
        palette.sendInfoToHTML("auto_connect_ending_selected", json.dumps(result))


class _ApplyExecuteHandler(adsk.core.CommandEventHandler):
    """
    Resolve contact geometry and save the batch in one transaction.
    """

    def __init__(
        self,
        request: AutoConnectApplyRequest,
    ) -> None:
        """
        Retain the reviewed palette choices until the apply command executes.
        """
        super().__init__()
        self.request = request

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Revalidate the saved contacts and update affected cable geometry.
        """
        application = adsk.core.Application.get()
        try:
            if application.activeDocument != self.request.document:
                raise ValueError("The active document changed; reopen Auto Connect.")
            design = _require_active_design(application)
            connection_id = self.request.connection_id
            parent_attachment_id = self.request.parent_attachment_id
            target_ending = (
                (self.request.target_connection_id, self.request.target_parent_attachment_id)
                if self.request.target_interface_id is not None
                else None
            )
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(self.request.harness_id))
            eligible = {
                (item_id, attachment_id)
                for item_id, attachment_id, _guide in _grouped_end_guides(definition, design)
            }
            if (connection_id, parent_attachment_id) not in eligible or (
                target_ending is not None and target_ending not in eligible
            ):
                raise ValueError("A selected cable ending changed; choose it again.")
            targets = _contact_targets(
                definition, design, self.request.interface_id, self.request.contact_ids
            )
            if target_ending is None:
                count = batch_connect_interface_contacts(
                    self.request.harness_id,
                    self.request.interface_id,
                    connection_id,
                    self.request.contact_ids,
                    targets,
                    self.request.include_pins,
                    self.request.include_values,
                    self.request.diameter_mm,
                    gateway,
                    parent_attachment_id=parent_attachment_id,
                    normalize_definition=lambda candidate: number_ribbon_connections(
                        design, candidate
                    ),
                )
                summary = f"Connected {count} contacts."
            else:
                target_connection_id, target_parent_id = target_ending
                target_targets = _contact_targets(
                    definition,
                    design,
                    self.request.target_interface_id,
                    self.request.target_contact_ids,
                )
                first_count, second_count, associations = (
                    batch_connect_and_associate_interface_contacts(
                        self.request.harness_id,
                        self.request.interface_id,
                        connection_id,
                        self.request.contact_ids,
                        targets,
                        self.request.include_pins,
                        self.request.include_values,
                        self.request.diameter_mm,
                        self.request.target_interface_id,
                        target_connection_id,
                        self.request.target_contact_ids,
                        target_targets,
                        self.request.target_include_pins,
                        self.request.target_include_values,
                        self.request.target_diameter_mm,
                        gateway,
                        first_parent_attachment_id=parent_attachment_id,
                        second_parent_attachment_id=target_parent_id,
                        normalize_definition=lambda candidate: number_ribbon_connections(
                            design, candidate
                        ),
                    )
                )
                summary = (
                    f"Connected {first_count} and {second_count} contacts; "
                    f"associated {associations} matching pins."
                )
            refreshed = loads(gateway.read_harness_definition(self.request.harness_id))
            refresh_generated_cable_groups_for_connection(
                design,
                gateway.harness_component(self.request.harness_id),
                refreshed,
                connection_id,
            )
            if target_ending is not None:
                refresh_generated_cable_groups_for_connection(
                    design,
                    gateway.harness_component(self.request.harness_id),
                    refreshed,
                    target_ending[0],
                )
            warning = _refresh_active_preview(application, self.request.harness_id)
            application.activeViewport.refresh()
            _send_palette_state(application, f"{summary} {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Auto Connect failed: {error}\n{traceback.format_exc()}")


class AutoConnectCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build either a read-only ending picker or an explicit apply command.
    """

    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Install only the handlers needed for the requested stage.
        """
        request = _runtime.pending_auto_connect.consume()
        if request is None:
            raise RuntimeError("No Auto Connect action was requested.")
        if isinstance(request, AutoConnectApplyRequest):
            handler = _ApplyExecuteHandler(request)
            if not args.command.execute.add(handler):
                raise RuntimeError("Fusion could not attach Auto Connect apply.")
            _runtime.retain_command_handlers(args.command, handler)
            return
        application = adsk.core.Application.get()
        if application.activeDocument != request.document:
            raise ValueError("The active document changed; reopen Auto Connect.")
        design = _require_active_design(application)
        definition = loads(
            _create_harness_gateway(application).read_harness_definition(request.harness_id)
        )
        candidates = _grouped_end_guides(definition, design)
        if not candidates:
            raise ValueError("No grouped cable ending guides are available.")
        picker = args.command.commandInputs.addSelectionInput(
            AUTO_CONNECT_END_INPUT_ID,
            "Cable Ending",
            "Pick a grouped cable end profile/open curve or connected profile node",
        )
        if picker is None or not picker.addSelectionFilter("Profiles"):
            raise RuntimeError("Fusion could not configure cable-ending selection.")
        if not picker.addSelectionFilter("SketchCurves"):
            raise RuntimeError("Fusion could not enable open-curve ending selection.")
        if not picker.setSelectionLimits(1, 1):
            raise RuntimeError("Fusion could not limit cable-ending selection.")
        execute = _PickExecuteHandler(request, candidates)
        destroyed = _PickDestroyedHandler(execute)
        handlers = (
            _PreSelectHandler(candidates),
            _ValidateHandler(candidates),
            execute,
        )
        for event, handler in zip(
            (args.command.preSelect, args.command.validateInputs, args.command.execute),
            handlers,
        ):
            if not event.add(handler):
                raise RuntimeError("Fusion could not attach Auto Connect selection.")
        if not args.command.destroy.add(destroyed):
            raise RuntimeError("Fusion could not return the selected cable ending.")
        _runtime.retain_command_handlers(args.command, *handlers, destroyed)
