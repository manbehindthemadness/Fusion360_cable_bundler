"""
Fusion command controllers for wires.
"""

from __future__ import annotations

from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import add_wire_batch
from ....domain import loads
from ..constants import (
    DESTINATION_CONNECTIONS_INPUT_ID,
    SOURCE_CONNECTIONS_INPUT_ID,
    WIRE_DIAMETER_INPUT_ID,
    WIRE_PATHWAY_INPUT_ID,
)
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import _create_harness_gateway, _report_failure
from ..viewport import _refresh_active_preview


class _AddWiresExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist ordered End A-to-End B wire assignments.
    """

    def __init__(self, harness_id: UUID, pathway_ids_by_name: dict[str, UUID]) -> None:
        """
        Bind the handler to one harness and its displayed pathway choices.
        """
        super().__init__()
        self._harness_id = harness_id
        self._pathway_ids_by_name = pathway_ids_by_name

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Pair endpoint selections in order and add their logical wire mappings.
        """
        try:
            application = adsk.core.Application.get()
            command_inputs = args.command.commandInputs
            result = add_wire_batch(
                self._harness_id,
                _read_wire_pathway_id(command_inputs, self._pathway_ids_by_name),
                _read_profile_tokens(command_inputs, SOURCE_CONNECTIONS_INPUT_ID, "End A"),
                _read_profile_tokens(
                    command_inputs,
                    DESTINATION_CONNECTIONS_INPUT_ID,
                    "End B",
                ),
                _read_wire_diameter_mm(command_inputs),
                _create_harness_gateway(application),
            )
            warning = _refresh_active_preview(application, self._harness_id)
            application.activeViewport.refresh()
            _send_palette_state(
                application, f"Created {len(result.wires)} wires. {warning}".strip()
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("add wires")


class _AddWiresValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require a pathway, valid diameter, and equally sized endpoint selections.
    """

    def __init__(self, pathway_ids_by_name: dict[str, UUID]) -> None:
        """
        Retain the displayed pathway choices for identity validation.
        """
        super().__init__()
        self._pathway_ids_by_name = pathway_ids_by_name

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Validate the complete wire batch before Fusion enables execution.
        """
        try:
            _read_wire_pathway_id(args.inputs, self._pathway_ids_by_name)
            _read_wire_diameter_mm(args.inputs)
            end_a_profiles = _read_profile_tokens(
                args.inputs,
                SOURCE_CONNECTIONS_INPUT_ID,
                "End A",
            )
            end_b_profiles = _read_profile_tokens(
                args.inputs,
                DESTINATION_CONNECTIONS_INPUT_ID,
                "End B",
            )
            if len(end_a_profiles) != len(end_b_profiles):
                raise ValueError("End A and End B profile counts must match.")
        except ValueError:
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddWiresCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the native ordered endpoint-selection command.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Add wire inputs and retain their event handlers.
        """

        pending_request = _runtime.pending_add_wires.consume()
        harness_id, selected_pathway_id = pending_request or (None, None)
        try:
            if harness_id is None:
                raise RuntimeError("No harness was selected for wire assignment.")
            application = adsk.core.Application.get()
            gateway = _create_harness_gateway(application)
            definition = loads(gateway.read_harness_definition(harness_id))
            if not definition.pathways:
                raise RuntimeError("Create a pathway before adding wires.")
            if selected_pathway_id is not None and all(
                pathway.pathway_id != selected_pathway_id for pathway in definition.pathways
            ):
                raise RuntimeError("The selected pathway is no longer available.")
            pathway_ids_by_name = {
                pathway.name: pathway.pathway_id for pathway in definition.pathways
            }
            command_inputs = args.command.commandInputs

            pathway_input = command_inputs.addDropDownCommandInput(
                WIRE_PATHWAY_INPUT_ID,
                "Pathway",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            if pathway_input is None:
                raise RuntimeError("Fusion did not create the wire pathway input.")
            for index, pathway in enumerate(definition.pathways):
                is_selected = (
                    pathway.pathway_id == selected_pathway_id
                    if selected_pathway_id is not None
                    else index == 0
                )
                if pathway_input.listItems.add(pathway.name, is_selected) is None:
                    raise RuntimeError(f"Fusion did not add the pathway option: {pathway.name}")

            diameter_value = adsk.core.ValueInput.createByString("1.5 mm")
            diameter_input = command_inputs.addValueInput(
                WIRE_DIAMETER_INPUT_ID,
                "Wire Diameter",
                "mm",
                diameter_value,
            )
            if diameter_input is None:
                raise RuntimeError("Fusion did not create the wire diameter input.")

            end_a_input = _add_profile_selection_input(
                command_inputs,
                SOURCE_CONNECTIONS_INPUT_ID,
                "Ordered End A Profiles",
                "Select each End A profile in wire order",
            )
            end_b_input = _add_profile_selection_input(
                command_inputs,
                DESTINATION_CONNECTIONS_INPUT_ID,
                "Ordered End B Profiles",
                "Select matching End B profiles in the same order",
            )
            end_a_input.hasFocus = True
            end_b_input.hasFocus = False

            execute_handler = _AddWiresExecuteHandler(harness_id, pathway_ids_by_name)
            validate_handler = _AddWiresValidateInputsHandler(pathway_ids_by_name)
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion did not register the wire execution handler.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion did not register the wire validation handler.")
            _runtime.retain_command_handlers(
                args.command,
                execute_handler,
                validate_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Wires")
            raise


def _add_profile_selection_input(
    command_inputs: adsk.core.CommandInputs,
    input_id: str,
    name: str,
    prompt: str,
) -> adsk.core.SelectionCommandInput:
    """
    Add a required multi-profile selection input.
    """
    selection_input = command_inputs.addSelectionInput(input_id, name, prompt)
    if selection_input is None:
        raise RuntimeError(f"Fusion did not create the {name} input.")
    if not selection_input.addSelectionFilter("Profiles"):
        raise RuntimeError(f"Fusion did not apply the sketch-profile filter to {name}.")
    if not selection_input.setSelectionLimits(1, 0):
        raise RuntimeError(f"Fusion did not configure the selection limits for {name}.")
    return selection_input


def _read_wire_pathway_id(
    command_inputs: adsk.core.CommandInputs,
    pathway_ids_by_name: dict[str, UUID],
) -> UUID:
    """
    Resolve the selected pathway label to its stable identity.
    """
    pathway_input = adsk.core.DropDownCommandInput.cast(
        command_inputs.itemById(WIRE_PATHWAY_INPUT_ID)
    )
    if pathway_input is None or pathway_input.selectedItem is None:
        raise ValueError("Select a pathway.")
    pathway_id = pathway_ids_by_name.get(pathway_input.selectedItem.name)
    if pathway_id is None:
        raise ValueError("Selected pathway is unavailable.")
    return pathway_id


def _read_wire_diameter_mm(command_inputs: adsk.core.CommandInputs) -> float:
    """
    Read a valid positive wire diameter and convert Fusion centimeters to millimeters.
    """
    diameter_input = adsk.core.ValueCommandInput.cast(
        command_inputs.itemById(WIRE_DIAMETER_INPUT_ID)
    )
    if diameter_input is None or not diameter_input.isValidExpression:
        raise ValueError("Wire diameter must be a valid length expression.")
    diameter_mm = diameter_input.value * 10.0
    if diameter_mm <= 0.0:
        raise ValueError("Wire diameter must be positive.")
    return diameter_mm


def _read_profile_tokens(
    command_inputs: adsk.core.CommandInputs,
    input_id: str,
    role: str,
) -> tuple[str, ...]:
    """
    Return selected Fusion profile tokens in user selection order.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(command_inputs.itemById(input_id))
    if selection_input is None or selection_input.selectionCount < 1:
        raise ValueError(f"Select at least one {role} profile.")
    tokens: list[str] = []
    for index in range(selection_input.selectionCount):
        selection = selection_input.selection(index)
        profile = adsk.fusion.Profile.cast(selection.entity if selection is not None else None)
        if profile is None or not profile.entityToken.strip():
            raise ValueError(f"{role.title()} selection {index + 1} is not a valid sketch profile.")
        tokens.append(profile.entityToken)
    return tuple(tokens)


AddWiresCreatedHandler = _AddWiresCreatedHandler
