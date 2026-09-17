"""
Fusion command controllers for ends.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from uuid import UUID

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.fusion

from ....application import add_standalone_end
from ....domain import (
    ControlKind,
    HarnessDefinition,
    JunctionPathwayRelationship,
    PathwayEndpoint,
    loads,
)
from ..constants import (
    STANDALONE_END_BOUNDARY_INPUT_ID,
    STANDALONE_END_CHOICE_INPUT_ID,
    STANDALONE_END_GUIDES_INPUT_ID,
)
from ..palette_state import _send_palette_state
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from .junctions import (
    _JunctionRelationshipCandidate,
)
from .pathways import (
    _native_fusion_entity,
    _native_profile_entities,
)


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


def _read_profile_tokens(
    command_inputs: adsk.core.CommandInputs,
    input_id: str,
    role: str,
    unavailable_profiles: tuple[object, ...] = (),
) -> tuple[str, ...]:
    """
    Return unused Fusion profile tokens in user selection order.
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
        selected = _native_fusion_entity(profile)
        if any(selected == registered for registered in unavailable_profiles):
            raise ValueError(
                f"{role.title()} selection {index + 1} is already registered in this harness."
            )
        tokens.append(profile.entityToken)
    return tuple(tokens)


@dataclass(frozen=True)
class _AddStandaloneEndCommandState:
    """
    Retain one harness and its profile-backed pathway boundaries.
    """

    harness_id: UUID
    candidates: tuple[_JunctionRelationshipCandidate, ...]
    unavailable_guide_profiles: tuple[object, ...]


def _harness_profile_entities(
    definition: HarnessDefinition,
    design: adsk.fusion.Design,
) -> tuple[object, ...]:
    """
    Resolve native profiles already owned by controls or connection members.
    """
    registered_tokens = (
        token for connection in definition.connections for token in connection.member_tokens
    )
    control_tokens = (
        control.entity_token for control in definition.controls if control.entity_token
    )
    return _native_profile_entities(design, (*registered_tokens, *control_tokens))


def _standalone_end_candidates(
    definition: HarnessDefinition,
    design: adsk.fusion.Design,
) -> tuple[_JunctionRelationshipCandidate, ...]:
    """
    Resolve every profile-backed pathway boundary available for end placement.
    """
    controls = {control.control_id: control for control in definition.controls}
    candidates: list[_JunctionRelationshipCandidate] = []
    for pathway in definition.pathways:
        if not pathway.ordered_control_ids:
            continue
        for endpoint, control_id, side in (
            (PathwayEndpoint.START, pathway.ordered_control_ids[0], "End A"),
            (PathwayEndpoint.END, pathway.ordered_control_ids[-1], "End B"),
        ):
            control = controls.get(control_id)
            if control is None or control.kind is ControlKind.REFINE:
                continue
            entities = design.findEntityByToken(control.entity_token) or ()
            profile = next(
                (
                    candidate
                    for entity in entities
                    if (candidate := adsk.fusion.Profile.cast(entity)) is not None
                ),
                None,
            )
            if profile is not None:
                candidates.append(
                    _JunctionRelationshipCandidate(
                        JunctionPathwayRelationship(pathway.pathway_id, endpoint),
                        f"{pathway.name} · {side}",
                        control_id,
                        profile,
                    )
                )
    return tuple(candidates)


def _matching_standalone_end_candidates(
    entity: object,
    state: _AddStandaloneEndCommandState,
) -> tuple[_JunctionRelationshipCandidate, ...]:
    """
    Return pathway boundaries represented by one selected profile.
    """
    profile = adsk.fusion.Profile.cast(entity)
    if profile is None:
        return ()
    selected = _native_fusion_entity(profile)
    return tuple(
        candidate
        for candidate in state.candidates
        if candidate.profile is not None and selected == _native_fusion_entity(candidate.profile)
    )


def _read_standalone_end_candidate(
    command_inputs: adsk.core.CommandInputs,
    state: _AddStandaloneEndCommandState,
) -> _JunctionRelationshipCandidate:
    """
    Resolve the selected profile to one logical pathway boundary.
    """
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(STANDALONE_END_BOUNDARY_INPUT_ID)
    )
    if selection_input is None or selection_input.selectionCount != 1:
        raise ValueError("Select exactly one pathway end.")
    selection = selection_input.selection(0)
    matches = _matching_standalone_end_candidates(
        selection.entity if selection is not None else None,
        state,
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError("Selected geometry is not a profile-backed pathway end.")
    choice_input = adsk.core.DropDownCommandInput.cast(
        command_inputs.itemById(STANDALONE_END_CHOICE_INPUT_ID)
    )
    selected_item = choice_input.selectedItem if choice_input is not None else None
    selected_item_name = getattr(selected_item, "name", None)
    for candidate in matches:
        if selected_item_name == candidate.label:
            return candidate
    raise ValueError("Choose which matching pathway end receives the disconnected end.")


def _update_standalone_end_choices(
    command_inputs: adsk.core.CommandInputs,
    state: _AddStandaloneEndCommandState,
) -> None:
    """
    Show an endpoint choice only when selected geometry is ambiguous.
    """
    choice_input = adsk.core.DropDownCommandInput.cast(
        command_inputs.itemById(STANDALONE_END_CHOICE_INPUT_ID)
    )
    selection_input = adsk.core.SelectionCommandInput.cast(
        command_inputs.itemById(STANDALONE_END_BOUNDARY_INPUT_ID)
    )
    if choice_input is None or selection_input is None:
        raise RuntimeError("Standalone-end inputs are unavailable.")
    choice_input.listItems.clear()
    matches: tuple[_JunctionRelationshipCandidate, ...] = ()
    if selection_input.selectionCount == 1:
        selection = selection_input.selection(0)
        matches = _matching_standalone_end_candidates(
            selection.entity if selection is not None else None,
            state,
        )
    for index, candidate in enumerate(matches):
        if choice_input.listItems.add(candidate.label, index == 0) is None:
            raise RuntimeError("Fusion could not add a standalone-end pathway choice.")
    choice_input.isVisible = len(matches) > 1


def _read_standalone_end_inputs(
    command_inputs: adsk.core.CommandInputs,
    state: _AddStandaloneEndCommandState,
) -> tuple[tuple[str, ...], _JunctionRelationshipCandidate]:
    """
    Return guides and placement while keeping the boundary outside the guide stack.
    """
    guides = _read_profile_tokens(
        command_inputs,
        STANDALONE_END_GUIDES_INPUT_ID,
        "end guide",
        state.unavailable_guide_profiles,
    )
    candidate = _read_standalone_end_candidate(command_inputs, state)
    boundary_token = getattr(candidate.profile, "entityToken", "")
    if boundary_token and boundary_token in guides:
        raise ValueError("The selected pathway end cannot also be an end guide.")
    return guides, candidate


class _AddStandaloneEndPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Enforce distinct geometry ownership for both standalone-end selectors.
    """

    def __init__(self, state: _AddStandaloneEndCommandState) -> None:
        """
        Retain eligible pathway boundaries.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Filter guides to unused profiles and boundaries to pathway ends.
        """
        active_input = getattr(args, "activeInput", None)
        input_id = getattr(active_input, "id", None)
        selection = args.selection
        entity = selection.entity if selection is not None else None
        if input_id == STANDALONE_END_GUIDES_INPUT_ID:
            profile = adsk.fusion.Profile.cast(entity)
            selected = _native_fusion_entity(profile) if profile is not None else None
            args.isSelectable = profile is not None and all(
                selected != registered for registered in self._state.unavailable_guide_profiles
            )
            return
        if input_id == STANDALONE_END_BOUNDARY_INPUT_ID:
            args.isSelectable = bool(_matching_standalone_end_candidates(entity, self._state))


class _AddStandaloneEndInputChangedHandler(adsk.core.InputChangedEventHandler):
    """
    Refresh the ambiguity choice after boundary selection changes.
    """

    def __init__(self, state: _AddStandaloneEndCommandState) -> None:
        """
        Retain eligible pathway boundaries.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.InputChangedEventArgs) -> None:
        """
        Update choices only for the pathway-end selector.
        """
        if getattr(args.input, "id", None) == STANDALONE_END_BOUNDARY_INPUT_ID:
            try:
                _update_standalone_end_choices(args.inputs, self._state)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                _report_failure("choose standalone pathway end")


class _AddStandaloneEndValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """
    Require ordered guides and exactly one resolved pathway boundary.
    """

    def __init__(self, state: _AddStandaloneEndCommandState) -> None:
        """
        Retain eligible pathway boundaries.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.ValidateInputsEventArgs) -> None:
        """
        Enable execution only for a complete standalone end.
        """
        try:
            _read_standalone_end_inputs(args.inputs, self._state)
        except (AttributeError, TypeError, ValueError):
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _AddStandaloneEndExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist one disconnected end without invoking route generation.
    """

    def __init__(self, state: _AddStandaloneEndCommandState) -> None:
        """
        Retain the selected harness and eligible boundaries.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Revalidate the selections and refresh only palette state.
        """
        application = adsk.core.Application.get()
        try:
            inputs = args.command.commandInputs
            guides, candidate = _read_standalone_end_inputs(inputs, self._state)
            result = add_standalone_end(
                self._state.harness_id,
                guides,
                candidate.relationship.pathway_id,
                candidate.relationship.endpoint,
                _create_harness_gateway(application),
            )
            application.activeViewport.refresh()
            _send_palette_state(application, f"Created disconnected {result.connection.name}.")
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            _log_to_fusion(f"Add standalone end failed: {error}\n{traceback.format_exc()}")


class _AddStandaloneEndCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Build ordered guide and pathway-boundary selectors.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Resolve eligible boundaries and attach command-lifetime handlers.
        """

        harness_id = _runtime.pending_standalone_end.consume()
        if harness_id is None:
            raise RuntimeError("No harness was selected for standalone-end creation.")
        application = adsk.core.Application.get()
        design = _require_active_design(application)
        definition = loads(_create_harness_gateway(application).read_harness_definition(harness_id))
        state = _AddStandaloneEndCommandState(
            harness_id,
            _standalone_end_candidates(definition, design),
            _harness_profile_entities(definition, design),
        )
        if not state.candidates:
            raise ValueError("No profile-backed pathway ends are available.")
        inputs = args.command.commandInputs
        _add_profile_selection_input(
            inputs,
            STANDALONE_END_GUIDES_INPUT_ID,
            "Ordered End Guides",
            "Select one or more guide profiles in end-to-pathway order",
        )
        boundary_input = inputs.addSelectionInput(
            STANDALONE_END_BOUNDARY_INPUT_ID,
            "Pathway End",
            "Select exactly one existing pathway-end profile",
        )
        if boundary_input is None or not boundary_input.addSelectionFilter("Profiles"):
            raise RuntimeError("Fusion could not configure pathway-end selection.")
        if not boundary_input.setSelectionLimits(1, 1):
            raise RuntimeError("Fusion could not limit pathway-end selection.")
        choice_input = inputs.addDropDownCommandInput(
            STANDALONE_END_CHOICE_INPUT_ID,
            "Matching Pathway End",
            adsk.core.DropDownStyles.TextListDropDownStyle,
        )
        if choice_input is None:
            raise RuntimeError("Fusion could not create the pathway-end choice.")
        choice_input.isVisible = False
        preselect = _AddStandaloneEndPreSelectHandler(state)
        changed = _AddStandaloneEndInputChangedHandler(state)
        validate = _AddStandaloneEndValidateInputsHandler(state)
        execute = _AddStandaloneEndExecuteHandler(state)
        if not args.command.preSelect.add(preselect):
            raise RuntimeError("Fusion could not filter standalone-end selection.")
        if not args.command.inputChanged.add(changed):
            raise RuntimeError("Fusion could not watch standalone-end selection.")
        if not args.command.validateInputs.add(validate):
            raise RuntimeError("Fusion could not validate standalone-end creation.")
        if not args.command.execute.add(execute):
            raise RuntimeError("Fusion could not save the standalone end.")
        _runtime.retain_command_handlers(
            args.command,
            preselect,
            changed,
            validate,
            execute,
        )


AddStandaloneEndCreatedHandler = _AddStandaloneEndCreatedHandler
