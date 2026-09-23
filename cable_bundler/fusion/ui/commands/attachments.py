"""
Native Fusion command for attaching one cable end to external geometry.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, replace
from typing import Any, Literal, Optional, cast
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import attach_cable_end, attach_cable_end_shielding
from ....domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget, loads
from ...attachment_targets import (
    attachment_target_kind,
    attachment_target_name,
    resolve_attachment_target,
)
from ...cable_solids import refresh_generated_cable_groups_for_connection
from ..constants import CABLE_END_ATTACHMENT_NAME_INPUT_ID, CABLE_END_ATTACHMENT_TARGET_INPUT_ID
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _log_to_fusion, _require_active_design
from ..viewport import _refresh_active_preview
from .pathways import _native_fusion_entity


@dataclass(frozen=True)
class _AttachCableEndCommandState:
    """
    Retain the selected node and geometry unavailable as a target.
    """

    harness_id: UUID
    connection_id: UUID
    attachment_id: UUID
    excluded_entities: tuple[object, ...]
    attachment: CableEndAttachment
    relationship: Literal["main", "shielding"] = "main"


def _surface_parameters(
    evaluator: object,
    point: object,
) -> Optional[tuple[float, float]]:
    """
    Read one UV pair without treating an evaluator miss as a command failure.
    """
    get_parameter = getattr(evaluator, "getParameterAtPoint", None)
    if not callable(get_parameter) or point is None:
        return None
    try:
        result = cast(Any, get_parameter)(point)
        if not isinstance(result, (list, tuple)) or len(result) != 2 or not result[0]:
            return None
        parameter = result[1]
        is_on_face = getattr(evaluator, "isParameterOnFace", None)
        if callable(is_on_face) and not cast(Any, is_on_face)(parameter):
            return None
        return float(parameter.x), float(parameter.y)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _read_face_parameters(face: object) -> tuple[float, float]:
    """
    Locate the selected face's center in persistent, assembly-safe surface parameters.
    """
    for candidate_face in (getattr(face, "nativeObject", None), face):
        if candidate_face is None:
            continue
        evaluator = getattr(candidate_face, "evaluator", None)
        for point_name in ("centroid", "pointOnFace"):
            parameters = _surface_parameters(
                evaluator,
                getattr(candidate_face, point_name, None),
            )
            if parameters is not None:
                return parameters
    raise ValueError("Fusion could not locate a persistent point on this face.")


def _read_attachment_inputs(
    command_inputs: adsk.core.CommandInputs,
    state: _AttachCableEndCommandState,
) -> CableEndTarget:
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
    parameters = _read_face_parameters(entity) if kind is AttachmentTargetKind.FACE else ()
    return CableEndTarget(
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
        Retain guide and previously connected geometry excluded from attachment.
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
    Persist one attachment and update only its affected cable geometry.
    """

    def __init__(self, state: _AttachCableEndCommandState) -> None:
        """
        Retain the attachment request context.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Save the target and rebuild only generated cable groups that use this end.
        """
        application = adsk.core.Application.get()
        try:
            target = _read_attachment_inputs(args.command.commandInputs, self._state)
            gateway = _create_harness_gateway(application)
            if self._state.relationship == "shielding":
                attach_cable_end_shielding(
                    self._state.harness_id,
                    self._state.connection_id,
                    self._state.attachment_id,
                    target,
                    gateway,
                )
                _send_palette_state(application, f"Connected shielding to {target.display_name}.")
            else:
                attachment = replace(
                    self._state.attachment,
                    target_kind=target.target_kind,
                    entity_token=target.entity_token,
                    inherited_name=target.inherited_name,
                    name=target.name,
                    parameters=target.parameters,
                )
                attach_cable_end(
                    self._state.harness_id,
                    self._state.connection_id,
                    self._state.attachment_id,
                    attachment,
                    gateway,
                )
                definition = loads(gateway.read_harness_definition(self._state.harness_id))
                updated_count = refresh_generated_cable_groups_for_connection(
                    _require_active_design(application),
                    gateway.harness_component(self._state.harness_id),
                    definition,
                    self._state.connection_id,
                )
                warning = _refresh_active_preview(application, self._state.harness_id)
                application.activeViewport.refresh()
                geometry_notice = (
                    f" Updated {updated_count} generated cable "
                    f"group{'s' if updated_count != 1 else ''}."
                    if updated_count
                    else ""
                )
                _send_palette_state(
                    application,
                    (
                        f"Attached cable end to {attachment.display_name}."
                        f"{geometry_notice} {warning}"
                    ).strip(),
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
        harness_id, connection_id, attachment_id, relationship = request
        if relationship not in {"main", "shielding"}:
            raise ValueError("Cable-end relationship kind is invalid.")
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
        attachment = next(
            (item for item in connection.attachments if item.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            raise ValueError("Selected cable-end connection no longer exists.")
        selected_target = attachment if relationship == "main" else attachment.shielding_target
        if (
            selected_target is not None
            and resolve_attachment_target(design, selected_target) is not None
        ):
            raise ValueError(
                f"Selected cable-end {relationship} relationship already has a target."
            )
        excluded_entities = tuple(
            _native_fusion_entity(entity)
            for token in (
                *connection.member_tokens,
                *(item.entity_token for item in connection.attachments if item.has_target),
                *(
                    item.shielding_target.entity_token
                    for item in connection.attachments
                    if item.shielding_target is not None
                ),
            )
            for entity in (design.findEntityByToken(token) or ())
        )
        state = _AttachCableEndCommandState(
            harness_id,
            connection_id,
            attachment_id,
            excluded_entities,
            attachment,
            relationship,
        )
        inputs = args.command.commandInputs
        selection_input = inputs.addSelectionInput(
            CABLE_END_ATTACHMENT_TARGET_INPUT_ID,
            "Shielding Target" if relationship == "shielding" else "Connection Target",
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
                "Shielding Connection Name" if relationship == "shielding" else "Connection Name",
                selected_target.name if selected_target is not None else "",
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
