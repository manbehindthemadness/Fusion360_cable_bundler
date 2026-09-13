"""Focused Fusion UI regressions for native commands."""

from __future__ import annotations

from tests.fusion_ui_support import (
    REFINE_ID,
    UUID,
    GateFrame,
    HarnessDefinition,
    JunctionPathwayRelationship,
    Mock,
    PathwayEndpoint,
    RefineGeometry,
    SimpleNamespace,
    Vector3,
    _configure_relationship_selector_casts,
    _PaletteLifecycleModule,
    _refine_control,
    dumps,
    importlib,
    json,
    pytest,
    replace,
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
    candidate = addin_module._JunctionRelationshipCandidate(
        JunctionPathwayRelationship(UUID(int=10), PathwayEndpoint.END),
        "Main · End B",
        UUID(int=11),
        boundary,
    )
    state = addin_module._AddStandaloneEndCommandState(UUID(int=1), (candidate,))
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

    guide_input.selection = lambda _index: SimpleNamespace(entity=boundary)
    with pytest.raises(ValueError, match="cannot also"):
        addin_module._read_standalone_end_inputs(inputs, state)


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
    junction_commands = importlib.import_module("wire_bundler.fusion.ui.commands.junctions")
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


def test_refine_selection_accepts_only_command_spine(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Exclude persistent markers and unrelated Custom Graphics from placement.
    """
    handler = addin_module._RefinePreSelectHandler()
    accepted = SimpleNamespace(
        selection=SimpleNamespace(entity=SimpleNamespace(id=addin_module.REFINE_SPINE_ENTITY_ID)),
        isSelectable=False,
    )
    rejected = SimpleNamespace(
        selection=SimpleNamespace(entity=SimpleNamespace(id="another-graphic")),
        isSelectable=True,
    )
    profile = SimpleNamespace(
        selection=SimpleNamespace(entity=SimpleNamespace()),
        isSelectable=True,
    )

    handler.notify(accepted)
    handler.notify(rejected)
    handler.notify(profile)

    assert accepted.isSelectable
    assert not rejected.isSelectable
    assert not profile.isSelectable


def test_segment_selection_normalizes_profiles_and_accepts_refine_marker(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Match eligible native geometry without relying on unstable entity-token strings.
    """
    fusion_module = sys.modules["adsk.fusion"]
    native_profile = object()
    eligible_profile = SimpleNamespace(nativeObject=native_profile, is_profile=True)
    selected_proxy = SimpleNamespace(nativeObject=native_profile, is_profile=True)
    unrelated = SimpleNamespace(nativeObject=object(), is_profile=True)
    fusion_module.Profile = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda entity: entity if getattr(entity, "is_profile", False) else None
    )
    refine_id = UUID(int=22)
    state = addin_module._SegmentCommandState(
        UUID(int=1),
        UUID(int=2),
        ((UUID(int=21), eligible_profile),),
        frozenset((refine_id,)),
    )
    handler = addin_module._SegmentPreSelectHandler(state)
    profile_args = SimpleNamespace(
        selection=SimpleNamespace(entity=selected_proxy), isSelectable=False
    )
    refine_args = SimpleNamespace(
        selection=SimpleNamespace(entity=SimpleNamespace(id=str(refine_id))),
        isSelectable=False,
    )
    unrelated_args = SimpleNamespace(selection=SimpleNamespace(entity=unrelated), isSelectable=True)

    handler.notify(profile_args)
    handler.notify(refine_args)
    handler.notify(unrelated_args)

    assert profile_args.isSelectable
    assert refine_args.isSelectable
    assert not unrelated_args.isSelectable


def test_refine_selection_uses_click_point_and_centimeter_radius(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Project Fusion's root-space click while converting database units to millimeters.
    """
    core_module = sys.modules["adsk.core"]
    core_module.SelectionCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(
            entity=SimpleNamespace(id=addin_module.REFINE_SPINE_ENTITY_ID),
            point=SimpleNamespace(x=0.0, y=0.0, z=1.5),
        ),
    )
    radius_input = SimpleNamespace(isValidExpression=True, value=1.0)
    inputs = SimpleNamespace(
        itemById=lambda identity: selection_input if identity == "refine_spine" else radius_input
    )
    frame = GateFrame(
        UUID(int=1),
        "Gate",
        Vector3(0.0, 0.0, 10.0),
        Vector3(1.0, 0.0, 0.0),
        Vector3(0.0, 1.0, 0.0),
        5.0,
    )
    spine = addin_module.PathwaySpine(
        (Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 20.0)),
        (frame,),
    )

    placement = addin_module._read_refine_placement(inputs, spine)

    assert placement.insertion_index == 1
    assert placement.geometry.origin_mm == (0.0, 0.0, 15.0)
    assert placement.geometry.display_radius_mm == 10.0


def test_refine_placement_rejects_selected_entity_without_graphics_id(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Reject an underlying Fusion profile without leaking an AttributeError.
    """
    core_module = sys.modules["adsk.core"]
    core_module.SelectionCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    selection_input = SimpleNamespace(
        selectionCount=1,
        selection=lambda _index: SimpleNamespace(
            entity=SimpleNamespace(),
            point=SimpleNamespace(x=0.0, y=0.0, z=1.5),
        ),
    )
    radius_input = SimpleNamespace(isValidExpression=True, value=1.0)
    inputs = SimpleNamespace(
        itemById=lambda identity: selection_input if identity == "refine_spine" else radius_input
    )

    with pytest.raises(ValueError, match="displayed pathway spine"):
        addin_module._read_refine_placement(inputs, SimpleNamespace())


def test_refine_placement_drag_updates_existing_candidate_in_place(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Resize the initial-placement marker without replacing its graphics entity.
    """
    geometry = _refine_control(18.0).refine_geometry
    assert geometry is not None
    placement = SimpleNamespace(insertion_index=1, geometry=geometry)
    candidate = SimpleNamespace(isValid=True)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        object(),
        candidate=candidate,
    )
    radius = SimpleNamespace(
        isEnabled=False,
        isVisible=False,
        setManipulator=Mock(return_value=True),
    )
    inputs = SimpleNamespace(itemById=lambda _identity: radius)
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeViewport=viewport)
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    update_candidate = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_read_refine_placement", lambda *_args: placement)
    monkeypatch.setitem(vars(refine_commands), "update_candidate_refine", update_candidate)

    addin_module._update_refine_placement(
        state,
        inputs,
        position_manipulator=False,
    )

    assert state.placement is placement
    assert radius.isEnabled
    assert radius.isVisible
    radius.setManipulator.assert_not_called()
    update_candidate.assert_called_once_with(candidate, geometry)
    viewport.refresh.assert_called_once()


def test_refine_mouse_drag_reads_live_command_inputs(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Poll the distance manipulator throughout a click-drag gesture.
    """
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        object(),
    )
    inputs = object()
    update_placement = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_update_refine_placement", update_placement)

    addin_module._RefineMouseDragHandler(state, inputs).notify(SimpleNamespace())

    update_placement.assert_called_once_with(
        state,
        inputs,
        position_manipulator=False,
    )


def test_refine_placement_replaces_invalidated_candidate_before_redraw(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Never update a Custom Graphics handle Fusion has already invalidated.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    placement = SimpleNamespace(insertion_index=1, geometry=geometry)
    group = object()
    invalid_candidate = SimpleNamespace(isValid=False)
    replacement = SimpleNamespace(isValid=True)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        group,
        candidate=invalid_candidate,
    )
    radius = SimpleNamespace(isEnabled=False, isVisible=False)
    inputs = SimpleNamespace(itemById=lambda _identity: radius)
    application = SimpleNamespace(activeViewport=SimpleNamespace(refresh=Mock()))
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    draw_candidate = Mock(return_value=replacement)
    update_candidate = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_read_refine_placement", lambda *_args: placement)
    monkeypatch.setitem(vars(refine_commands), "draw_candidate_refine", draw_candidate)
    monkeypatch.setitem(vars(refine_commands), "update_candidate_refine", update_candidate)

    addin_module._update_refine_placement(
        state,
        inputs,
        position_manipulator=False,
    )

    assert state.candidate is replacement
    draw_candidate.assert_called_once_with(group, geometry)
    update_candidate.assert_not_called()


def test_edited_refine_geometry_reads_triad_and_resized_radius(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Convert the live triad frame and radius from centimeters to millimeters.
    """
    core_module = sys.modules["adsk.core"]
    triad = SimpleNamespace(
        isValidExpressions=True,
        transform=SimpleNamespace(
            getAsCoordinateSystem=lambda: (
                SimpleNamespace(x=1.0, y=2.0, z=3.0),
                SimpleNamespace(x=0.0, y=1.0, z=0.0),
                SimpleNamespace(x=0.0, y=0.0, z=1.0),
                SimpleNamespace(x=1.0, y=0.0, z=0.0),
            )
        ),
    )
    radius = SimpleNamespace(isValidExpression=True, value=1.8)
    core_module.TriadCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    inputs = SimpleNamespace(
        itemById=lambda identity: triad if identity == "refine_transform" else radius
    )

    geometry = addin_module._read_edited_refine_geometry(inputs)

    assert geometry == RefineGeometry((10.0, 20.0, 30.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), 18.0)


def test_refine_triad_reapplies_initial_world_transform(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Work around Fusion ignoring the matrix passed during triad creation.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    transform = object()
    triad = SimpleNamespace(transform=None)
    inputs = SimpleNamespace(addTriadCommandInput=Mock(return_value=triad))
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(
        vars(refine_commands), "_refine_geometry_transform", lambda _geometry: transform
    )

    result = addin_module._add_refine_transform_input(inputs, geometry)

    assert result is triad
    inputs.addTriadCommandInput.assert_called_once_with("refine_transform", transform)
    assert triad.transform is transform


def test_edit_refine_preview_redraws_current_triad_geometry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Rebuild the command-local marker during Fusion's preview event.
    """
    initial = _refine_control().refine_geometry
    assert initial is not None
    changed = replace(initial, origin_mm=(10.0, 20.0, 30.0))
    group = object()
    state = addin_module._EditRefineCommandState(UUID(int=1), REFINE_ID, group, initial)
    read_geometry = Mock(return_value=changed)
    update_editor = Mock()
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeViewport=viewport)
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_read_edited_refine_geometry", read_geometry)
    monkeypatch.setitem(vars(refine_commands), "update_refine_editor", update_editor)
    command_inputs = object()

    addin_module._EditRefineExecutePreviewHandler(state).notify(
        SimpleNamespace(command=SimpleNamespace(commandInputs=command_inputs))
    )

    assert state.geometry == changed
    read_geometry.assert_called_once_with(command_inputs)
    update_editor.assert_called_once_with(group, changed)
    viewport.refresh.assert_called_once()


def test_edit_refine_input_change_updates_existing_marker(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Apply drag and dialog edits through the immediate input-change event.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    state = addin_module._EditRefineCommandState(UUID(int=1), REFINE_ID, object(), geometry)
    preview = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_preview_edited_refine", preview)
    command_inputs = object()

    addin_module._EditRefineInputChangedHandler(state).notify(
        SimpleNamespace(inputs=command_inputs)
    )

    preview.assert_called_once_with(state, command_inputs)


def test_refine_editor_updates_one_graphics_transform_in_place(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Encode world position, orientation, and radius in the live graphics transform.
    """
    from wire_bundler.fusion import refine_graphics

    core_module = refine_graphics.adsk.core
    transform = SimpleNamespace(setCell=Mock(return_value=True))
    core_module.Matrix3D = SimpleNamespace(create=lambda: transform)  # type: ignore[attr-defined]
    geometry = RefineGeometry(
        (10.0, 20.0, 30.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        20.0,
    )
    group = SimpleNamespace(isValid=True, transform=None)

    addin_module.update_refine_editor(group, geometry)

    assert [item.args for item in transform.setCell.call_args_list] == [
        (0, 0, 0.0),
        (1, 0, 2.0),
        (2, 0, 0.0),
        (0, 1, 0.0),
        (1, 1, 0.0),
        (2, 1, 2.0),
        (0, 2, 1.0),
        (1, 2, 0.0),
        (2, 2, 0.0),
        (0, 3, 1.0),
        (1, 3, 2.0),
        (2, 3, 3.0),
    ]
    assert group.transform is transform


def test_refine_editor_hides_only_selected_persistent_marker(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep sibling refines visible while replacing the selected marker for editing.
    """
    from wire_bundler.fusion import refine_graphics

    geometry = _refine_control().refine_geometry
    assert geometry is not None
    sibling_id = UUID("30000000-0000-0000-0000-000000000100")
    selected = SimpleNamespace(id=str(REFINE_ID), isVisible=True)
    sibling = SimpleNamespace(id=str(sibling_id), isVisible=True)
    persistent_group = SimpleNamespace(
        count=2,
        item=lambda index: (selected, sibling)[index],
    )
    editor_group = SimpleNamespace(id="", name="")
    groups = SimpleNamespace(add=Mock(return_value=editor_group))
    design = SimpleNamespace(rootComponent=SimpleNamespace(customGraphicsGroups=groups))
    clear_spine = Mock()
    clear_persistent = Mock()
    draw_candidate = Mock()
    update_editor = Mock()
    monkeypatch.setattr(refine_graphics, "clear_refine_spine", clear_spine)
    monkeypatch.setattr(refine_graphics, "clear_refine_graphics", clear_persistent)
    monkeypatch.setattr(
        refine_graphics,
        "_find_group",
        lambda _design, _identity: persistent_group,
    )
    monkeypatch.setattr(refine_graphics, "draw_candidate_refine", draw_candidate)
    monkeypatch.setattr(refine_graphics, "update_refine_editor", update_editor)

    result = addin_module.draw_refine_editor(design, REFINE_ID, geometry)

    assert result is editor_group
    assert selected.isVisible is False
    assert sibling.isVisible is True
    clear_spine.assert_called_once_with(design)
    clear_persistent.assert_not_called()
    groups.add.assert_called_once_with()
    draw_candidate.assert_called_once()
    update_editor.assert_called_once_with(editor_group, geometry)


@pytest.mark.parametrize("cancelled", [False, True])
def test_edit_refine_destroy_restores_persistent_markers(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    cancelled: bool,
) -> None:
    """
    Reconcile every saved marker when editing ends through Save or Cancel.
    """
    design = object()
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeProduct=design, activeViewport=viewport)
    core_module = sys.modules["adsk.core"]
    fusion_module = sys.modules["adsk.fusion"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    fusion_module.Design = SimpleNamespace(cast=lambda product: product)  # type: ignore[attr-defined]
    clear_spine = Mock()
    reconcile = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "clear_refine_spine", clear_spine)
    monkeypatch.setitem(vars(refine_commands), "_reconcile_active_refines", reconcile)

    addin_module._EditRefineDestroyedHandler([]).notify(SimpleNamespace(isCancelled=cancelled))

    clear_spine.assert_called_once_with(design)
    reconcile.assert_called_once_with(application)
    viewport.refresh.assert_called_once_with()


def test_selecting_persistent_refine_opens_transform_editor(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Turn a normal viewport selection of a refine marker into an edit command.
    """
    refine_id = REFINE_ID
    refine = _refine_control()
    definition = replace(valid_harness, controls=(*valid_harness.controls, refine))
    command_definition = SimpleNamespace(execute=Mock(return_value=True))
    selections = SimpleNamespace(clear=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(
            activeSelections=selections,
            commandDefinitions=SimpleNamespace(itemById=lambda _identity: command_definition),
        )
    )
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(
        vars(refine_commands),
        "load_harnesses",
        lambda _gateway: (SimpleNamespace(definition=definition),),
    )
    monkeypatch.setitem(
        vars(refine_commands), "_create_harness_gateway", lambda _application: object()
    )
    marker = SimpleNamespace(
        id=str(refine_id),
        parent=SimpleNamespace(id=addin_module.REFINE_GRAPHICS_GROUP_ID),
    )

    addin_module._RefineActiveSelectionHandler().notify(
        SimpleNamespace(currentSelection=[SimpleNamespace(entity=marker)])
    )

    selections.clear.assert_called_once_with()
    command_definition.execute.assert_called_once_with()
    assert addin_module._runtime.pending_refine_edit.value == (
        definition.harness_id,
        refine_id,
    )


def test_refine_reconciliation_redraws_changed_geometry_with_same_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Rebuild a marker even when a resize preserves its persistent control UUID.
    """
    from wire_bundler.fusion import refine_graphics

    refine_id = REFINE_ID
    refine = _refine_control(18.0)
    definition = replace(valid_harness, controls=(*valid_harness.controls, refine))
    existing = SimpleNamespace(count=1, item=lambda _index: SimpleNamespace(id=str(refine_id)))
    marker = SimpleNamespace()
    created_group = SimpleNamespace()
    groups = SimpleNamespace(add=Mock(return_value=created_group))
    design = SimpleNamespace(rootComponent=SimpleNamespace(customGraphicsGroups=groups))
    clear = Mock()
    add_polyline = Mock(return_value=marker)
    monkeypatch.setattr(refine_graphics, "_find_group", lambda _design, _identity: existing)
    monkeypatch.setattr(refine_graphics, "clear_refine_graphics", clear)
    monkeypatch.setattr(refine_graphics, "_add_polyline", add_polyline)

    refine_graphics.reconcile_refine_graphics(design, (definition,))

    clear.assert_called_once_with(design)
    groups.add.assert_called_once_with()
    add_polyline.assert_called_once()
    assert marker.id == str(refine_id)


def test_refine_control_hover_highlights_persistent_marker(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Route a refine-row hover to Custom Graphics without requiring a profile token.
    """
    refine_id = REFINE_ID
    refine = _refine_control()
    definition = replace(valid_harness, controls=(*valid_harness.controls, refine))
    design = SimpleNamespace(rootComponent=object())
    selections = SimpleNamespace(clear=Mock(return_value=True), add=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(activeSelections=selections),
        activeViewport=SimpleNamespace(refresh=Mock()),
    )
    gateway = SimpleNamespace(
        read_harness_definition=lambda _harness_id: dumps(definition),
        harness_component=lambda _harness_id: object(),
    )
    marker_highlight = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "highlight_refine_graphics", marker_highlight)
    monkeypatch.setattr(addin_module, "highlight_route_members", lambda _design, _ids: 0)
    monkeypatch.setattr(addin_module, "generated_wire_bodies", lambda *_args: ())
    payload = json.dumps(
        {
            "harnessId": str(definition.harness_id),
            "memberType": "control",
            "memberId": str(refine_id),
        }
    )

    count = addin_module._highlight_member(application, payload)

    assert count == 1
    marker_highlight.assert_called_once_with(design, (refine_id,))
    assert not selections.add.called
