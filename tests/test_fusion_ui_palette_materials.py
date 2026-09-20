"""Focused Fusion UI regressions for palette."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    CableColor,
    CableGroupDefinition,
    CableStripe,
    ControlKind,
    ControlStructure,
    HarnessDefinition,
    JunctionDefinition,
    JunctionPathwayRelationship,
    Mock,
    PathwayEndpoint,
    SimpleNamespace,
    _PaletteLifecycleModule,
    dumps,
    json,
    loads,
    pytest,
    replace,
    sys,
)


@pytest.mark.parametrize(
    ("action", "payload_values", "edit_notice", "geometry_notice"),
    (
        (
            "set_harness_material_defaults",
            {},
            "Saved harness cable-material defaults.",
            "Applied materials to 2 generated cable groups.",
        ),
        (
            "set_cable_group_material_overrides",
            {"cableGroupId": str(UUID(int=2)), "overrides": {}},
            "Saved connected-cable material overrides.",
            "Applied materials to 1 generated cable group.",
        ),
        (
            "set_harness_material_defaults",
            {},
            "Saved harness cable-material defaults.",
            "Applied materials to 0 generated cable groups.",
        ),
    ),
)
def test_material_save_applies_existing_bodies_and_preview(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    payload_values: dict[str, object],
    edit_notice: str,
    geometry_notice: str,
) -> None:
    """
    Apply material settings to persistent solids and graphics, if geometry exists.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    harness_id = UUID(int=1)
    applied = Mock(return_value=edit_notice)
    applied_bodies = Mock(return_value=geometry_notice)
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_apply_generated_materials", applied_bodies)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id), **payload_values})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler((action, payload, document)).notify(args)

    applied_bodies.assert_called_once_with(application, harness_id)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=True)
    sent.assert_called_once_with(
        application,
        f"{edit_notice} {geometry_notice}",
    )
    assert not args.executeFailed


def test_connected_cable_property_save_refreshes_only_group_preview(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refresh transient group graphics without applying legacy generated-cable materials.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    harness_id = UUID(int=1)
    applied = Mock(return_value="Saved connected-cable properties.")
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
            "cableGroupId": str(UUID(int=2)),
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
        ("set_cable_group_properties", payload, document)
    ).notify(args)

    applied_bodies.assert_not_called()
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=True)
    sent.assert_called_once_with(application, "Saved connected-cable properties.")
    assert not args.executeFailed


def test_material_refresh_shows_striped_preview_when_none_is_active(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Create visible stripe graphics as direct feedback for Apply and Save.
    """
    stripe = CableStripe(CableColor("White", 245, 245, 245), 0.2)
    definition = replace(
        valid_harness,
        material_defaults=replace(valid_harness.material_defaults, stripes=(stripe,)),
        cable_groups=(
            CableGroupDefinition(
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
    assert saved.cable_groups == valid_harness.cable_groups
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
