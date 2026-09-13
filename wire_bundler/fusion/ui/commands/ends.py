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
from ....application.edit_harness import edit_end_members
from ....domain import (
    ControlKind,
    HarnessDefinition,
    JunctionPathwayRelationship,
    PathwayEndpoint,
    loads,
)
from ..constants import (
    PATHWAY_GATES_INPUT_ID,
    STANDALONE_END_BOUNDARY_INPUT_ID,
    STANDALONE_END_CHOICE_INPUT_ID,
    STANDALONE_END_GUIDES_INPUT_ID,
)
from ..palette_state import _send_palette_state
from ..payloads import _read_payload_uuid
from ..runtime import runtime as _runtime
from ..support import (
    _create_harness_gateway,
    _log_to_fusion,
    _report_failure,
    _require_active_design,
)
from ..viewport import _refresh_active_preview
from .junctions import (
    _JunctionRelationshipCandidate,
)
from .pathways import (
    _AppendGatesValidateInputsHandler,
    _native_fusion_entity,
    _read_pathway_gate_tokens,
)
from .wires import (
    _add_profile_selection_input,
    _read_profile_tokens,
)


@dataclass(frozen=True)
class _AddStandaloneEndCommandState:
    """
    Retain one harness and its profile-backed pathway boundaries.
    """

    harness_id: UUID
    candidates: tuple[_JunctionRelationshipCandidate, ...]


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
    )
    candidate = _read_standalone_end_candidate(command_inputs, state)
    boundary_token = getattr(candidate.profile, "entityToken", "")
    if boundary_token and boundary_token in guides:
        raise ValueError("The selected pathway end cannot also be an end guide.")
    return guides, candidate


class _AddStandaloneEndPreSelectHandler(adsk.core.SelectionEventHandler):
    """
    Restrict the boundary input to existing profile-backed pathway ends.
    """

    def __init__(self, state: _AddStandaloneEndCommandState) -> None:
        """
        Retain eligible pathway boundaries.
        """
        super().__init__()
        self._state = state

    def notify(self, args: adsk.core.SelectionEventArgs) -> None:
        """
        Filter only while Fusion is selecting the boundary input.
        """
        active_input = getattr(args, "activeInput", None)
        if getattr(active_input, "id", None) != STANDALONE_END_BOUNDARY_INPUT_ID:
            return
        selection = args.selection
        entity = selection.entity if selection is not None else None
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


class _EditEndExecuteHandler(adsk.core.CommandEventHandler):
    """
    Persist profiles selected for a connection-member edit.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        """
        Retain the selected end and member identity for the native command.
        """
        super().__init__()
        self._payload = payload

    def notify(self, args: adsk.core.CommandEventArgs) -> None:
        """
        Apply the profile selection and refresh the palette after success.
        """
        try:
            application = adsk.core.Application.get()
            tokens = _read_pathway_gate_tokens(args.command.commandInputs)
            _apply_end_member_edit(application, self._payload, tokens)
            warning = _refresh_active_preview(
                application, _read_payload_uuid(self._payload, "harnessId", "harness")
            )
            application.activeViewport.refresh()
            _send_palette_state(application, f"Updated end members. {warning}".strip())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            _report_failure("edit end members")


class _EditEndCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """
    Open native profile selection for adding or replacing end members.
    """

    # noinspection PyMethodMayBeStatic
    def notify(self, args: adsk.core.CommandCreatedEventArgs) -> None:
        """
        Configure ordered profile selection and retain execution handlers.
        """
        payload = _runtime.pending_end_edit.consume()
        if payload is None:
            raise RuntimeError("No end was selected.")
        selection = _add_profile_selection_input(
            args.command.commandInputs,
            PATHWAY_GATES_INPUT_ID,
            "Connection Profiles",
            "Select profiles for this end sequence",
        )
        if not selection.setSelectionLimits(1, 1 if payload.get("editAction") == "replace" else 0):
            raise RuntimeError("Fusion could not set end-member selection limits.")
        execute_handler = _EditEndExecuteHandler(payload)
        validate_handler = _AppendGatesValidateInputsHandler()
        if not args.command.execute.add(execute_handler):
            raise RuntimeError("Fusion could not register the end edit handler.")
        if not args.command.validateInputs.add(validate_handler):
            raise RuntimeError("Fusion could not register end edit validation.")
        _runtime.retain_command_handlers(
            args.command,
            execute_handler,
            validate_handler,
        )


def _apply_end_member_edit(
    application: adsk.core.Application,
    payload: dict[str, object],
    tokens: tuple[str, ...] = (),
) -> None:
    """
    Validate member indices and persist a connection edit through its gateway.
    """
    endpoint = payload.get("endpoint")
    action = payload.get("editAction")
    index = payload.get("memberIndex", 0)
    count = payload.get("expectedMembers")
    target = payload.get("targetIndex", 0)
    if not isinstance(endpoint, str) or not isinstance(action, str):
        raise ValueError("End edit requires an endpoint and action.")
    if (
        isinstance(index, bool)
        or not isinstance(index, int)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or isinstance(target, bool)
        or not isinstance(target, int)
    ):
        raise ValueError("End edit requires integer member indices and counts.")
    edit_end_members(
        _read_payload_uuid(payload, "harnessId", "harness"),
        _read_payload_uuid(payload, "wireId", "wire"),
        endpoint,
        action,
        _create_harness_gateway(application),
        tokens,
        index,
        count,
        target,
    )


AddStandaloneEndCreatedHandler = _AddStandaloneEndCreatedHandler
EditEndCreatedHandler = _EditEndCreatedHandler
apply_end_member_edit = _apply_end_member_edit
