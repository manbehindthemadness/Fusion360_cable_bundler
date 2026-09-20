"""Focused Fusion UI regressions for native commands."""

from __future__ import annotations

from tests.fusion_ui_support import (
    REFINE_ID,
    UUID,
    Any,
    HarnessDefinition,
    Mock,
    RefineGeometry,
    SimpleNamespace,
    _PaletteLifecycleModule,
    _refine_control,
    dumps,
    importlib,
    json,
    pytest,
    replace,
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
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    return args, application, refine_commands


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


def test_edited_refine_geometry_clamps_zero_radius(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep an edited marker valid if Fusion reports zero during a drag event.
    """
    core_module = sys.modules["adsk.core"]
    triad = SimpleNamespace(
        isValidExpressions=True,
        transform=SimpleNamespace(
            getAsCoordinateSystem=lambda: (
                SimpleNamespace(x=1.0, y=2.0, z=3.0),
                SimpleNamespace(x=1.0, y=0.0, z=0.0),
                SimpleNamespace(x=0.0, y=1.0, z=0.0),
                SimpleNamespace(x=0.0, y=0.0, z=1.0),
            )
        ),
    )
    radius = SimpleNamespace(isValidExpression=True, value=0.0)
    core_module.TriadCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    core_module.DistanceValueCommandInput = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    inputs = SimpleNamespace(
        itemById=lambda identity: triad if identity == "refine_transform" else radius
    )

    geometry = addin_module._read_edited_refine_geometry(inputs)

    assert geometry.display_radius_mm == 0.5


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
    monkeypatch.setattr(
        "wire_bundler.fusion.ui.commands.refine_parts.inputs._refine_geometry_transform",
        lambda _geometry: transform,
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
    state = addin_module._EditRefineCommandState(UUID(int=1), REFINE_ID, initial)
    read_geometry = Mock(return_value=changed)
    design = object()
    group = object()
    draw_editor = Mock(return_value=group)
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeViewport=viewport)
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_read_edited_refine_geometry", read_geometry)
    monkeypatch.setitem(vars(refine_commands), "_require_active_design", lambda _app: design)
    monkeypatch.setitem(vars(refine_commands), "draw_refine_editor", draw_editor)
    command_inputs = object()
    args = SimpleNamespace(
        command=SimpleNamespace(commandInputs=command_inputs),
        isValidResult=True,
    )

    addin_module._EditRefineExecutePreviewHandler(state).notify(args)

    assert state.geometry == changed
    assert state.group is group
    read_geometry.assert_called_once_with(command_inputs)
    draw_editor.assert_called_once_with(design, REFINE_ID, changed)
    viewport.refresh.assert_called_once()
    assert args.isValidResult is False


def test_edit_refine_input_change_updates_existing_marker(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Apply drag and dialog edits through the immediate input-change event.
    """
    geometry = _refine_control().refine_geometry
    assert geometry is not None
    state = addin_module._EditRefineCommandState(UUID(int=1), REFINE_ID, geometry)
    preview = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "_preview_edited_refine", preview)
    command_inputs = object()

    addin_module._EditRefineInputChangedHandler(state).notify(
        SimpleNamespace(inputs=command_inputs)
    )

    preview.assert_called_once_with(state, command_inputs)


def test_edit_refine_execute_finalizes_graphics_inside_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Commit the geometry edit and persistent marker without preview graphics.
    """
    geometry = _refine_control(18.0).refine_geometry
    assert geometry is not None
    state = addin_module._EditRefineCommandState(
        UUID(int=1),
        REFINE_ID,
        geometry,
    )
    args, application, refine_commands = _refine_execute_context()
    update_refine = Mock()
    finalize = Mock()
    send_state = Mock()
    monkeypatch.setitem(
        vars(refine_commands),
        "_read_edited_refine_geometry",
        lambda _inputs: geometry,
    )
    monkeypatch.setitem(vars(refine_commands), "update_pathway_refine", update_refine)
    monkeypatch.setitem(vars(refine_commands), "_create_harness_gateway", lambda _app: object())
    monkeypatch.setitem(vars(refine_commands), "_refresh_active_preview", lambda *_args: "")
    monkeypatch.setitem(vars(refine_commands), "_finalize_refine_graphics", finalize)
    monkeypatch.setitem(vars(refine_commands), "_send_palette_state", send_state)

    addin_module._EditRefineExecuteHandler(state).notify(args)

    update_refine.assert_called_once()
    finalize.assert_called_once_with(application)
    send_state.assert_called_once_with(application, "Updated refine point.")
    assert not args.executeFailed


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

    refine_graphics.update_refine_editor(group, geometry)

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


def test_edit_refine_destroy_releases_handlers_without_graphics_mutation(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Let Fusion restore edited graphics by aborting its preview transaction.
    """
    release = Mock()
    monkeypatch.setitem(vars(addin_module._runtime.handler_registry), "release", release)
    owned_handler = object()
    destroyed = addin_module._EditRefineDestroyedHandler([owned_handler])

    destroyed.notify(SimpleNamespace())

    release.assert_called_once_with(owned_handler, destroyed)


def test_finalize_refine_graphics_replaces_command_group(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Clear the temporary group before rebuilding saved refine markers.
    """
    design = object()
    viewport = SimpleNamespace(refresh=Mock())
    application = SimpleNamespace(activeProduct=design, activeViewport=viewport)
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda product: product)  # type: ignore[attr-defined]
    clear_spine = Mock()
    reconcile = Mock()
    refine_commands = importlib.import_module("wire_bundler.fusion.ui.commands.refines")
    monkeypatch.setitem(vars(refine_commands), "clear_refine_spine", clear_spine)
    monkeypatch.setitem(vars(refine_commands), "_reconcile_active_refines", reconcile)

    addin_module._finalize_refine_graphics(application)

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
    monkeypatch.setattr(addin_module, "highlight_route_members", lambda _design, _ids, **_kwargs: 0)
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
