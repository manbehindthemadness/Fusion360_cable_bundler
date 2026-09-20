"""Focused Fusion UI regressions for native commands."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Any,
    JunctionPathwayRelationship,
    Mock,
    PathwayEndpoint,
    SimpleNamespace,
    _configure_relationship_selector_casts,
    _PaletteLifecycleModule,
    importlib,
    pytest,
    sys,
)


def test_junction_selector_rejects_registered_profiles(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Filter registered native geometry and read one unused profile token.
    """
    registered = SimpleNamespace(entityToken="registered", nativeObject=None)
    unused = SimpleNamespace(entityToken="unused", nativeObject=None)
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=unused),
    )
    inputs = SimpleNamespace(itemById=lambda _identity: selection_input)
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.SelectionCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    fusion_module.Profile = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    state = addin_module._AddJunctionCommandState(UUID(int=1), (registered,))

    assert addin_module._junction_profile_token(inputs, state) == "unused"
    unused_args = SimpleNamespace(selection=SimpleNamespace(entity=unused), isSelectable=False)
    registered_args = SimpleNamespace(
        selection=SimpleNamespace(entity=registered), isSelectable=True
    )
    handler = addin_module._AddJunctionPreSelectHandler(state)
    handler.notify(unused_args)
    handler.notify(registered_args)
    assert unused_args.isSelectable is True
    assert registered_args.isSelectable is False

    selection_input.selection = lambda _index: SimpleNamespace(entity=registered)
    with pytest.raises(ValueError, match="already registered"):
        addin_module._junction_profile_token(inputs, state)


def test_junction_selector_requires_a_name_and_passes_it_to_creation(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Validate and persist the friendly name supplied beside the profile selector.
    """
    name_input = SimpleNamespace(value=" Power Branch ")
    profile = SimpleNamespace(entityToken="unused", nativeObject=None)
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=profile),
    )
    inputs_by_id = {
        addin_module.JUNCTION_NAME_INPUT_ID: name_input,
        addin_module.JUNCTION_PROFILE_INPUT_ID: selection_input,
    }
    inputs = SimpleNamespace(itemById=inputs_by_id.get)
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.StringValueCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    core_module.SelectionCommandInput = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda value: value
    )
    fusion_module.Profile = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    state = addin_module._AddJunctionCommandState(UUID(int=1), ())
    validate_args = SimpleNamespace(inputs=inputs, areInputsValid=False)

    addin_module._AddJunctionValidateInputsHandler(state).notify(validate_args)

    assert validate_args.areInputsValid
    gateway = object()
    application = object()
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    junction_commands = importlib.import_module("cable_bundler.fusion.ui.commands.junctions")
    add = Mock(return_value=SimpleNamespace(name="Power Branch"))
    send = Mock()
    monkeypatch.setitem(vars(junction_commands), "add_junction", add)
    monkeypatch.setitem(vars(junction_commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(junction_commands), "_send_palette_state", send)
    execute_args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=inputs),
        executeFailed=False,
        executeFailedMessage="",
    )

    addin_module._AddJunctionExecuteHandler(state).notify(execute_args)

    add.assert_called_once_with(UUID(int=1), "Power Branch", "unused", gateway)
    send.assert_called_once_with(application, "Created Power Branch.")
    assert not execute_args.executeFailed

    name_input.value = "  "
    addin_module._AddJunctionValidateInputsHandler(state).notify(validate_args)
    assert not validate_args.areInputsValid


def test_add_junction_picker_includes_a_suggested_name_field(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Place the editable junction name before the native profile selector.
    """
    harness_id = UUID(int=1)
    application = object()
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value="definition"))
    junction_commands = importlib.import_module("cable_bundler.fusion.ui.commands.junctions")
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setitem(vars(junction_commands), "_require_active_design", lambda _app: object())
    monkeypatch.setitem(vars(junction_commands), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(
        vars(junction_commands),
        "loads",
        lambda _serialized: SimpleNamespace(connections=(), controls=()),
    )
    suggest = Mock(return_value="Junction 02")
    monkeypatch.setitem(vars(junction_commands), "suggest_junction_name", suggest)
    monkeypatch.setitem(vars(junction_commands), "_native_profile_entities", lambda *_args: ())
    name_input = object()
    selection_input = SimpleNamespace(
        addSelectionFilter=Mock(return_value=True),
        setSelectionLimits=Mock(return_value=True),
    )
    command_inputs = SimpleNamespace(
        addStringValueInput=Mock(return_value=name_input),
        addSelectionInput=Mock(return_value=selection_input),
    )
    accepted_event = SimpleNamespace(add=Mock(return_value=True))
    command = SimpleNamespace(
        commandInputs=command_inputs,
        preSelect=accepted_event,
        validateInputs=accepted_event,
        execute=accepted_event,
        destroy=accepted_event,
    )
    addin_module._runtime.pending_junction.prepare(harness_id)

    addin_module._AddJunctionCreatedHandler().notify(SimpleNamespace(command=command))

    suggest.assert_called_once_with(harness_id, "Junction 01", gateway)
    command_inputs.addStringValueInput.assert_called_once_with(
        addin_module.JUNCTION_NAME_INPUT_ID,
        "Junction Name",
        "Junction 02",
    )
    command_inputs.addSelectionInput.assert_called_once_with(
        addin_module.JUNCTION_PROFILE_INPUT_ID,
        "Junction Profile",
        "Select one sketch profile not already registered in this harness",
    )


def test_relationship_selector_narrows_ambiguous_geometry_to_endpoint_choice(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Require an explicit End A/End B choice when one profile represents both.
    """
    profile = SimpleNamespace(nativeObject=None)
    first = JunctionPathwayRelationship(UUID(int=10), PathwayEndpoint.START)
    second = JunctionPathwayRelationship(UUID(int=10), PathwayEndpoint.END)
    candidates = (
        addin_module._JunctionRelationshipCandidate(
            first,
            "Pathway_001 · End A",
            UUID(int=20),
            profile,
        ),
        addin_module._JunctionRelationshipCandidate(
            second,
            "Pathway_001 · End B",
            UUID(int=20),
            profile,
        ),
    )
    state = addin_module._AddJunctionRelationshipCommandState(
        UUID(int=1),
        UUID(int=2),
        candidates,
    )
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=profile),
    )
    choice_input = SimpleNamespace(selectedItem=SimpleNamespace(name="Pathway_001 · End B"))
    inputs = SimpleNamespace(
        itemById=lambda identity: (
            selection_input
            if identity == addin_module.JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID
            else choice_input
        )
    )
    _configure_relationship_selector_casts()

    selected = addin_module._read_junction_relationship_candidate(inputs, state)

    assert selected.relationship == second


def test_relationship_selector_refreshes_choices_as_a_collection(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Clear an active drop-down safely before adding current geometry matches.
    """
    profile = SimpleNamespace(nativeObject=None)
    candidates = tuple(
        addin_module._JunctionRelationshipCandidate(
            JunctionPathwayRelationship(UUID(int=10), endpoint),
            f"Pathway_001 · {label}",
            UUID(int=20),
            profile,
        )
        for endpoint, label in (
            (PathwayEndpoint.START, "End A"),
            (PathwayEndpoint.END, "End B"),
        )
    )
    state = addin_module._AddJunctionRelationshipCommandState(
        UUID(int=1),
        UUID(int=2),
        candidates,
    )
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=profile),
    )
    list_items = SimpleNamespace(clear=Mock(), add=Mock(side_effect=lambda *_args: object()))
    choice_input = SimpleNamespace(listItems=list_items, isVisible=False)
    inputs = SimpleNamespace(
        itemById=lambda identity: (
            selection_input
            if identity == addin_module.JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID
            else choice_input
        )
    )
    _configure_relationship_selector_casts()

    addin_module._update_junction_relationship_choices(inputs, state)

    list_items.clear.assert_called_once_with()
    assert [record.args for record in list_items.add.call_args_list] == [
        ("Pathway_001 · End A", True),
        ("Pathway_001 · End B", False),
    ]
    assert choice_input.isVisible is True


def test_standalone_end_selector_reads_guides_and_one_pathway_boundary(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep ordered guide profiles separate from their placement boundary.
    """
    _configure_relationship_selector_casts()
    guide = SimpleNamespace(entityToken="guide", nativeObject=None)
    boundary = SimpleNamespace(entityToken="boundary", nativeObject=None)
    registered_end = SimpleNamespace(entityToken="registered-end", nativeObject=None)
    candidate = addin_module._JunctionRelationshipCandidate(
        JunctionPathwayRelationship(UUID(int=10), PathwayEndpoint.END),
        "Main · End B",
        UUID(int=11),
        boundary,
    )
    state = addin_module._AddStandaloneEndCommandState(
        UUID(int=1),
        (candidate,),
        (boundary, registered_end),
    )
    guide_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=guide),
    )
    boundary_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(entity=boundary),
    )
    inputs_by_id = {
        addin_module.STANDALONE_END_GUIDES_INPUT_ID: guide_input,
        addin_module.STANDALONE_END_BOUNDARY_INPUT_ID: boundary_input,
    }
    inputs = SimpleNamespace(itemById=inputs_by_id.get)

    guides, selected = addin_module._read_standalone_end_inputs(inputs, state)

    assert guides == ("guide",)
    assert selected == candidate
    selection_args = SimpleNamespace(
        activeInput=SimpleNamespace(id=addin_module.STANDALONE_END_BOUNDARY_INPUT_ID),
        selection=SimpleNamespace(entity=guide),
        isSelectable=True,
    )
    addin_module._AddStandaloneEndPreSelectHandler(state).notify(selection_args)
    assert selection_args.isSelectable is False

    guide_handler = addin_module._AddStandaloneEndPreSelectHandler(state)
    unused_guide_args = SimpleNamespace(
        activeInput=SimpleNamespace(id=addin_module.STANDALONE_END_GUIDES_INPUT_ID),
        selection=SimpleNamespace(entity=guide),
        isSelectable=False,
    )
    pathway_guide_args = SimpleNamespace(
        activeInput=SimpleNamespace(id=addin_module.STANDALONE_END_GUIDES_INPUT_ID),
        selection=SimpleNamespace(entity=boundary),
        isSelectable=True,
    )
    existing_end_args = SimpleNamespace(
        activeInput=SimpleNamespace(id=addin_module.STANDALONE_END_GUIDES_INPUT_ID),
        selection=SimpleNamespace(entity=registered_end),
        isSelectable=True,
    )
    guide_handler.notify(unused_guide_args)
    guide_handler.notify(pathway_guide_args)
    guide_handler.notify(existing_end_args)
    assert unused_guide_args.isSelectable is True
    assert pathway_guide_args.isSelectable is False
    assert existing_end_args.isSelectable is False

    guide_input.selection = lambda _index: SimpleNamespace(entity=boundary)
    with pytest.raises(ValueError, match="already registered"):
        addin_module._read_standalone_end_inputs(inputs, state)


def test_standalone_end_resolves_all_harness_owned_profiles(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reserve both existing end members and routing-control profiles from guide reuse.
    """
    fusion_module = sys.modules["adsk.fusion"]
    connection_native = object()
    control_native = object()
    profiles = {
        "connection": SimpleNamespace(nativeObject=connection_native),
        "control": SimpleNamespace(nativeObject=control_native),
    }
    fusion_module.Profile = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    definition: Any = SimpleNamespace(
        connections=(SimpleNamespace(member_tokens=("connection",)),),
        controls=(
            SimpleNamespace(entity_token="control"),
            SimpleNamespace(entity_token=""),
        ),
    )
    design = SimpleNamespace(
        findEntityByToken=lambda token: (profiles[token],),
    )

    registered = addin_module._harness_profile_entities(definition, design)

    assert set(registered) == {connection_native, control_native}


def test_relationship_selector_refreshes_only_for_geometry_input_changes(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve an active choice while continuing to respond to geometry changes.
    """
    state = addin_module._AddJunctionRelationshipCommandState(
        UUID(int=1),
        UUID(int=2),
        (),
    )
    update_choices = Mock()
    junction_commands = importlib.import_module("cable_bundler.fusion.ui.commands.junctions")
    monkeypatch.setitem(
        vars(junction_commands),
        "_update_junction_relationship_choices",
        update_choices,
    )

    addin_module._AddJunctionRelationshipInputChangedHandler(state).notify(
        SimpleNamespace(
            input=SimpleNamespace(id=addin_module.JUNCTION_RELATIONSHIP_CHOICE_INPUT_ID),
            inputs=object(),
        )
    )

    update_choices.assert_not_called()

    inputs = object()
    addin_module._AddJunctionRelationshipInputChangedHandler(state).notify(
        SimpleNamespace(
            input=SimpleNamespace(id=addin_module.JUNCTION_RELATIONSHIP_GEOMETRY_INPUT_ID),
            inputs=inputs,
        )
    )

    update_choices.assert_called_once_with(inputs, state)
