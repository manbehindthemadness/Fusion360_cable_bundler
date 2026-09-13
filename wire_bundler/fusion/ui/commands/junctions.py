"""
Fusion command controllers for junctions.
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

from ....application import add_junction, add_junction_relationship
from ....domain import (
    ControlKind,
    HarnessDefinition,
    JunctionPathwayRelationship,
    PathwayEndpoint,
    loads,
)
from ..constants import (
    JUNCTION_PROFILE_INPUT_ID,
    JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID,
    JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID,
)
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from .pathways import (
    _native_fusion_entity,
)


@dataclass(frozen=True)
class _AddJunctionCommandState:
    """
    Retain the selected harness and its already registered profile entities.
    """

    harness_id: UUID
    registered_profiles: tuple[object, ...]


def _junction_profile_token(
    command_inputs: adsk.core.CommandInputs,
    state: _AddJunctionCommandState,
) -> str:
    """
    Return one unregistered selected sketch-profile token.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(JUNCTION_PROFILE_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select one unused sketch profile for the junction.")
    selection = selection_input.selection(0)
    profile = adsk.fusion.Profile.cast(selection.entity if selection is not None else None)
    if profile is None or not profile.entityToken.strip():
        raise ValueError("Junction selection is not a valid sketch profile.")
    selected = _native_fusion_entity(profile)
    if any(selected == registered for registered in state.registered_profiles):
        raise ValueError("Selected geometry is already registered in this harness.")
    return profile.entityToken


class _AddJunctionPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Prevent selection of profiles already registered in the owning harness.
    """

    def __init__(self, state: _AddJunctionCommandState) -> None:
        """
        Retain resolved registered profile entities.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Allow only an unused sketch profile.
        """
        selection = args.selection
        profile = adsk.fusion.Profile.cast(selection.entity if selection is not None else None)
        selected = _native_fusion_entity(profile) if profile is not None else None
        args.isSelectable = profile is not None and all(
            selected != registered for registered in self._state.registered_profiles
        )


class _AddJunctionValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require exactly one currently unregistered sketch profile.
    """

    def __init__(self, state: _AddJunctionCommandState) -> None:
        """
        Retain the selection-validation state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Enable execution only for an eligible selection.
        """
        try:
            _junction_profile_token(args.inputs, self._state)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddJunctionExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one isolated junction inside Fusion's command transaction.
    """

    def __init__(self, state: _AddJunctionCommandState) -> None:
        """
        Retain the selected harness and registered geometry state.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Add the junction and refresh the palette projection.
        """
        application = adsk.core.Application.get()
        try:
            junction = add_junction(
                self._state.harness_id,
                _junction_profile_token(args.command.commandInputs, self._state),
                _create_harness_gateway(application),
            )
            _send_palette_state(application, f"Created {junction.name}.")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add junction failed: {error}\n{traceback.format_exc()}")


class _AddJunctionCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the unused-profile selector for isolated junction creation.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve registered profiles and attach command-lifetime handlers.
        """

        harness_id = _runtime.pending_junction.consume()
        try:
            if harness_id is None:
                raise RuntimeError("No harness was selected for junction creation.")
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            definition = loads(
                _create_harness_gateway(application).read_harness_definition(harness_id)
            )
            registered_tokens = {
                token for connection in definition.connections for token in connection.member_tokens
            } | {control.entity_token for control in definition.controls if control.entity_token}
            registered_profiles: list[object] = []
            for token in registered_tokens:
                for entity in design.findEntityByToken(token) or ():
                    profile = adsk.fusion.Profile.cast(entity)
                    if profile is not None:
                        registered_profiles.append(_native_fusion_entity(profile))
            state = _AddJunctionCommandState(harness_id, tuple(registered_profiles))
            selection_input = args.command.commandInputs.addSelectionInput(
                JUNCTION_PROFILE_INPUT_ID,
                "Junction Profile",
                "Select one sketch profile not already registered in this harness",
            )
            if selection_input is None or not selection_input.addSelectionFilter("Profiles"):
                raise RuntimeError("Fusion could not configure junction-profile selection.")
            if not selection_input.setSelectionLimits(1, 1):
                raise RuntimeError("Fusion could not limit junction-profile selection.")
            preselect_handler = _AddJunctionPreSelectHandler(state)
            validate_handler = _AddJunctionValidateInputsHandler(state)
            execute_handler = _AddJunctionExecuteHandler(state)
            if not args.command.preSelect.add(preselect_handler):
                raise RuntimeError("Fusion could not filter junction-profile selection.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate junction creation.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save the junction.")
            _runtime.retain_command_handlers(
                args.command,
                preselect_handler,
                validate_handler,
                execute_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Junction")
            raise


@dataclass(frozen=True)
class _JunctionRelationshipCandidate:
    """
    Bind one available pathway endpoint to its selectable Fusion geometry.
    """

    relationship: JunctionPathwayRelationship
    label: str
    control_id: UUID
    profile: Optional[object]


@dataclass(frozen=True)
class _AddJunctionRelationshipCommandState:
    """
    Retain one junction and its currently selectable pathway endpoints.
    """

    harness_id: UUID
    junction_id: UUID
    candidates: tuple[_JunctionRelationshipCandidate, ...]


def _junction_relationship_candidates(
    definition: HarnessDefinition,
    junction_id: UUID,
    design: adsk.fusion.Design,
) -> tuple[_JunctionRelationshipCandidate, ...]:
    """
    Resolve unclaimed pathway boundaries to profiles or persistent refine markers.
    """
    if all(junction.junction_id != junction_id for junction in definition.junctions):
        raise ValueError("Selected junction no longer exists.")
    claimed = {
        (relationship.pathway_id, relationship.endpoint)
        for junction in definition.junctions
        for relationship in junction.pathway_relationships
    }
    controls = {control.control_id: control for control in definition.controls}
    candidates: list[_JunctionRelationshipCandidate] = []
    for pathway in definition.pathways:
        if not pathway.ordered_control_ids:
            continue
        for endpoint, control_id, label in (
            (PathwayEndpoint.START, pathway.ordered_control_ids[0], "End A"),
            (PathwayEndpoint.END, pathway.ordered_control_ids[-1], "End B"),
        ):
            relationship = JunctionPathwayRelationship(pathway.pathway_id, endpoint)
            if (relationship.pathway_id, relationship.endpoint) in claimed:
                continue
            control = controls.get(control_id)
            if control is None:
                continue
            profile: Optional[object] = None
            if control.kind is not ControlKind.REFINE:
                entities = design.findEntityByToken(control.entity_token) or ()
                profile = next(
                    (
                        candidate
                        for entity in entities
                        if (candidate := adsk.fusion.Profile.cast(entity)) is not None
                    ),
                    None,
                )
                if profile is None:
                    continue
            candidates.append(
                _JunctionRelationshipCandidate(
                    relationship,
                    f"{pathway.name} · {label}",
                    control_id,
                    profile,
                )
            )
    return tuple(candidates)


def _matching_junction_relationship_candidates(
    entity: object,
    state: _AddJunctionRelationshipCommandState,
) -> tuple[_JunctionRelationshipCandidate, ...]:
    """
    Return available endpoint candidates represented by one selected entity.
    """
    marker_id = getattr(entity, "id", None)
    marker_control_id: Optional[UUID] = None
    if isinstance(marker_id, str):
        try:
            marker_control_id = UUID(marker_id)
        except ValueError:
            marker_control_id = None
    profile = adsk.fusion.Profile.cast(entity)
    selected_profile = _native_fusion_entity(profile) if profile is not None else None
    return tuple(
        candidate
        for candidate in state.candidates
        if (
            marker_control_id == candidate.control_id
            if candidate.profile is None
            else selected_profile is not None
            and selected_profile == _native_fusion_entity(candidate.profile)
        )
    )


def _read_junction_relationship_candidate(
    command_inputs: adsk.core.CommandInputs,
    state: _AddJunctionRelationshipCommandState,
) -> _JunctionRelationshipCandidate:
    """
    Resolve one selected boundary, requiring a choice only when geometry is ambiguous.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select one pathway-ending shape.")
    selection = selection_input.selection(0)
    entity = selection.entity if selection is not None else None
    matches = _matching_junction_relationship_candidates(entity, state)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError("Selected geometry is not an available pathway end.")
    choice_input = adsk.core.DropDownCommandInput.cast(
        command_inputs.itemById(JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID)
    )
    selected_item = choice_input.selectedItem if choice_input is not None else None
    selected_item_name = getattr(selected_item, "name", None)
    for candidate in matches:
        if selected_item_name == candidate.label:
            return candidate
    raise ValueError("Choose which matching pathway end to attach.")


def _update_junction_relationship_choices(
    command_inputs: adsk.core.CommandInputs,
    state: _AddJunctionRelationshipCommandState,
) -> None:
    """
    Show only endpoint choices represented by the currently selected geometry.
    """
    choice_input = adsk.core.DropDownCommandInput.cast(
        command_inputs.itemById(JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID)
    )
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID)
    )
    if choice_input is None or selection_input is None:
        raise RuntimeError("Junction relationship inputs are unavailable.")
    choice_input.listItems.clear()
    matches: tuple[_JunctionRelationshipCandidate, ...] = ()
    if selection_input.selectionCount == 1:
        selection = selection_input.selection(0)
        entity = selection.entity if selection is not None else None
        matches = _matching_junction_relationship_candidates(entity, state)
    for index, candidate in enumerate(matches):
        if choice_input.listItems.add(candidate.label, index == 0) is None:
            raise RuntimeError("Fusion could not add a pathway-end choice.")
    choice_input.isVisible = len(matches) > 1


class _AddJunctionRelationshipPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Restrict relationship selection to unclaimed pathway-ending geometry.
    """

    def __init__(self, state: _AddJunctionRelationshipCommandState) -> None:
        """
        Retain eligible endpoint geometry for the command lifetime.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Mark only geometry representing at least one available endpoint selectable.
        """
        selection = args.selection
        entity = selection.entity if selection is not None else None
        args.isSelectable = bool(_matching_junction_relationship_candidates(entity, self._state))


class _AddJunctionRelationshipInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Narrow the endpoint choice after pathway-ending geometry is selected.
    """

    def __init__(self, state: _AddJunctionRelationshipCommandState) -> None:
        """
        Retain eligible endpoint geometry for the command lifetime.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Refresh the ambiguity choice from the current selection.
        """
        if getattr(args.input, "id", None) != JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID:
            return
        try:
            _update_junction_relationship_choices(args.inputs, self._state)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("choose junction pathway end")


class _AddJunctionRelationshipValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require one eligible geometry selection and resolved endpoint choice.
    """

    def __init__(self, state: _AddJunctionRelationshipCommandState) -> None:
        """
        Retain eligible endpoint geometry for validation.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Enable execution only when the selection resolves unambiguously.
        """
        try:
            _read_junction_relationship_candidate(args.inputs, self._state)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddJunctionRelationshipExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one geometry-selected junction relationship.
    """

    def __init__(self, state: _AddJunctionRelationshipCommandState) -> None:
        """
        Retain the target junction and eligible endpoint set.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Revalidate and attach the selected endpoint in the native transaction.
        """
        application = adsk.core.Application.get()
        try:
            candidate = _read_junction_relationship_candidate(
                args.command.commandInputs,
                self._state,
            )
            add_junction_relationship(
                self._state.harness_id,
                self._state.junction_id,
                candidate.relationship,
                _create_harness_gateway(application),
            )
            _send_palette_state(application, f"Attached {candidate.label}.")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add junction relationship failed: {error}\n{traceback.format_exc()}")


class _AddJunctionRelationshipCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build the pathway-ending geometry selector for one junction.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve available boundaries and attach command-lifetime handlers.
        """

        pending_ids = _runtime.pending_junction_relationship.consume()
        try:
            if pending_ids is None:
                raise RuntimeError("No junction was selected for relationship editing.")
            harness_id, junction_id = pending_ids
            application = adsk.core.Application.get()
            design = _require_active_design(application)
            definition = loads(
                _create_harness_gateway(application).read_harness_definition(harness_id)
            )
            candidates = _junction_relationship_candidates(definition, junction_id, design)
            if not candidates:
                raise ValueError("No unclaimed pathway-ending geometry is available.")
            state = _AddJunctionRelationshipCommandState(
                harness_id,
                junction_id,
                candidates,
            )
            command_inputs = args.command.commandInputs
            selection_input = command_inputs.addSelectionInput(
                JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID,
                "Pathway End",
                "Select pathway-ending shape geometry",
            )
            if selection_input is None:
                raise RuntimeError("Fusion could not create pathway-end selection.")
            if not selection_input.addSelectionFilter("Profiles"):
                raise RuntimeError("Fusion could not allow pathway profile selection.")
            if not selection_input.addSelectionFilter("CustomGraphics"):
                raise RuntimeError("Fusion could not allow refine-marker selection.")
            if not selection_input.setSelectionLimits(1, 1):
                raise RuntimeError("Fusion could not limit pathway-end selection.")
            choice_input = command_inputs.addDropDownCommandInput(
                JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID,
                "Matching Pathway End",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            if choice_input is None:
                raise RuntimeError("Fusion could not create the pathway-end choice.")
            choice_input.isVisible = False
            preselect_handler = _AddJunctionRelationshipPreSelectHandler(state)
            input_handler = _AddJunctionRelationshipInputChangedHandler(state)
            validate_handler = _AddJunctionRelationshipValidateInputsHandler(state)
            execute_handler = _AddJunctionRelationshipExecuteHandler(state)
            if not args.command.preSelect.add(preselect_handler):
                raise RuntimeError("Fusion could not filter pathway-end selection.")
            if not args.command.inputChanged.add(input_handler):
                raise RuntimeError("Fusion could not watch pathway-end selection.")
            if not args.command.validateInputs.add(validate_handler):
                raise RuntimeError("Fusion could not validate pathway-end selection.")
            if not args.command.execute.add(execute_handler):
                raise RuntimeError("Fusion could not save the junction relationship.")
            _runtime.retain_command_handlers(
                args.command,
                preselect_handler,
                input_handler,
                validate_handler,
                execute_handler,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("open Add Junction Relationship")
            raise


AddJunctionCreatedHandler = _AddJunctionCreatedHandler
AddJunctionRelationshipCreatedHandler = _AddJunctionRelationshipCreatedHandler
