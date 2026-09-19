"""Focused Fusion UI regressions for palette."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    Mock,
    PathwayEndpoint,
    SimpleNamespace,
    WireColor,
    WireGroupDefinition,
    WireStripe,
    _PaletteLifecycleModule,
    cast,
    dumps,
    json,
    loads,
    pytest,
    replace,
    sys,
)


def test_palette_is_shown_during_command_creation(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Show the palette immediately when Fusion creates the input-free command.
    """
    shown_applications: list[object] = []
    application = object()
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        addin_module,
        "_show_palette",
        shown_applications.append,
    )

    created_handler = addin_module._ShowPaletteCreatedHandler()
    created_handler.notify(SimpleNamespace(command=object()))

    assert shown_applications == [application]


def test_palette_opens_at_relationship_graphic_working_size(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Give the editor enough initial room for its connection-map labels and controls.
    """
    palette = SimpleNamespace(
        incomingFromHTML=SimpleNamespace(add=Mock(return_value=True)),
        navigatingURL=SimpleNamespace(add=Mock(return_value=True)),
        htmlFileURL="palette.html",
    )
    palettes = SimpleNamespace(
        itemById=Mock(return_value=None),
        add=Mock(return_value=palette),
    )
    application = SimpleNamespace(userInterface=SimpleNamespace(palettes=palettes))
    monkeypatch.setattr(addin_module, "_send_palette_state", lambda _application: None)
    monkeypatch.setattr(addin_module, "_log_to_fusion", lambda _message: None)

    addin_module._show_palette(application)

    assert palettes.add.call_args.args[6:8] == (840, 760)
    assert palettes.add.call_args.args[3] is False
    assert palette.dockingOption == "vertical"
    assert palette.dockingState == "right"
    assert palette.isVisible is True


def test_existing_palette_is_redocked_and_revealed(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Recover a floating palette that macOS moved outside Fusion's fullscreen Space.
    """
    palette = SimpleNamespace(dockingState="floating", isVisible=True)
    palettes = SimpleNamespace(itemById=Mock(return_value=palette))
    application = SimpleNamespace(userInterface=SimpleNamespace(palettes=palettes))
    monkeypatch.setattr(addin_module, "_send_palette_state", lambda _application: None)

    addin_module._show_palette(application)

    assert palette.dockingState == "right"
    assert palette.dockingOption == "vertical"
    assert palette.isVisible is True


def test_palette_remains_usable_when_fusion_rejects_redocking(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reveal and refresh an existing palette when Fusion rejects area placement.
    """

    class _Palette:
        """
        Reproduce Fusion's docking-state assignment failure.
        """

        def __init__(self) -> None:
            """
            Start hidden with no docking option assigned.
            """
            self.dockingOption = None
            self.isVisible = False

        # noinspection PyPep8Naming
        @property
        def dockingState(self) -> str:
            """
            Return the current floating state.
            """
            return "floating"

        # noinspection PyPep8Naming
        @dockingState.setter
        def dockingState(self, _value: str) -> None:
            """
            Reproduce Fusion's internal area-placement rejection.
            """
            raise RuntimeError("InternalValidationError: setAreaPlacement")

    palette = _Palette()
    application = SimpleNamespace(
        userInterface=SimpleNamespace(palettes=SimpleNamespace(itemById=Mock(return_value=palette)))
    )
    sent = Mock()
    logged: list[str] = []
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    monkeypatch.setattr(addin_module, "_log_to_fusion", logged.append)

    addin_module._show_palette(application)

    assert palette.isVisible
    sent.assert_called_once_with(application)
    assert logged == [
        "Harness Builder could not restore right docking: InternalValidationError: setAreaPlacement"
    ]


def test_route_capacity_error_fails_preview_command(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep expected preview rejection actionable through Fusion's command failure.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document)
    logged_messages: list[str] = []
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        addin_module,
        "_preview_routes",
        Mock(side_effect=ValueError("Gate 4 cannot fit 3 wires.")),
    )
    monkeypatch.setattr(addin_module, "_log_to_fusion", logged_messages.append)
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")
    addin_module._PaletteEditExecuteHandler(("preview_routes", "{}", document)).notify(args)
    assert args.executeFailed
    assert args.executeFailedMessage == "Gate 4 cannot fit 3 wires."
    assert len(logged_messages) == 1
    assert logged_messages[0].startswith("Harness command failed: Gate 4 cannot fit 3 wires.")
    assert "Traceback (most recent call last)" in logged_messages[0]


def test_damaged_deletion_runs_inside_palette_command(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Delete and refresh palette state within the native Fusion transaction.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    delete = Mock(return_value="Deleted damaged harness Broken Harness.")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_delete_damaged_harness", delete)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"deletionToken": "current-token"})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(("delete_damaged_harness", payload, document)).notify(
        args
    )

    delete.assert_called_once_with(application, payload)
    application.activeViewport.refresh.assert_called_once_with()
    sent.assert_called_once_with(application, "Deleted damaged harness Broken Harness.")
    assert not args.executeFailed


def test_palette_edit_deletes_standalone_end_by_connection_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the disconnected-end identity and delegate the metadata deletion.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    gateway = object()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "remove_standalone_end", remove)

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_standalone_end",
        json.dumps({"harnessId": str(harness_id), "connectionId": str(connection_id)}),
    )

    remove.assert_called_once_with(harness_id, connection_id, gateway)
    assert notice == "Deleted standalone end."


def test_palette_edit_renames_standalone_end_by_connection_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the end identity and delegate its connection-name edit.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    gateway = object()
    rename = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "rename_standalone_end", rename)

    notice = addin_module._apply_palette_edit(
        object(),
        "rename_standalone_end",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "name": "Bulkhead outlet",
            }
        ),
    )

    rename.assert_called_once_with(harness_id, connection_id, "Bulkhead outlet", gateway)
    assert notice == "Saved end name."


def test_palette_edit_saves_wire_editor_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse all staged end and grouping changes into one application call.
    """
    harness_id = UUID(int=1)
    left_pathway_id = UUID(int=2)
    right_pathway_id = UUID(int=3)
    left_connection_id = UUID(int=4)
    right_connection_id = UUID(int=5)
    deleted_connection_id = UUID(int=6)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "save_wire_editor", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "save_wire_editor",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "leftBoundary": {"pathwayId": str(left_pathway_id), "endpoint": "start"},
                "rightBoundary": {"pathwayId": str(right_pathway_id), "endpoint": "end"},
                "pairings": [
                    {
                        "leftConnectionId": str(left_connection_id),
                        "rightConnectionId": str(right_connection_id),
                    }
                ],
                "detachedConnectionIds": [str(left_connection_id)],
                "renames": [{"connectionId": str(right_connection_id), "name": "Right"}],
                "deletedConnectionIds": [str(deleted_connection_id)],
            }
        ),
    )

    save.assert_called_once()
    arguments = save.call_args.args
    assert arguments[:5] == (
        harness_id,
        left_pathway_id,
        addin_module.PathwayEndpoint.START,
        right_pathway_id,
        addin_module.PathwayEndpoint.END,
    )
    assert arguments[-1] is gateway
    assert notice == "Saved Route Editor changes."


def test_palette_edit_saves_connected_wire_properties_atomically(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse diameter and nullable construction-material overrides into one edit.
    """
    harness_id = UUID(int=1)
    wire_group_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_wire_group_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_wire_group_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "wireGroupId": str(wire_group_id),
                "diameterMm": 2.75,
                "insulationMaterial": "ETFE",
                "conductorMaterial": None,
                "manufacturer": "",
                "partNumber": "WB-42",
                "notes": "Install as matched stock",
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        wire_group_id,
        2.75,
        "ETFE",
        None,
        "",
        "WB-42",
        "Install as matched stock",
        gateway,
    )
    assert notice == "Saved connected-wire properties."


def test_palette_edit_saves_harness_properties_without_visual_materials(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the property-only payload without requiring appearance or stripe values.
    """
    harness_id = UUID(int=1)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_harness_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_harness_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "insulationMaterial": "ETFE",
                "conductorMaterial": "Tinned Copper",
                "manufacturer": "Acme",
                "partNumber": "WB-42",
                "notes": "Matched stock",
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        "ETFE",
        "Tinned Copper",
        "Acme",
        "WB-42",
        "Matched stock",
        gateway,
    )
    assert notice == "Saved harness properties."


def test_palette_edit_deletes_pathway_by_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Translate the master-diagram deletion into one application edit.
    """
    harness_id = UUID(int=1)
    pathway_id = UUID(int=2)
    gateway = object()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "remove_pathway", remove)

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_pathway",
        json.dumps({"harnessId": str(harness_id), "pathwayId": str(pathway_id)}),
    )

    remove.assert_called_once_with(harness_id, pathway_id, gateway)
    assert notice == "Deleted pathway branch."


def test_palette_edit_deletes_junction_by_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Translate the master-diagram junction deletion into one application edit.
    """
    harness_id = UUID(int=1)
    junction_id = UUID(int=2)
    gateway = object()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "remove_junction", remove)

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_junction",
        json.dumps({"harnessId": str(harness_id), "junctionId": str(junction_id)}),
    )

    remove.assert_called_once_with(harness_id, junction_id, gateway)
    assert notice == "Deleted junction."


@pytest.mark.parametrize("action", ["rename_pathway", "set_interpolation"])
def test_palette_edit_waits_for_execute_and_releases_handlers(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """
    Queue without changing data, then group persistence and preview in execute.
    """
    document = object()
    definition = Mock(execute=Mock(return_value=True))
    application = SimpleNamespace(
        activeDocument=document,
        activeViewport=Mock(),
        userInterface=SimpleNamespace(
            commandDefinitions=Mock(itemById=Mock(return_value=definition))
        ),
    )
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Renamed wire.")
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(UUID(int=1))})
    addin_module._open_palette_edit(application, action, payload)
    applied.assert_not_called()
    handlers: list[object] = []
    cleanup: list[object] = []
    command = SimpleNamespace(
        execute=Mock(add=Mock(side_effect=lambda handler: handlers.append(handler) or True)),
        destroy=Mock(add=Mock(side_effect=lambda handler: cleanup.append(handler) or True)),
    )
    addin_module._PaletteEditCreatedHandler().notify(SimpleNamespace(command=command))
    applied.assert_not_called()
    args = SimpleNamespace(executeFailed=False)
    cast(Mock, handlers[0]).notify(args)
    applied.assert_called_once_with(application, action, payload)
    refreshed.assert_called_once_with(application, UUID(int=1), ensure_visible=False)
    assert not args.executeFailed
    cast(Mock, cleanup[0]).notify(SimpleNamespace())
    assert handlers[0] not in addin_module._runtime.handlers
    assert cleanup[0] not in addin_module._runtime.handlers


def test_pathway_deletion_runs_in_one_native_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reconcile deleted refine graphics before the native deletion command commits.
    """
    document = object()
    harness_id = UUID(int=1)
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Deleted pathway branch.")
    reconciled = Mock()
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "reconcile_active_refines", reconciled)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id), "pathwayId": str(UUID(int=2))})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(("remove_pathway", payload, document)).notify(args)

    applied.assert_called_once_with(application, "remove_pathway", payload)
    reconciled.assert_called_once_with(application)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=False)
    application.activeViewport.refresh.assert_called_once_with()
    sent.assert_called_once_with(application, "Deleted pathway branch.")
    assert not args.executeFailed


def test_junction_deletion_runs_in_one_native_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reconcile deleted refine graphics before the native junction deletion commits.
    """
    document = object()
    harness_id = UUID(int=1)
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Deleted junction.")
    reconciled = Mock()
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "reconcile_active_refines", reconciled)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id), "junctionId": str(UUID(int=2))})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(("remove_junction", payload, document)).notify(args)

    applied.assert_called_once_with(application, "remove_junction", payload)
    reconciled.assert_called_once_with(application)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=False)
    application.activeViewport.refresh.assert_called_once_with()
    sent.assert_called_once_with(application, "Deleted junction.")
    assert not args.executeFailed


def test_material_save_applies_existing_bodies_and_preview(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Apply saved material settings to persistent solids and active graphics together.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    harness_id = UUID(int=1)
    applied = Mock(return_value="Saved harness wire-material defaults.")
    applied_bodies = Mock(return_value="Applied materials to 2 generated wires.")
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_apply_generated_materials", applied_bodies)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id)})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(
        ("set_harness_material_defaults", payload, document)
    ).notify(args)

    applied_bodies.assert_called_once_with(application, harness_id)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=True)
    sent.assert_called_once_with(
        application,
        "Saved harness wire-material defaults. Applied materials to 2 generated wires.",
    )
    assert not args.executeFailed


def test_connected_wire_property_save_refreshes_only_group_preview(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refresh transient group graphics without applying legacy generated-wire materials.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    harness_id = UUID(int=1)
    applied = Mock(return_value="Saved connected-wire properties.")
    applied_bodies = Mock()
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_apply_generated_materials", applied_bodies)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps(
        {
            "harnessId": str(harness_id),
            "wireGroupId": str(UUID(int=2)),
            "diameterMm": 2.75,
            "insulationMaterial": "ETFE",
            "conductorMaterial": None,
            "manufacturer": "",
            "partNumber": "WB-42",
            "notes": "Install as matched stock",
        }
    )
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(
        ("set_wire_group_properties", payload, document)
    ).notify(args)

    applied_bodies.assert_not_called()
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=True)
    sent.assert_called_once_with(application, "Saved connected-wire properties.")
    assert not args.executeFailed


def test_material_refresh_shows_striped_preview_when_none_is_active(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create visible stripe graphics as direct feedback for Apply and Save.
    """
    stripe = WireStripe(WireColor("White", 245, 245, 245), 0.2)
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, stripes=(stripe,)),
        wire_groups=(
            WireGroupDefinition(
                UUID(int=9902),
                (
                    valid_harness.connections[0].connection_id,
                    valid_harness.connections[1].connection_id,
                ),
            ),
        ),
    )
    design = object()
    application = SimpleNamespace(activeProduct=design)
    gateway = SimpleNamespace(read_harness_definition=lambda _identity: dumps(definition))
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda product: product)  # type: ignore[attr-defined]
    show = Mock(return_value=(object(),))
    refresh = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "show_route_previews", show)
    monkeypatch.setattr(addin_module, "refresh_route_previews", refresh)

    assert (
        addin_module._refresh_active_preview(
            application,
            definition.harness_id,
            ensure_visible=True,
        )
        == ""
    )

    show.assert_called_once_with(design, definition)
    refresh.assert_not_called()


def test_palette_edit_rejects_document_switch(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Do not apply delayed palette requests to a different active document.
    """
    application = SimpleNamespace(activeDocument=object())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_log_to_fusion", Mock())
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")
    addin_module._PaletteEditExecuteHandler(("remove_pathway", "{}", object())).notify(args)
    assert args.executeFailed
    assert "document changed" in args.executeFailedMessage
    applied.assert_not_called()


def test_palette_command_launch_failure_releases_request(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Allow a retry after Fusion declines to launch a queued edit.
    """
    definition = Mock(execute=Mock(return_value=False))
    application = SimpleNamespace(
        activeDocument=object(),
        userInterface=SimpleNamespace(
            commandDefinitions=Mock(itemById=Mock(return_value=definition))
        ),
    )
    addin_module._runtime.pending_palette_edit.clear()
    with pytest.raises(RuntimeError, match="could not execute"):
        addin_module._open_palette_edit(application, "rename_pathway", "{}")
    assert addin_module._runtime.pending_palette_edit.value is None


@pytest.mark.parametrize("target", ["gate", "end", "defaults"])
def test_interpolation_bridge_persists_selected_target(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    target: str,
) -> None:
    """
    Translate popup distances into one complete metadata write with stable target identity.
    """
    gateway = Mock(read_harness_definition=Mock(return_value=dumps(valid_harness)))
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    target_id = (
        valid_harness.controls[0].control_id
        if target == "gate"
        else valid_harness.connections[0].connection_id
    )
    request = {
        "harnessId": str(valid_harness.harness_id),
        "target": target,
        "targetId": str(target_id),
        "memberId": str(valid_harness.connections[0].member_identities[0]),
        "settings": {"approach_mm": 2, "departure_mm": None},
        "endDefaults": {"approach_mm": 1, "departure_mm": 3},
        "minimumClearanceMm": 0.35,
        "autoTransitionPreset": "loose",
    }
    addin_module._apply_palette_edit(object(), "set_interpolation", json.dumps(request))
    gateway.replace_harness_definition.assert_called_once()
    saved = loads(gateway.replace_harness_definition.call_args.args[1])
    actual = (
        saved.gate_defaults
        if target == "defaults"
        else saved.controls[0].interpolation
        if target == "gate"
        else saved.connections[0].member_settings[0]
    )
    assert actual.approach_mm == 2
    assert actual.departure_mm is None
    assert saved.wire_groups == valid_harness.wire_groups
    if target == "defaults":
        assert saved.end_defaults.departure_mm == 3
        assert saved.minimum_clearance_mm == 0.35
        assert saved.auto_transition_preset.value == "loose"
        assert saved.connections == valid_harness.connections
        assert saved.controls == valid_harness.controls


def test_junction_relationship_bridge_persists_endpoint_list(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Translate palette endpoint selections into the typed application edit.
    """
    control = ControlStructure(
        UUID("37000000-0000-0000-0000-000000000001"),
        "Junction Gate",
        ControlKind.ROUTING_GATE,
        "junction-token",
    )
    junction = JunctionDefinition(
        UUID("38000000-0000-0000-0000-000000000001"),
        "Junction 01",
        control.control_id,
    )
    definition = replace(
        valid_harness,
        controls=(*valid_harness.controls, control),
        junctions=(junction,),
    )
    gateway = Mock(read_harness_definition=Mock(return_value=dumps(definition)))
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    request = {
        "harnessId": str(definition.harness_id),
        "junctionId": str(junction.junction_id),
        "pathwayRelationships": [
            {
                "pathwayId": str(definition.pathways[0].pathway_id),
                "endpoint": "end",
            }
        ],
    }

    notice = addin_module._apply_palette_edit(
        object(),
        "update_junction_relationships",
        json.dumps(request),
    )

    saved = loads(gateway.replace_harness_definition.call_args.args[1])
    assert notice == "Saved junction relationships."
    assert saved.junctions[0].pathway_relationships[0].endpoint is PathwayEndpoint.END


def test_junction_rename_bridge_persists_name(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Translate a palette junction rename into one transactional metadata edit.
    """
    control = ControlStructure(
        UUID("37000000-0000-0000-0000-000000000011"),
        "Junction Gate",
        ControlKind.ROUTING_GATE,
        "junction-token",
    )
    junction = JunctionDefinition(
        UUID("38000000-0000-0000-0000-000000000011"),
        "Junction 01",
        control.control_id,
    )
    definition = replace(
        valid_harness,
        controls=(*valid_harness.controls, control),
        junctions=(junction,),
    )
    gateway = Mock(read_harness_definition=Mock(return_value=dumps(definition)))
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)

    notice = addin_module._apply_palette_edit(
        object(),
        "rename_junction",
        json.dumps(
            {
                "harnessId": str(definition.harness_id),
                "junctionId": str(junction.junction_id),
                "name": "Main Splice",
            }
        ),
    )

    saved = loads(gateway.replace_harness_definition.call_args.args[1])
    assert notice == "Saved name."
    assert saved.junctions[0] == replace(junction, name="Main Splice")


def test_junction_relationship_bridge_removes_one_endpoint(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Translate one palette row removal into the atomic application edit.
    """
    control = ControlStructure(
        UUID("37000000-0000-0000-0000-000000000001"),
        "Junction Gate",
        ControlKind.ROUTING_GATE,
        "junction-token",
    )
    relationship = JunctionPathwayRelationship(
        valid_harness.pathways[0].pathway_id,
        PathwayEndpoint.END,
    )
    junction = JunctionDefinition(
        UUID("38000000-0000-0000-0000-000000000001"),
        "Junction 01",
        control.control_id,
        (relationship,),
    )
    definition = replace(
        valid_harness,
        controls=(*valid_harness.controls, control),
        junctions=(junction,),
    )
    gateway = Mock(read_harness_definition=Mock(return_value=dumps(definition)))
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    request = {
        "harnessId": str(definition.harness_id),
        "junctionId": str(junction.junction_id),
        "pathwayId": str(relationship.pathway_id),
        "endpoint": relationship.endpoint.value,
    }

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_junction_relationship",
        json.dumps(request),
    )

    saved = loads(gateway.replace_harness_definition.call_args.args[1])
    assert notice == "Removed junction relationship."
    assert saved.junctions[0].pathway_relationships == ()


def test_solid_generation_fails_native_transaction_on_kernel_error(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Abort the native command if solid generation fails, preserving Undo/Redo semantics.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    monkeypatch.setitem(
        vars(addin_module), "_generate_solids", Mock(side_effect=RuntimeError("Wire 002 failed"))
    )
    monkeypatch.setattr(addin_module, "_log_to_fusion", Mock())
    args = SimpleNamespace(executeFailed=False)
    handler = addin_module._PaletteEditExecuteHandler(("generate_solids", "{}", document))
    handler.notify(args)
    assert args.executeFailed
    assert args.executeFailedMessage == "Wire 002 failed"
    assert not handler.clear_preview_after_destroy


def test_successful_solid_generation_clears_preview_after_command_destroy(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Remove transient graphics only after Fusion closes the successful transaction.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    generate = Mock(return_value=3)
    clear = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "_generate_solids", generate)
    monkeypatch.setattr(addin_module, "_clear_preview", clear)
    execute = addin_module._PaletteEditExecuteHandler(("generate_solids", "{}", document))
    destroyed = addin_module._PaletteEditDestroyedHandler(execute)
    args = SimpleNamespace(executeFailed=False)

    execute.notify(args)

    assert execute.clear_preview_after_destroy
    clear.assert_not_called()
    destroyed.notify(SimpleNamespace())
    clear.assert_called_once_with(application)


def test_clear_preview_deletes_graphics_outside_edit_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refresh Fusion after deleting transient graphics so they disappear immediately.
    """
    design = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    clear = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_clear_highlight", Mock())
    monkeypatch.setattr(addin_module, "clear_route_previews", clear)

    assert addin_module._clear_preview(application) == 1

    clear.assert_called_once_with(design)
    viewport.refresh.assert_called_once()


def test_clear_preview_palette_event_bypasses_model_edit_command(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Complete transient cleanup synchronously before returning to the palette.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    clear = Mock(return_value=2)
    open_edit = Mock()
    monkeypatch.setattr(addin_module, "_clear_preview", clear)
    monkeypatch.setattr(addin_module, "_open_palette_edit", open_edit)
    args = SimpleNamespace(action="clear_preview", data="{}", returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    clear.assert_called_once_with(application)
    open_edit.assert_not_called()
    assert json.loads(args.returnData) == {
        "ok": True,
        "notice": "Cleared 2 route-preview graphics groups.",
    }


def test_add_junction_palette_event_opens_native_selector(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the background-menu action through the dedicated Fusion command.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    opened = Mock()
    monkeypatch.setattr(addin_module, "_open_add_junction_command", opened)
    data = json.dumps({"harnessId": str(UUID(int=1))})
    args = SimpleNamespace(action="add_junction", data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    opened.assert_called_once_with(application, data)
    assert json.loads(args.returnData) == {"ok": True}


def test_add_junction_relationship_palette_event_opens_native_selector(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the popup action through the pathway-ending geometry command.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    opened = Mock()
    monkeypatch.setattr(
        addin_module,
        "_open_add_junction_relationship_command",
        opened,
    )
    data = json.dumps({"harnessId": str(UUID(int=1)), "junctionId": str(UUID(int=2))})
    args = SimpleNamespace(action="add_junction_relationship", data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    opened.assert_called_once_with(application, data)
    assert json.loads(args.returnData) == {"ok": True}


def test_palette_records_bounded_relationship_diagram_observation(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Retain only report-safe continuity metrics from the visual QA probe.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    args = SimpleNamespace(
        action="qa_diagram_observation",
        data=json.dumps(
            {
                "status": "passed",
                "connectorCount": 4,
                "maximumEndpointGap": 0.0,
                "obstructedTraceCount": 0,
                "portCount": 4,
                "invalidTraceGroupCount": 0,
                "contractVersion": "4",
                "layout": "endpoint-junction-forest",
            }
        ),
        returnData="",
    )

    addin_module._PaletteIncomingHandler().notify(args)

    assert addin_module._runtime.last_diagram_qa_observation == {
        "status": "passed",
        "connectorCount": 4,
        "maximumEndpointGap": 0.0,
        "obstructedTraceCount": 0,
        "portCount": 4,
        "invalidTraceGroupCount": 0,
        "contractVersion": "4",
        "layout": "endpoint-junction-forest",
    }
    assert json.loads(args.returnData) == {"ok": True}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("portCount", -1),
        ("invalidTraceGroupCount", True),
        ("contractVersion", "3"),
    ],
)
def test_palette_rejects_invalid_relationship_diagram_rendering_metrics(
    addin_module: _PaletteLifecycleModule,
    field: str,
    value: object,
) -> None:
    """
    Reject malformed adaptive-trace observations before retaining QA state.
    """
    application = SimpleNamespace(userInterface=None)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda candidate: candidate)
    payload = cast(
        dict[str, object],
        {
            "status": "passed",
            "connectorCount": 4,
            "maximumEndpointGap": 0.0,
            "obstructedTraceCount": 0,
            "portCount": 4,
            "invalidTraceGroupCount": 0,
            "contractVersion": "4",
            "layout": "endpoint-junction-forest",
        },
    )
    payload[field] = value
    args = SimpleNamespace(
        action="qa_diagram_observation",
        data=json.dumps(payload),
        returnData="",
    )
    addin_module._runtime.last_diagram_qa_observation = None

    addin_module._PaletteIncomingHandler().notify(args)

    assert addin_module._runtime.last_diagram_qa_observation is None
    assert json.loads(args.returnData)["ok"] is False
