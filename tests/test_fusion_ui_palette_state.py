"""Focused Fusion UI regressions for palette state."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    HarnessDefinition,
    HarnessLoadResult,
    PathwayEndpoint,
    SimpleNamespace,
    StandaloneEndDefinition,
    WireGroupDefinition,
    _PaletteLifecycleModule,
    json,
    pytest,
    replace,
)


def test_all_palette_resources_are_packaged(addin_module: _PaletteLifecycleModule) -> None:
    """
    Keep every stylesheet and ordered script beside the palette entry point.
    """
    assert all(path.is_file() for path in addin_module.PALETTE_RESOURCE_FILES)


def test_palette_state_contains_complete_editor_definition(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Include stable identities and ordered relationships needed by the editor.
    """
    gateway = SimpleNamespace(
        is_entity_token_resolvable=lambda entity_token: entity_token == "fusion-gate-token"
    )
    valid_harness = replace(
        valid_harness,
        pathways=(replace(valid_harness.pathways[0], start_name="Sensor", end_name="Controller"),),
        wires=(replace(valid_harness.wires[0], display_name="Signal", start_end_name="O2"),),
        standalone_ends=(
            StandaloneEndDefinition(
                valid_harness.connections[0].connection_id,
                valid_harness.pathways[0].pathway_id,
                PathwayEndpoint.START,
            ),
        ),
        wire_groups=(
            WireGroupDefinition(
                UUID("60000000-0000-0000-0000-000000000001"),
                tuple(connection.connection_id for connection in valid_harness.connections),
            ),
        ),
    )
    result = HarnessLoadResult(
        component_name="Harness_001",
        definition=valid_harness,
        error=None,
        validation_messages=(),
    )
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))

    payload = json.loads(addin_module.serialize_palette_state(object(), "Ready"))

    harness = payload["harnesses"][0]
    assert payload["notice"] == "Ready"
    assert "ETFE" in payload["catalog"]["insulationMaterials"]
    assert harness["materialDefaults"]["mainColor"]["hex"] == "#202020"
    assert harness["wires"][0]["materials"] == harness["materialDefaults"]
    assert harness["wires"][0]["materialOverrides"]["mainColor"] is None
    assert harness["gateDefaults"] == {"approach_mm": None, "departure_mm": None}
    assert harness["connections"][0]["interpolation"] == harness["endDefaults"]
    assert harness["controls"][0]["interpolation"] == harness["gateDefaults"]
    addin_module._runtime.last_command_error = "Wire 001: create cross-section plane failed"
    refreshed = json.loads(addin_module.serialize_palette_state(object(), ""))
    assert refreshed["notice"] == "Wire 001: create cross-section plane failed"
    assert harness["schemaVersion"] == valid_harness.schema_version
    assert harness["profiles"][0]["name"] == "Primary wire"
    assert harness["connections"][0]["name"] == "J1 / Pin 1"
    assert harness["controls"][0]["kind"] == "routing_gate"
    assert harness["controls"][0]["hasLinkedGeometry"]
    assert not harness["connections"][0]["hasLinkedGeometry"]
    assert harness["pathways"][0]["name"] == "Main Pathway"
    assert harness["pathways"][0]["startName"] == "Sensor"
    assert harness["pathways"][0]["endName"] == "Controller"
    assert harness["wires"][0]["displayName"] == "Signal"
    assert harness["wires"][0]["startEndName"] == "O2"
    assert harness["pathways"][0]["orderedControlIds"] == [
        str(valid_harness.controls[0].control_id)
    ]
    assert harness["wires"][0]["wireNumber"] == "001"
    assert harness["wires"][0]["orderedPathwayIds"] == [str(valid_harness.pathways[0].pathway_id)]
    assert harness["wires"][0]["orderedControlIds"] == [str(valid_harness.controls[0].control_id)]
    assert harness["standaloneEnds"] == [
        {
            "connectionId": str(valid_harness.connections[0].connection_id),
            "pathwayId": str(valid_harness.pathways[0].pathway_id),
            "endpoint": "start",
        }
    ]
    wire_group = harness["wireGroups"][0]
    assert wire_group["wireGroupId"] == "60000000-0000-0000-0000-000000000001"
    assert wire_group["connectionIds"] == [
        str(connection.connection_id) for connection in valid_harness.connections
    ]
    assert wire_group["diameterMm"] == valid_harness.wire_groups[0].diameter_mm
    assert wire_group["materials"] == harness["materialDefaults"]
    assert wire_group["materialOverrides"]["mainColor"] is None
    assert len(wire_group["routeLegs"]) == 1
    route_leg = wire_group["routeLegs"][0]
    assert route_leg["routeId"]
    assert route_leg["label"] == "Group 1 Leg 1"
    assert {route_leg["startConnectionId"], route_leg["endConnectionId"]} == {
        str(connection.connection_id) for connection in valid_harness.connections
    }
    assert route_leg["controlSteps"] == [
        {
            "controlId": str(valid_harness.controls[0].control_id),
            "reversed": True,
        }
    ]
    assert route_leg["pathwayIds"] == [str(valid_harness.pathways[0].pathway_id)]
    assert harness["wireGroupRouteError"] is None
    relationship_map = harness["relationshipMap"]
    assert relationship_map["routes"][0]["nodeIds"] == [
        f"connection:{valid_harness.connections[0].connection_id}",
        f"pathway:{valid_harness.pathways[0].pathway_id}",
        f"connection:{valid_harness.connections[1].connection_id}",
    ]
    assert relationship_map["pathwayOccupancy"][0]["wireIds"] == [
        str(valid_harness.wires[0].wire_id)
    ]
    assert relationship_map["auditIssues"] == []


def test_damaged_palette_entry_can_delete_its_exact_component(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Give an unreadable entry a short-lived token that resolves to its component.
    """
    component = object()
    result = HarnessLoadResult(
        component_name="Broken Harness",
        definition=None,
        error="Stored definition is malformed.",
        validation_messages=(),
        component_handle=component,
    )
    deleted_components: list[object] = []
    gateway = SimpleNamespace(
        delete_stored_harness_component=deleted_components.append,
    )
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))

    state = json.loads(addin_module.serialize_palette_state(object(), ""))
    deletion_token = state["harnesses"][0]["deletionToken"]
    refreshed = json.loads(addin_module.serialize_palette_state(object(), ""))
    notice = addin_module._delete_damaged_harness(
        object(),
        json.dumps({"deletionToken": deletion_token}),
    )

    assert isinstance(deletion_token, str)
    assert refreshed["harnesses"][0]["deletionToken"] == deletion_token
    assert deleted_components == [component]
    assert notice == "Deleted damaged harness Broken Harness."
    assert deletion_token not in addin_module._runtime.damaged_harness_results


def test_lists_installed_fusion_appearance_libraries_and_contents(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Load appearance names only for the library selected in the palette.
    """
    appearances = SimpleNamespace(
        count=2,
        item=lambda index: (
            SimpleNamespace(id="blue-id", name="Rubber - Blue"),
            SimpleNamespace(id="black-id", name="Rubber - Black"),
        )[index],
    )
    library = SimpleNamespace(id="custom-id", name="My Library", appearances=appearances)
    libraries = SimpleNamespace(
        count=1,
        item=lambda _index: library,
        itemById=lambda identity: library if identity == "custom-id" else None,
    )
    application = SimpleNamespace(materialLibraries=libraries)

    assert addin_module._appearance_libraries_payload(application) == [
        {"id": "custom-id", "name": "My Library"}
    ]
    assert addin_module._library_appearances_payload(application, "custom-id") == [
        {"id": "black-id", "name": "Rubber - Black"},
        {"id": "blue-id", "name": "Rubber - Blue"},
    ]
