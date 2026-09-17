"""
Fusion command controllers for pathways.
"""

from __future__ import annotations

import traceback
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import (
    add_pathway,
    append_pathway_gates,
    segment_pathway,
    suggest_pathway_extension_name,
    suggest_pathway_name,
)
from ....domain import ControlKind, loads
from ..constants import (
    PATHWAY_GATES_INPUT_ID,
    PATHWAY_NAME_INPUT_ID,
    ROUTING_MODE_INPUT_ID,
    SEGMENT_CONTROL_INPUT_ID,
    SEGMENT_PATHWAY_NAME_INPUT_ID,
)
from ..constants import (
    ROUTING_MODE_LABELS as _ROUTING_MODE_LABELS,
)
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from ..viewport import _refresh_active_preview
from .harness import (
    _read_routing_mode,
)
from .refines import (
    _reconcile_active_refines,
)


class _AddPathwayExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist an ordered pathway selected from Fusion sketch profiles.
    """

    def __init__(self, harness_id: UUID) -> None:
        """
        Bind the handler to the harness selected in the palette.
        """
        super().__init__()
        self._harness_id = harness_id

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Add the selected gate profiles to the owning harness as one pathway.
        """
        try:
            application = adsk.core.Application.get()
            command_inputs = args.command.commandInputs
            pathway = add_pathway(
                self._harness_id,
                _read_pathway_name(command_inputs),
                _read_routing_mode(command_inputs),
                _read_pathway_gate_tokens(command_inputs),
                _create_harness_gateway(application),
            )
            _send_palette_state(application, f"Created {pathway.name}.")
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("add pathway")


class _AddPathwayValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require a name, routing mode, and at least one selected profile.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Validate the complete pathway draft before Fusion enables execution.
        """
        try:
            _read_pathway_name(args.inputs)
            _read_routing_mode(args.inputs)
            _read_pathway_gate_tokens(args.inputs)
        except ValueError:
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddPathwayCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the ordered profile-selection command for the selected harness.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Add pathway inputs and retain their event handlers.
        """

        harness_id = _runtime.pending_pathway.consume()
        try:
            if harness_id is None:
                raise RuntimeError("No harness was selected for pathway creation.")
            application = adsk.core.Application.get()
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(harness_id))
            initial_name = suggest_pathway_name(harness_id, "Pathway_001", gateway)
            command_inputs = args.command.commandInputs

            name_input = command_inputs.addStringValueInput(
                PATHWAY_NAME_INPUT_ID,
                "Pathway Name",
                initial_name,
            )
            if name_input is None:
                raise RuntimeError("Fusion did not create the pathway name input.")

            routing_mode_input = command_inputs.addDropDownCommandInput(
                ROUTING_MODE_INPUT_ID,
                "Routing Mode",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            if routing_mode_input is None:
                raise RuntimeError("Fusion did not create the pathway routing-mode input.")
            for routing_mode, label in _ROUTING_MODE_LABELS.items():
                list_item = routing_mode_input.listItems.add(
                    label,
                    routing_mode is definition.routing_mode,
                )
                if list_item is None:
                    raise RuntimeError(f"Fusion did not add the routing mode option: {label}")

            gate_input = command_inputs.addSelectionInput(
                PATHWAY_GATES_INPUT_ID,
                "Ordered Gate Profiles",
                "Select sketch profiles in pathway traversal order",
            )
            if gate_input is None:
                raise RuntimeError("Fusion did not create the pathway gate selection input.")
            if not gate_input.addSelectionFilter("Profiles"):
                raise RuntimeError("Fusion did not apply the sketch-profile selection filter.")
            if not gate_input.setSelectionLimits(1, 0):
                raise RuntimeError("Fusion did not configure the pathway selection limits.")

            execute_handler = _AddPathwayExecuteHandler(harness_id)
            validate_handler = _AddPathwayValidateInputsHandler()
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion did not register the pathway execution handler.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion did not register the pathway validation handler.")
            _runtime.retain_command_handlers(
                args.command,
                execute_handler,
                validate_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Pathway")
            raise


class _AppendGatesExecuteHandler(adsk.core.CommandEventHandler):
    """
    Append selected sketch profiles to an existing pathway.
    """

    def __init__(self, harness_id: UUID, pathway_id: UUID) -> None:
        """
        Bind the handler to the selected harness and pathway.
        """
        super().__init__()
        self._harness_id = harness_id
        self._pathway_id = pathway_id

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Persist the selected profiles at the end of the pathway.
        """
        try:
            application = adsk.core.Application.get()
            controls = append_pathway_gates(
                self._harness_id,
                self._pathway_id,
                _read_pathway_gate_tokens(args.command.commandInputs),
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._harness_id)
            application.activeViewport.refresh()
            _send_palette_state(application, f"Added {len(controls)} gates. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("add pathway gates")


class _AppendGatesCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the ordered gate-selection command for one existing pathway.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Add gate selection input and retain its event handlers.
        """

        pending_ids = _runtime.pending_append_gates.consume()
        try:
            if pending_ids is None:
                raise RuntimeError("No pathway was selected for gate creation.")
            harness_id, pathway_id = pending_ids
            gate_input = args.command.commandInputs.addSelectionInput(
                PATHWAY_GATES_INPUT_ID,
                "Additional Gate Profiles",
                "Select additional sketch profiles in traversal order",
            )
            if gate_input is None:
                raise RuntimeError("Fusion did not create the gate selection input.")
            if not gate_input.addSelectionFilter("Profiles"):
                raise RuntimeError("Fusion did not apply the sketch-profile selection filter.")
            if not gate_input.setSelectionLimits(1, 0):
                raise RuntimeError("Fusion did not configure the gate selection limits.")

            execute_handler = _AppendGatesExecuteHandler(harness_id, pathway_id)
            validate_handler = _AppendGatesValidateInputsHandler()
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion did not register the add-gates execution handler.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion did not register the add-gates validation handler.")
            _runtime.retain_command_handlers(
                args.command,
                execute_handler,
                validate_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Gates")
            raise


class _AppendGatesValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require at least one selected gate profile.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Validate gate selections before Fusion enables execution.
        """
        try:
            _read_pathway_gate_tokens(args.inputs)
        except ValueError:
            args.areInputsValid = False
            return
        args.areInputsValid = True


@dataclass(frozen=True)
class _SegmentCommandState:
    """
    Retain eligible resolved controls for one pathway-segmentation command.
    """

    harness_id: UUID
    pathway_id: UUID
    profile_controls: tuple[tuple[UUID, object], ...]
    refine_control_ids: frozenset[UUID]


class _SegmentPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Restrict segmentation selection to supported interior pathway controls.
    """

    def __init__(self, state: _SegmentCommandState) -> None:
        """
        Retain the resolved eligible controls.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Accept an eligible profile or persistent refine marker.
        """
        selection = args.selection
        entity = selection.entity if selection is not None else None
        args.isSelectable = _segment_entity_control_id(entity, self._state) is not None


class _SegmentValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require a new pathway name and exactly one eligible control.
    """

    def __init__(self, state: _SegmentCommandState) -> None:
        """
        Retain the eligible command controls.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Enable execution only for a complete segmentation request.
        """
        try:
            _read_segment_pathway_name(args.inputs)
            _read_segment_control_id(args.inputs, self._state)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _SegmentExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one pathway split inside Fusion's command transaction.
    """

    def __init__(self, state: _SegmentCommandState) -> None:
        """
        Retain the selected harness and pathway identities.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Segment the pathway and refresh logical and graphical projections.
        """
        application = adsk.core.Application.get()
        try:
            result = segment_pathway(
                self._state.harness_id,
                self._state.pathway_id,
                _read_segment_control_id(args.command.commandInputs, self._state),
                _read_segment_pathway_name(args.command.commandInputs),
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._state.harness_id)
            _reconcile_active_refines(application)
            application.activeViewport.refresh()
            _send_palette_state(
                application,
                f"Created {result.following_pathway.name} and {result.junction.name}. "
                f"{warning}".strip(),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Segment pathway failed: {error}\n{traceback.format_exc()}")


class _SegmentCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the native name-and-member pathway-segmentation command.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve eligible interior controls and attach command handlers.
        """
        pending_ids = _runtime.pending_segment.consume()
        try:
            if pending_ids is None:
                raise RuntimeError("No pathway was selected for segmentation.")
            harness_id, pathway_id = pending_ids
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(harness_id))
            pathway = next(
                (item for item in definition.pathways if item.pathway_id == pathway_id),
                None,
            )
            if pathway is None:
                raise ValueError("Selected pathway no longer exists.")
            controls = {control.control_id: control for control in definition.controls}
            profile_controls: list[tuple[UUID, object]] = []
            refine_control_ids: set[UUID] = set()
            for control_id in pathway.ordered_control_ids[1:-1]:
                control = controls.get(control_id)
                if control is None:
                    continue
                if control.kind is ControlKind.REFINE:
                    refine_control_ids.add(control_id)
                elif control.kind is ControlKind.ROUTING_GATE:
                    entities = design.findEntityByToken(control.entity_token)
                    profile = adsk.fusion.Profile.cast(entities[0] if entities else None)
                    if profile is not None:
                        profile_controls.append((control_id, profile))
            if not profile_controls and not refine_control_ids:
                raise ValueError("This pathway has no supported interior control to segment.")

            command_inputs = args.command.commandInputs
            name_input = command_inputs.addStringValueInput(
                SEGMENT_PATHWAY_NAME_INPUT_ID,
                "New Pathway Name",
                suggest_pathway_extension_name(harness_id, pathway_id, gateway),
            )
            if name_input is None:
                raise RuntimeError("Fusion could not create the extension-name input.")
            selection_input = command_inputs.addSelectionInput(
                SEGMENT_CONTROL_INPUT_ID,
                "Junction Control",
                "Select an interior routing gate or refine point",
            )
            if selection_input is None:
                raise RuntimeError("Fusion could not create the junction-control input.")
            if not selection_input.addSelectionFilter("Profiles"):
                raise RuntimeError("Fusion could not allow routing-gate selection.")
            if not selection_input.addSelectionFilter("CustomGraphics"):
                raise RuntimeError("Fusion could not allow refine-point selection.")
            if not selection_input.setSelectionLimits(1, 1):
                raise RuntimeError("Fusion could not limit junction-control selection.")
            state = _SegmentCommandState(
                harness_id,
                pathway_id,
                tuple(profile_controls),
                frozenset(refine_control_ids),
            )
            preselect_handler = _SegmentPreSelectHandler(state)
            validate_handler = _SegmentValidateInputsHandler(state)
            execute_handler = _SegmentExecuteHandler(state)
            if not args.command.preSelect.add(preselect_handler):
                raise RuntimeError("Fusion could not filter pathway segmentation selection.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate pathway segmentation.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save pathway segmentation.")
            _runtime.retain_command_handlers(
                args.command,
                preselect_handler,
                validate_handler,
                execute_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Segment Pathway")
            raise


def _native_fusion_entity(entity: object) -> object:
    """
    Normalize an assembly-context proxy to its native Fusion entity.
    """
    native = getattr(entity, "nativeObject", None)
    return native if native is not None else entity


def _native_profile_entities(
    design: adsk.fusion.Design,
    entity_tokens: Iterable[str],
) -> tuple[object, ...]:
    """
    Resolve persisted entity tokens to native Fusion profiles.
    """
    profiles: list[object] = []
    for token in set(entity_tokens):
        for entity in design.findEntityByToken(token) or ():
            profile = adsk.fusion.Profile.cast(entity)
            if profile is not None:
                profiles.append(_native_fusion_entity(profile))
    return tuple(profiles)


def _segment_entity_control_id(
    entity: object,
    state: _SegmentCommandState,
) -> Optional[UUID]:
    """
    Resolve an eligible selected profile or refine marker to its control identity.
    """
    marker_id = getattr(entity, "id", None)
    if isinstance(marker_id, str):
        try:
            marker_control_id = UUID(marker_id)
        except ValueError:
            marker_control_id = None
        if marker_control_id in state.refine_control_ids:
            return marker_control_id
    profile = adsk.fusion.Profile.cast(entity)
    if profile is None:
        return None
    selected_entity = _native_fusion_entity(profile)
    for control_id, eligible_profile in state.profile_controls:
        if selected_entity == _native_fusion_entity(eligible_profile):
            return control_id
    return None


def _read_segment_control_id(
    command_inputs: adsk.core.CommandInputs,
    state: _SegmentCommandState,
) -> UUID:
    """
    Return the single eligible pathway control selected for segmentation.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(SEGMENT_CONTROL_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select one interior routing gate or refine point.")
    selection = selection_input.selection(0)
    control_id = _segment_entity_control_id(
        selection.entity if selection is not None else None,
        state,
    )
    if control_id is None:
        raise ValueError("Selected geometry is not a supported interior pathway control.")
    return control_id


def _read_segment_pathway_name(command_inputs: adsk.core.CommandInputs) -> str:
    """
    Read the required friendly name for the new pathway half.
    """
    name_input = adsk.core.StringValueCommandInput.cast(
        command_inputs.itemById(SEGMENT_PATHWAY_NAME_INPUT_ID)
    )
    if name_input is None or not name_input.value.strip():
        raise ValueError("New pathway name must not be empty.")
    return name_input.value.strip()


def _read_pathway_name(command_inputs: adsk.core.CommandInputs) -> str:
    """
    Read and normalize the required pathway name input.
    """
    name_input = adsk.core.StringValueCommandInput.cast(
        command_inputs.itemById(PATHWAY_NAME_INPUT_ID)
    )
    if name_input is None:
        raise ValueError("Pathway name input is unavailable.")
    name = name_input.value.strip()
    if not name:
        raise ValueError("Pathway name must not be empty.")
    return name


def _read_pathway_gate_tokens(command_inputs: adsk.core.CommandInputs) -> tuple[str, ...]:
    """
    Return selected Fusion profile tokens in traversal order.
    """
    gate_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(PATHWAY_GATES_INPUT_ID)
    )
    if gate_input is None or gate_input.selectionCount < 1:
        raise ValueError("Select at least one pathway gate profile.")

    tokens: list[str] = []
    for index in range(gate_input.selectionCount):
        selection = gate_input.selection(index)
        profile = adsk.fusion.Profile.cast(selection.entity if selection is not None else None)
        if profile is None or not profile.entityToken.strip():
            raise ValueError(f"Pathway gate selection {index + 1} is not a valid sketch profile.")
        tokens.append(profile.entityToken)
    return tuple(tokens)


AddPathwayCreatedHandler = _AddPathwayCreatedHandler
AppendGatesCreatedHandler = _AppendGatesCreatedHandler
SegmentCreatedHandler = _SegmentCreatedHandler
