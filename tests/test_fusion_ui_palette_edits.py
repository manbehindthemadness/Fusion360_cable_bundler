"""
Focused Fusion UI regressions for palette.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Mock,
    ModuleType,
    PathwayEndpoint,
    SimpleNamespace,
    _PaletteLifecycleModule,
    importlib,
    json,
    pytest,
    sys,
)


def _mock_palette_service(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
) -> tuple[object, Mock]:
    """
    Install one named palette service with a shared synthetic gateway.
    """
    gateway = object()
    service = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    topology_services = {
        "disconnect_cable_end_main",
        "disconnect_cable_end_shielding",
        "remove_end_guide",
        "remove_end_control",
    }
    target = _topology_edits_module() if service_name in topology_services else addin_module
    monkeypatch.setattr(target, service_name, service)
    return gateway, service


def _topology_edits_module() -> ModuleType:
    """
    Return the module that owns palette topology service calls.
    """
    return importlib.import_module("cable_bundler.fusion.ui.topology_edits")


def _mock_topology_service(
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
    service: Mock,
) -> None:
    """
    Replace one topology service at its owning module boundary.
    """
    monkeypatch.setattr(_topology_edits_module(), service_name, service)


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
    _mock_topology_service(monkeypatch, "remove_standalone_end", remove)

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_standalone_end",
        json.dumps({"harnessId": str(harness_id), "connectionId": str(connection_id)}),
    )

    remove.assert_called_once_with(harness_id, connection_id, gateway)
    assert notice == "Deleted standalone end."


def test_palette_edit_adds_unattached_cable_end_connection(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Persist the connection node before the native target picker is opened.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    gateway = object()
    add = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    _mock_topology_service(monkeypatch, "add_cable_end_connection", add)

    notice = addin_module._apply_palette_edit(
        object(),
        "add_cable_end_connection",
        json.dumps({"harnessId": str(harness_id), "connectionId": str(connection_id)}),
    )

    add.assert_called_once_with(harness_id, connection_id, gateway, parent_attachment_id=None)
    assert notice == "Added cable-end connection."


def test_palette_edit_adds_child_connection_to_selected_parent(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Pass the selected connection identity through the palette edit boundary.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    parent_attachment_id = UUID(int=3)
    gateway = object()
    add = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    _mock_topology_service(monkeypatch, "add_cable_end_connection", add)

    addin_module._apply_palette_edit(
        object(),
        "add_cable_end_connection",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "parentAttachmentId": str(parent_attachment_id),
            }
        ),
    )

    add.assert_called_once_with(
        harness_id,
        connection_id,
        gateway,
        parent_attachment_id=parent_attachment_id,
    )


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
    gateway, remove = _mock_palette_service(addin_module, monkeypatch, service_name)

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
    attachment_id = UUID(int=3)
    gateway = object()
    rename = Mock()
    remove = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "rename_cable_end_attachment", rename)
    _mock_topology_service(monkeypatch, "remove_cable_end_attachment", remove)

    rename_notice = addin_module._apply_palette_edit(
        object(),
        "rename_cable_end_attachment",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "attachmentId": str(attachment_id),
                "name": "Bulkhead pin",
            }
        ),
    )
    remove_notice = addin_module._apply_palette_edit(
        object(),
        "remove_cable_end_attachment",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "attachmentId": str(attachment_id),
            }
        ),
    )

    rename.assert_called_once_with(
        harness_id, connection_id, attachment_id, "Bulkhead pin", gateway
    )
    remove.assert_called_once_with(harness_id, connection_id, attachment_id, gateway)
    assert rename_notice == "Saved connection name."
    assert remove_notice == "Detached cable end."


@pytest.mark.parametrize(
    ("relationship", "service_name"),
    (("main", "disconnect_cable_end_main"), ("shielding", "disconnect_cable_end_shielding")),
)
def test_palette_edit_disconnects_one_cable_end_relationship(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    relationship: str,
    service_name: str,
) -> None:
    """
    Route each submenu choice to the matching relationship-specific edit service.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    gateway, disconnect = _mock_palette_service(addin_module, monkeypatch, service_name)

    notice = addin_module._apply_palette_edit(
        object(),
        "disconnect_cable_end_relationship",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "attachmentId": str(attachment_id),
                "relationship": relationship,
            }
        ),
    )

    disconnect.assert_called_once_with(harness_id, connection_id, attachment_id, gateway)
    assert notice == f"Disconnected cable-end {relationship} relationship."


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


def test_palette_edit_saves_multirow_attachment_association(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve one association identity and ordered members in the palette payload.
    """
    harness_id = UUID(int=801)
    left_connection_id = UUID(int=802)
    right_connection_id = UUID(int=803)
    association_id = UUID(int=804)
    members = [UUID(int=810 + index) for index in range(3)]
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "save_attachment_associations", save)

    addin_module._apply_palette_edit(
        object(),
        "save_attachment_associations",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "leftAnchor": {"connectionId": str(left_connection_id)},
                "rightAnchor": {"connectionId": str(right_connection_id)},
                "associations": [
                    {
                        "associationId": str(association_id),
                        "attachmentIds": [str(member) for member in members],
                    }
                ],
            }
        ),
    )

    saved_group = save.call_args.args[3][0]
    assert saved_group.association_id == association_id
    assert saved_group.attachment_ids == tuple(members)
    assert save.call_args.args[-1] is gateway


def test_palette_edit_parses_cable_group_remainder_anchor(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve the group and excluded owner in a partitioned association save.
    """
    harness_id, owner_id, group_id, leaf_id = (UUID(int=950 + index) for index in range(4))
    gateway, save = _mock_palette_service(addin_module, monkeypatch, "save_attachment_associations")
    addin_module._apply_palette_edit(
        object(),
        "save_attachment_associations",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "leftAnchor": {"connectionId": str(owner_id)},
                "rightAnchor": {
                    "nodeKind": "cableGroupRemainder",
                    "nodeId": str(group_id),
                    "connectionId": str(owner_id),
                    "candidateAttachmentIds": [str(leaf_id)],
                },
                "associations": [],
            }
        ),
    )
    right_anchor = save.call_args.args[2]
    assert right_anchor.node_kind == "cableGroupRemainder"
    assert right_anchor.node_id == group_id
    assert right_anchor.connection_id == owner_id
    assert right_anchor.candidate_attachment_ids == (leaf_id,)
    assert save.call_args.args[-1] is gateway


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
                "conductorDiameterMm": 2.0,
                "insulationMaterial": "ETFE",
                "conductorMaterial": None,
                "shielding": "Braided copper",
                "dielectricMaterial": "FEP",
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
        "Braided copper",
        "FEP",
        "",
        "WB-42",
        (("drawing-zone", "B4"),),
        gateway,
        conductor_diameter_mm=2.0,
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
                "shielding": "Foil",
                "dielectricMaterial": "PE",
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
        "Foil",
        "PE",
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
    _mock_topology_service(monkeypatch, "remove_pathway", remove)

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
    _mock_topology_service(monkeypatch, "remove_junction", remove)

    notice = addin_module._apply_palette_edit(
        object(),
        "remove_junction",
        json.dumps({"harnessId": str(harness_id), "junctionId": str(junction_id)}),
    )

    remove.assert_called_once_with(harness_id, junction_id, gateway)
    assert notice == "Deleted junction."


def test_palette_edit_clears_selected_contact_pins(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route one selected set to the bulk pin edit.
    """
    harness_id = UUID(int=1)
    interface_id = UUID(int=2)
    contact_ids = (UUID(int=3), UUID(int=4))
    gateway, clear_pins = _mock_palette_service(
        addin_module, monkeypatch, "clear_interface_contact_pins"
    )

    notice = addin_module._apply_palette_edit(
        object(),
        "clear_interface_contact_pins",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "interfaceId": str(interface_id),
                "contactIds": [str(contact_id) for contact_id in contact_ids],
            }
        ),
    )

    clear_pins.assert_called_once_with(harness_id, interface_id, contact_ids, gateway)
    assert notice == "Selected Interface contact pins cleared."
