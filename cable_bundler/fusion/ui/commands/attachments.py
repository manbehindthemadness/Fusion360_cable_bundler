"""Native Fusion command for attaching one cable end to external geometry."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import attach_cable_end
from ....domain import AttachmentTargetKind, CableEndAttachment, loads
from ...attachment_targets import attachment_target_kind, attachment_target_name
from ..constants import CABLE_END_ATTACHMENT_NAME_INPUT_ID, CABLE_END_ATTACHMENT_TARGET_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design
from ..viewport import _refresh_active_preview
from .pathways import _native_fusion_entity


@dataclass(frozen=True)
class _AttachCableEndCommandState:
    """
    Retain the selected end and geometry that cannot target itself.
    """

    harness_id: UUID
    connection_id: UUID
    excluded_entities: tuple[object, ...]


def _read_face_parameters(face: object, point: object) -> tuple[float, float]:
    """
    Convert a clicked face position into persistent surface parameters.
    """
    evaluator = getattr(face, "evaluator", None)
    result = evaluator.getParameterAtPoint(point) if evaluator is not None else None
    if not isinstance(result, tuple) or len(result) != 2 or not result[0]:
        raise ValueError("Fusion could not locate the selected point on this face.")
    parameter = result[1]
    return float(parameter.x), float(parameter.y)


def _read_attachment_inputs(
    command_inputs: adsk.core.CommandInputs,
    state: _AttachCableEndCommandState,
) -> CableEndAttachment:
    """
    Validate the selected target and optional connection name.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(CABLE_END_ATTACHMENT_TARGET_INPUT_ID)
    )
    name_input = adsk.core.StringValueCommandInput.cast(
        command_inputs.itemById(CABLE_END_ATTACHMENT_NAME_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select exactly one connectable target.")
    selection = selection_input.selection(0)
    entity = selection.entity if selection is not None else None
    kind = attachment_target_kind(entity)
    token = getattr(entity, "entityToken", "")
    if kind is None or not isinstance(token, str) or not token.strip():
        raise ValueError("Selected geometry is not a supported persistent target.")
    native = _native_fusion_entity(entity)
    if any(native == excluded for excluded in state.excluded_entities):
        raise ValueError("A cable end cannot connect to its own guide geometry.")
    name = getattr(name_input, "value", "") if name_input is not None else ""
    if not isinstance(name, str):
        raise ValueError("Connection name must be text.")
    parameters = (
        _read_face_parameters(entity, getattr(selection, "point", None))
        if kind is AttachmentTargetKind.FACE
        else ()
    )
    return CableEndAttachment(
        target_kind=kind,
        entity_token=token.strip(),
        inherited_name=attachment_target_name(entity, kind),
        name=name.strip(),
        parameters=parameters,
    )


class _AttachCableEndPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Reject unsupported targets and the selected end's own guide geometry.
    """

    def __init__(self, state: _AttachCableEndCommandState) -> None:
        """
        Retain geometry excluded from attachment.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Allow only supported, externally owned target entities.
        """
        entity = args.selection.entity if args.selection is not None else None
        native = _native_fusion_entity(entity)
        args.isSelectable = attachment_target_kind(entity) is not None and all(
            native != excluded for excluded in self._state.excluded_entities
        )


class _AttachCableEndValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Enable execution after one target accepted by the picker filters is selected.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Avoid requiring persistent geometry data that Fusion defers until execution.
        """
        selection_input = adsk.core.SelectionCommandInput.cast(
            args.inputs.itemById(CABLE_END_ATTACHMENT_TARGET_INPUT_ID)
        )
        args.areInputsValid = selection_input is not None and selection_input.selectionCount == 1


class _AttachCableEndExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one attachment and refresh any visible route preview.
    """

    def __init__(self, state: _AttachCableEndCommandState) -> None:
        """
        Retain the attachment request context.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Save the selected target without modifying the target object itself.
        """
        application = adsk.core.Application.get()
        try:
            attachment = _read_attachment_inputs(args.command.commandInputs, self._state)
            attach_cable_end(
                self._state.harness_id,
                self._state.connection_id,
                attachment,
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._state.harness_id)
            application.activeViewport.refresh()
            _send_palette_state(
                application,
                f"Attached cable end to {attachment.display_name}. {warning}".strip(),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Connect cable end failed: {error}\n{traceback.format_exc()}")


class _AttachCableEndCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the supported-target picker and optional connection-name field.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve the selected cable end and register command-lifetime handlers.
        """
        request = _runtime.pending_cable_end_attachment.consume()
        if request is None:
            raise RuntimeError("No cable end was selected for connection.")
        harness_id, connection_id = request
        application = adsk.core.Application.get()
        design = _require_active_design(application)
        gateway = _create_harness_gateway(application)
        definition = loads(gateway.read_harness_definition(harness_id))
        connection = next(
            (item for item in definition.connections if item.connection_id == connection_id),
            None,
        )
        if connection is None:
            raise ValueError("Selected cable end no longer exists.")
        if connection.attachment is not None:
            raise ValueError("Selected cable end is already attached.")
        excluded_entities = tuple(
            _native_fusion_entity(entity)
            for token in connection.member_tokens
            for entity in (design.findEntityByToken(token) or ())
        )
        state = _AttachCableEndCommandState(harness_id, connection_id, excluded_entities)
        inputs = args.command.commandInputs
        selection_input = inputs.addSelectionInput(
            CABLE_END_ATTACHMENT_TARGET_INPUT_ID,
            "Connection Target",
            "Select a profile, face, joint origin, circular edge, construction point, or sketch point",
        )
        if selection_input is None:
            raise RuntimeError("Fusion could not create the connection-target picker.")
        for selection_filter in (
            "Profiles",
            "Faces",
            "JointOrigins",
            "CircularEdges",
            "ConstructionPoints",
            "SketchPoints",
        ):
            if not selection_input.addSelectionFilter(selection_filter):
                raise RuntimeError(
                    f"Fusion could not enable {selection_filter} connection targets."
                )
        if not selection_input.setSelectionLimits(1, 1):
            raise RuntimeError("Fusion could not limit connection-target selection.")
        if (
            inputs.addStringValueInput(
                CABLE_END_ATTACHMENT_NAME_INPUT_ID,
                "Connection Name",
                "",
            )
            is None
        ):
            raise RuntimeError("Fusion could not create the optional connection-name field.")
        preselect = _AttachCableEndPreSelectHandler(state)
        validate = _AttachCableEndValidateInputsHandler()
        execute = _AttachCableEndExecuteHandler(state)
        if not args.command.preSelect.add(preselect):
            raise RuntimeError("Fusion could not filter connection targets.")
        if not args.command.validateInputs.add(validate):
            raise RuntimeError("Fusion could not validate the connection target.")
        if not args.command.execute.add(execute):
            raise RuntimeError("Fusion could not save the cable-end connection.")
        _runtime.retain_command_handlers(args.command, preselect, validate, execute)


AttachCableEndCreatedHandler = _AttachCableEndCreatedHandler
