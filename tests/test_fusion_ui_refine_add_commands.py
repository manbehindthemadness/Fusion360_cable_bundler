"""Focused Fusion UI regressions for native commands."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Any,
    GateFrame,
    Mock,
    SimpleNamespace,
    Vector3,
    _PaletteLifecycleModule,
    _refine_control,
    importlib,
    pytest,
    sys,
)


# noinspection DuplicatedCode
def _command_execute_args() -> tuple[SimpleNamespace, object]:
    """
    Build mutable command-event arguments with one opaque input collection.
    """
    inputs = object()
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=inputs),
        executeFailed=False,
        executeFailedMessage="",
    )
    return args, inputs


def _refine_execute_context() -> tuple[SimpleNamespace, SimpleNamespace, Any]:
    """
    Configure the shared application boundary for refine execute handlers.
    """
    args, _inputs = _command_execute_args()
    application = SimpleNamespace()
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    return args, application, refine_commands


def test_refine_selection_accepts_only_command_spine(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Exclude persistent markers and unrelated Custom Graphics from placement.
    """
    state = addin_module._RefineCommandState(UUID(int=1), UUID(int=2), object())
    handler = addin_module._RefinePreSelectHandler(state)
    accepted = SimpleNamespace(
        selection=SimpleNamespace(
            entity=SimpleNamespace(id=addin_module.REFINE_SPINE_ENTITY_ID),
            point=SimpleNamespace(x=1.0, y=2.0, z=3.0),
        ),
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
    assert state.preselected_point_mm == Vector3(10.0, 20.0, 30.0)


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


@pytest.mark.parametrize(("radius_cm", "expected_mm"), ((1.0, 10.0), (0.0, 0.5)))
def test_refine_selection_uses_click_point_and_clamped_centimeter_radius(
    addin_module: _PaletteLifecycleModule,
    radius_cm: float,
    expected_mm: float,
) -> None:
    """
    Project the click while converting and clamping Fusion's centimeter radius.
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
    radius_input = SimpleNamespace(isValidExpression=True, value=radius_cm)
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
    assert placement.geometry.display_radius_mm == expected_mm


def test_refine_radius_input_starts_at_inclusive_half_millimeter_minimum(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Configure Fusion's manipulator to stop before its radius reaches zero.
    """
    core_module = sys.modules["adsk.core"]
    initial_value = object()
    create_value = Mock(return_value=initial_value)
    core_module.ValueInput = SimpleNamespace(createByString=create_value)  # type: ignore[attr-defined]
    radius = SimpleNamespace(minimumValue=None, isMinimumValueInclusive=False)
    inputs = SimpleNamespace(addDistanceValueCommandInput=Mock(return_value=radius))

    result = addin_module._add_refine_radius_input(inputs)

    assert result is radius
    create_value.assert_called_once_with("0.5 mm")
    inputs.addDistanceValueCommandInput.assert_called_once_with(
        "refine_radius",
        "Marker Radius",
        initial_value,
    )
    assert radius.minimumValue == pytest.approx(0.05)
    assert radius.isMinimumValueInclusive


def test_refine_radius_input_clamps_legacy_initial_radius(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Open a legacy subminimum refine at the supported editable radius.
    """
    core_module = sys.modules["adsk.core"]
    create_value = Mock(return_value=object())
    core_module.ValueInput = SimpleNamespace(createByString=create_value)  # type: ignore[attr-defined]
    inputs = SimpleNamespace(
        addDistanceValueCommandInput=Mock(
            return_value=SimpleNamespace(
                minimumValue=None,
                isMinimumValueInclusive=False,
            )
        )
    )

    addin_module._add_refine_radius_input(inputs, 0.1)

    create_value.assert_called_once_with("0.5 mm")


@pytest.mark.parametrize(
    ("radius_cm", "expected_mm"),
    ((0.0, 0.5), (0.01, 0.5), (0.05, 0.5), (1.8, 18.0)),
)
def test_refine_radius_read_clamps_at_half_millimeter(
    addin_module: _PaletteLifecycleModule,
    radius_cm: float,
    expected_mm: float,
) -> None:
    """
    Keep transient drag values at a valid visible radius.
    """
    radius = SimpleNamespace(isValidExpression=True, value=radius_cm)

    assert addin_module._read_refine_radius_mm(radius) == pytest.approx(expected_mm)


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


def test_refine_placement_drag_updates_captured_radius_without_graphics(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Update stored placement while leaving document graphics to executePreview.
    """
    geometry = _refine_control(18.0).refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    placement = refine_commands.RefinePlacement(1, geometry)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        placement=placement,
    )
    radius = SimpleNamespace(
        isValidExpression=True,
        value=2.4,
        isEnabled=False,
        isVisible=False,
        setManipulator=Mock(return_value=True),
    )
    selection = SimpleNamespace(selectionCount=0)
    inputs = SimpleNamespace(
        itemById=lambda identity: selection if identity == "refine_spine" else radius
    )
    core_module = sys.modules["adsk.core"]
    core_module.SelectionCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]

    addin_module._update_refine_placement(
        state,
        inputs,
        position_manipulator=False,
    )

    assert state.placement is not placement
    assert state.placement.geometry.display_radius_mm == pytest.approx(24.0)
    assert radius.isEnabled
    assert radius.isVisible
    radius.setManipulator.assert_not_called()


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
    )
    inputs = object()
    command = SimpleNamespace(doExecutePreview=Mock(return_value=True))
    update_placement = Mock()
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_update_refine_placement", update_placement)

    addin_module._RefineMouseDragHandler(state, inputs, command).notify(SimpleNamespace())

    update_placement.assert_called_once_with(
        state,
        inputs,
        position_manipulator=False,
    )
    command.doExecutePreview.assert_called_once_with()


def test_refine_activation_starts_transaction_owned_preview(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Delay initial graphics until Fusion can contain them in executePreview.
    """
    command = SimpleNamespace(doExecutePreview=Mock(return_value=True))

    addin_module._RefineActivateHandler().notify(SimpleNamespace(command=command))

    command.doExecutePreview.assert_called_once_with()


def test_add_refine_activation_requires_selection_after_initial_preview(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep OK present but disabled only after Fusion has drawn the selectable path.
    """
    events = Mock()
    preview = Mock(return_value=True)
    require_selection = Mock(return_value=True)
    events.attach_mock(preview, "preview")
    events.attach_mock(require_selection, "require_selection")
    command = SimpleNamespace(doExecutePreview=preview)
    selection = SimpleNamespace(setSelectionLimits=require_selection)

    addin_module._RefineActivateHandler(selection).notify(SimpleNamespace(command=command))

    assert [event[0] for event in events.mock_calls] == ["preview", "require_selection"]
    selection.setSelectionLimits.assert_called_once_with(1, 1)


def test_add_refine_select_captures_click_before_preview_rollback(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Redraw from stored placement instead of retaining a selected preview entity.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    spine = object()
    placement = refine_commands.RefinePlacement(1, geometry)
    state = addin_module._RefineCommandState(UUID(int=1), UUID(int=2), spine)
    command = SimpleNamespace(doExecutePreview=Mock(return_value=True))
    radius = SimpleNamespace(
        isValidExpression=True,
        value=1.0,
        isEnabled=False,
        isVisible=False,
        setManipulator=Mock(return_value=True),
    )
    inputs = SimpleNamespace(itemById=lambda _identity: radius)
    selection_input = SimpleNamespace(
        setSelectionLimits=Mock(return_value=True),
        clearSelection=Mock(return_value=True),
    )
    selected = SimpleNamespace(
        entity=SimpleNamespace(id=addin_module.REFINE_SPINE_ENTITY_ID),
        point=SimpleNamespace(x=1.0, y=2.0, z=3.0),
    )
    core_module = sys.modules["adsk.core"]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.Point3D = SimpleNamespace(create=Mock(return_value=object()))  # type: ignore[attr-defined]
    core_module.Vector3D = SimpleNamespace(create=Mock(return_value=object()))  # type: ignore[attr-defined]
    place = Mock(return_value=placement)
    monkeypatch.setitem(vars(refine_commands), "place_refine", place)

    addin_module._RefineSelectHandler(
        state,
        command,
        inputs,
        selection_input,
    ).notify(SimpleNamespace(selection=selected))

    selected_point = Vector3(10.0, 20.0, 30.0)
    place.assert_called_once_with(spine, selected_point, 10.0)
    assert state.placement is placement
    assert state.preselected_point_mm == selected_point
    assert radius.isEnabled
    assert radius.isVisible
    selection_input.setSelectionLimits.assert_called_once_with(0, 1)
    selection_input.clearSelection.assert_called_once_with()
    command.doExecutePreview.assert_called_once_with()


def test_add_refine_validation_allows_initial_preview_before_selection(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep Fusion preview-valid before activation makes selection mandatory.
    """
    state = addin_module._RefineCommandState(UUID(int=1), UUID(int=2), object())
    args = SimpleNamespace(inputs=object(), areInputsValid=False)

    addin_module._RefineValidateInputsHandler(state).notify(args)

    assert args.areInputsValid is True


def test_add_refine_selection_captures_placement(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Retain a pathway placement when its selection input changes.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        placement=refine_commands.RefinePlacement(1, geometry),
    )
    update = Mock()
    monkeypatch.setitem(vars(refine_commands), "_update_refine_placement", update)
    inputs = object()

    addin_module._RefineInputChangedHandler(state).notify(SimpleNamespace(inputs=inputs))

    update.assert_called_once_with(state, inputs)


def test_add_refine_uses_preselection_after_preview_invalidates_selection(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the clicked point when Fusion rolls back its selectable preview.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    spine = object()
    clicked_point = Vector3(10.0, 20.0, 30.0)
    placement = refine_commands.RefinePlacement(1, geometry)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        spine,
        preselected_point_mm=clicked_point,
    )
    selection = SimpleNamespace(selectionCount=1, selection=lambda _index: None)
    radius = SimpleNamespace(
        isValidExpression=True,
        value=1.0,
        isEnabled=False,
        isVisible=False,
        setManipulator=Mock(return_value=True),
    )
    inputs = SimpleNamespace(
        itemById=lambda identity: selection if identity == "refine_spine" else radius
    )
    core_module = sys.modules["adsk.core"]
    core_module.SelectionCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.Point3D = SimpleNamespace(create=Mock(return_value=object()))  # type: ignore[attr-defined]
    core_module.Vector3D = SimpleNamespace(create=Mock(return_value=object()))  # type: ignore[attr-defined]
    place = Mock(return_value=placement)
    monkeypatch.setattr(
        "cable_bundler.fusion.ui.commands.refine_parts.placement.place_refine",
        place,
    )

    addin_module._RefineInputChangedHandler(state).notify(SimpleNamespace(inputs=inputs))

    place.assert_called_once_with(spine, clicked_point, 10.0)
    assert state.placement is placement
    assert radius.isEnabled
    assert radius.isVisible


def test_add_refine_execute_finalizes_graphics_inside_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Commit only persisted state and persistent markers in the final transaction.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    placement = refine_commands.RefinePlacement(1, geometry)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        placement=placement,
    )
    radius = SimpleNamespace(isValidExpression=True, value=1.8)
    args, application, refine_commands = _refine_execute_context()
    args.command.commandInputs = SimpleNamespace(itemById=lambda _identity: radius)
    core_module = sys.modules["adsk.core"]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    add_refine = Mock()
    finalize = Mock()
    send_state = Mock()
    monkeypatch.setitem(vars(refine_commands), "add_pathway_refine", add_refine)
    monkeypatch.setitem(vars(refine_commands), "_create_harness_gateway", lambda _app: object())
    monkeypatch.setitem(vars(refine_commands), "_refresh_active_preview", lambda *_args: "")
    monkeypatch.setitem(vars(refine_commands), "_finalize_refine_graphics", finalize)
    monkeypatch.setitem(vars(refine_commands), "_send_palette_state", send_state)

    addin_module._RefineExecuteHandler(state).notify(args)

    add_refine.assert_called_once()
    finalize.assert_called_once_with(application)
    send_state.assert_called_once_with(application, "Added refine point.")
    assert not args.executeFailed


def test_add_refine_destroy_restores_solids_and_releases_handlers(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Restore hidden geometry after Fusion rolls back preview graphics.
    """
    release = Mock()
    monkeypatch.setitem(vars(addin_module._runtime.handler_registry), "release", release)
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    restore = Mock()
    monkeypatch.setitem(vars(refine_commands), "restore_generated_cable_group_visibility", restore)
    visibility = ((object(), True),)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        solid_visibility=visibility,
    )
    refresh = Mock()
    application = SimpleNamespace(activeViewport=SimpleNamespace(refresh=refresh))
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    owned_handler = object()
    destroyed = addin_module._RefineDestroyedHandler(state, [owned_handler])

    destroyed.notify(SimpleNamespace())

    restore.assert_called_once_with(visibility)
    refresh.assert_called_once_with()
    release.assert_called_once_with(owned_handler, destroyed)


def test_add_refine_preview_rebuilds_transaction_owned_graphics(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Recreate the spine and candidate after Fusion aborts the prior preview.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    refine_commands = importlib.import_module("cable_bundler.fusion.ui.commands.refines")
    placement = refine_commands.RefinePlacement(1, geometry)
    state = addin_module._RefineCommandState(
        UUID(int=1),
        UUID(int=2),
        object(),
        placement=placement,
    )
    design = object()
    group = object()
    replacement = object()
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeViewport=viewport)
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    draw_spine = Mock(return_value=(group, object()))
    draw_candidate = Mock(return_value=replacement)
    monkeypatch.setattr(
        "cable_bundler.fusion.ui.commands.refine_parts.placement._require_active_design",
        lambda _app: design,
    )
    monkeypatch.setattr(
        "cable_bundler.fusion.ui.commands.refine_parts.placement.draw_pathway_spine",
        draw_spine,
    )
    monkeypatch.setattr(
        "cable_bundler.fusion.ui.commands.refine_parts.placement.draw_candidate_refine",
        draw_candidate,
    )
    args = SimpleNamespace(isValidResult=True)

    addin_module._RefineExecutePreviewHandler(state).notify(args)

    assert state.group is group
    assert state.candidate is replacement
    draw_spine.assert_called_once_with(design, state.spine)
    draw_candidate.assert_called_once_with(group, geometry)
    viewport.refresh.assert_called_once_with()
    assert args.isValidResult is False
