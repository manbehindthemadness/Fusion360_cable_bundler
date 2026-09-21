"""Focused Fusion UI regressions for palette."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Mock,
    PathwayEndpoint,
    SimpleNamespace,
    _PaletteLifecycleModule,
    cast,
    json,
    pytest,
    sys,
)


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
        Mock(side_effect=ValueError("Gate 4 cannot fit 3 cables.")),
    )
    monkeypatch.setattr(addin_module, "_log_to_fusion", logged_messages.append)
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")
    addin_module._PaletteEditExecuteHandler(("preview_routes", "{}", document)).notify(args)
    assert args.executeFailed
    assert args.executeFailedMessage == "Gate 4 cannot fit 3 cables."
    assert len(logged_messages) == 1
    assert logged_messages[0].startswith("Harness command failed: Gate 4 cannot fit 3 cables.")
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
    Parse the unassigned-end identity and delegate the metadata deletion.
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


@pytest.mark.parametrize(
    ("action", "identity_key", "service_name", "notice"),
    [
        ("remove_end_guide", "memberId", "remove_end_guide", "Removed cable-end guide."),
        (
            "remove_end_control",
            "controlId",
            "remove_end_control",
            "Removed cable-end control.",
        ),
    ],
)
def test_palette_edit_removes_cable_end_routing_items_by_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    identity_key: str,
    service_name: str,
    notice: str,
) -> None:
    """
    Parse stable end and item identities before delegating routing-item removal.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    item_id = UUID(int=3)
    gateway = object()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, service_name, remove)

    result = addin_module._apply_palette_edit(
        object(),
        action,
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                identity_key: str(item_id),
            }
        ),
    )

    remove.assert_called_once_with(harness_id, connection_id, item_id, gateway)
    assert result == notice


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


def test_palette_edits_rename_and_remove_cable_end_attachment(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Delegate diagram connection lifecycle edits by their cable-end identity.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    gateway = object()
    rename = Mock()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "rename_cable_end_attachment", rename)
    monkeypatch.setattr(addin_module, "remove_cable_end_attachment", remove)

    rename_notice = addin_module._apply_palette_edit(
        object(),
        "rename_cable_end_attachment",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "name": "Bulkhead pin",
            }
        ),
    )
    remove_notice = addin_module._apply_palette_edit(
        object(),
        "remove_cable_end_attachment",
        json.dumps({"harnessId": str(harness_id), "connectionId": str(connection_id)}),
    )

    rename.assert_called_once_with(harness_id, connection_id, "Bulkhead pin", gateway)
    remove.assert_called_once_with(harness_id, connection_id, gateway)
    assert rename_notice == "Saved connection name."
    assert remove_notice == "Detached cable end."


def test_palette_edit_renames_cable_group_by_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the group identity and delegate its display-name edit.
    """
    harness_id = UUID(int=1)
    cable_group_id = UUID(int=2)
    gateway = object()
    rename = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "rename_cable_group", rename)

    notice = addin_module._apply_palette_edit(
        object(),
        "rename_cable_group",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "cableGroupId": str(cable_group_id),
                "name": "Engine loom",
            }
        ),
    )

    rename.assert_called_once_with(harness_id, cable_group_id, "Engine loom", gateway)
    assert notice == "Saved cable-group name."


def test_palette_edit_renames_harness_by_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the master-graphic harness name and delegate its metadata edit.
    """
    harness_id = UUID(int=1)
    gateway = object()
    rename = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "rename_harness", rename)

    notice = addin_module._apply_palette_edit(
        object(),
        "rename_harness",
        json.dumps({"harnessId": str(harness_id), "name": "Engine Harness"}),
    )

    rename.assert_called_once_with(harness_id, "Engine Harness", gateway)
    assert notice == "Saved name."


def test_palette_edit_switches_standalone_end_by_connection_identity(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the unassigned-end identity and delegate its boundary swap.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    gateway = object()
    switch = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "switch_standalone_end", switch)

    notice = addin_module._apply_palette_edit(
        object(),
        "switch_standalone_end",
        json.dumps({"harnessId": str(harness_id), "connectionId": str(connection_id)}),
    )

    switch.assert_called_once_with(harness_id, connection_id, gateway)
    assert notice == "Switched standalone end."


def test_palette_edit_saves_cable_editor_transaction(
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
    monkeypatch.setattr(addin_module, "save_cable_editor", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "save_cable_editor",
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
        PathwayEndpoint.START,
        right_pathway_id,
        PathwayEndpoint.END,
    )
    assert arguments[-1] is gateway
    assert notice == "Saved Route Editor changes."


def test_palette_edit_saves_connected_cable_properties_atomically(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse diameter and nullable construction-material overrides into one edit.
    """
    harness_id = UUID(int=1)
    cable_group_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_cable_group_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_cable_group_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "cableGroupId": str(cable_group_id),
                "diameterMm": 2.75,
                "insulationMaterial": "ETFE",
                "conductorMaterial": None,
                "manufacturer": "",
                "partNumber": "WB-42",
                "metadataOverrides": [{"key": "drawing-zone", "value": "B4"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        cable_group_id,
        2.75,
        "ETFE",
        None,
        "",
        "WB-42",
        (("drawing-zone", "B4"),),
        gateway,
    )
    assert notice == "Saved connected-cable properties."


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
                "metadata": [{"key": "project", "value": "Orion"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        "ETFE",
        "Tinned Copper",
        "Acme",
        "WB-42",
        (("project", "Orion"),),
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


def test_palette_edit_saves_pathway_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse pathway key/value rows independently of routing controls.
    """
    harness_id = UUID(int=1)
    pathway_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_pathway_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_pathway_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "pathwayId": str(pathway_id),
                "metadata": [{"key": "zone", "value": "forward"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        pathway_id,
        (("zone", "forward"),),
        gateway,
    )
    assert notice == "Saved pathway properties."


def test_palette_edit_saves_pathway_end_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the selected boundary and its key/value rows without changing routing.
    """
    harness_id = UUID(int=1)
    pathway_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_pathway_end_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_pathway_end_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "pathwayId": str(pathway_id),
                "endpoint": "end",
                "metadata": [{"key": "station", "value": "right"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        pathway_id,
        PathwayEndpoint.END,
        (("station", "right"),),
        gateway,
    )
    assert notice == "Saved pathway-end properties."


@pytest.mark.parametrize(
    ("action", "identity_key", "service_name", "notice"),
    (
        (
            "set_junction_properties",
            "junctionId",
            "set_junction_properties",
            "Saved junction properties.",
        ),
        (
            "set_cable_end_properties",
            "connectionId",
            "set_cable_end_properties",
            "Saved cable-end properties.",
        ),
    ),
)
def test_palette_edit_saves_identity_owned_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    identity_key: str,
    service_name: str,
    notice: str,
) -> None:
    """
    Parse junction and cable-end metadata through their dedicated edit services.
    """
    harness_id = UUID(int=1)
    identity = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, service_name, save)

    result = addin_module._apply_palette_edit(
        object(),
        action,
        json.dumps(
            {
                "harnessId": str(harness_id),
                identity_key: str(identity),
                "metadata": [{"key": "location", "value": "P2"}],
            }
        ),
    )

    save.assert_called_once_with(harness_id, identity, (("location", "P2"),), gateway)
    assert result == notice


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
    applied = Mock(return_value="Renamed cable.")
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


# noinspection DuplicatedCode
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


# noinspection DuplicatedCode
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
