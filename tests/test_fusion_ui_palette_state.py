"""Focused Fusion UI regressions for palette state."""

from __future__ import annotations

import re

from tests.fusion_ui_support import (
    HarnessDefinition,
    HarnessLoadResult,
    SimpleNamespace,
    _PaletteLifecycleModule,
    json,
    pytest,
)


def test_all_palette_resources_are_packaged(addin_module: _PaletteLifecycleModule) -> None:
    """
    Keep every stylesheet and ordered script beside the palette entry point.
    """
    assert all(path.is_file() for path in addin_module.PALETTE_RESOURCE_FILES)
    palette_file = addin_module.PALETTE_RESOURCE_FILES[0]
    html = palette_file.read_text(encoding="utf-8")
    relative_resources = {
        path.relative_to(palette_file.parent).as_posix()
        for path in addin_module.PALETTE_RESOURCE_FILES
        if path != palette_file
    }
    referenced_resources = set(re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', html))
    assert relative_resources == referenced_resources


def test_palette_state_contains_complete_group_definition(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Include group identities and planned route legs without legacy wire payloads.
    """
    gateway = SimpleNamespace(
        is_entity_token_resolvable=lambda entity_token: entity_token == "fusion-gate-token"
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
    assert "wires" not in harness
    assert "profiles" not in harness
    assert "relationshipMap" not in harness
    assert harness["schemaVersion"] == valid_harness.schema_version
    assert harness["minimumClearanceMm"] == valid_harness.minimum_clearance_mm
    assert harness["autoTransitionPreset"] == valid_harness.auto_transition_preset.value
    assert harness["standaloneEnds"] == [
        {
            "connectionId": str(end.connection_id),
            "pathwayId": str(end.pathway_id),
            "endpoint": end.endpoint.value,
            "orderedControlIds": [str(control_id) for control_id in end.ordered_control_ids],
        }
        for end in valid_harness.standalone_ends
    ]
    wire_group = harness["wireGroups"][0]
    assert wire_group["wireGroupId"] == str(valid_harness.wire_groups[0].wire_group_id)
    assert wire_group["connectionIds"] == [
        str(connection_id) for connection_id in valid_harness.wire_groups[0].connection_ids
    ]
    assert wire_group["diameterMm"] == valid_harness.wire_groups[0].diameter_mm
    assert len(wire_group["routeLegs"]) == 1
    assert wire_group["routeLegs"][0]["pathwayIds"] == [str(valid_harness.pathways[0].pathway_id)]


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
