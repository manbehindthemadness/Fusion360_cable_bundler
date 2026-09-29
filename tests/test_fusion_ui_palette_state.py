"""
Focused Fusion UI regressions for palette state.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from uuid import UUID

from cable_bundler.domain import (
    AttachmentTargetKind,
    CableEndAttachment,
    CableEndTarget,
    InterfaceContact,
    InterfaceDefinition,
    InterfaceTarget,
    InterfaceTargetKind,
    JunctionDefinition,
)
from tests.fusion_ui_support import (
    HarnessDefinition,
    HarnessLoadResult,
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    json,
    pytest,
    sys,
)


def _serialize_definition(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    definition: HarnessDefinition,
    serialize_palette_state: Callable[[object, str], str],
) -> dict[str, Any]:
    """
    Project one deterministic definition through the mocked palette boundary.
    """
    gateway = SimpleNamespace(is_entity_token_resolvable=lambda _entity_token: True)
    result = HarnessLoadResult("Harness_001", definition, None, ())
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))
    return json.loads(serialize_palette_state(object(), ""))


def test_palette_state_includes_saved_interface_contacts_without_live_design(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep disconnected contact identities visible until Fusion can resolve geometry.
    """
    contact = InterfaceContact(
        UUID(int=900),
        AttachmentTargetKind.FACE,
        "face",
        pin="P7",
        orientation_name="Power side",
    )
    interface = InterfaceDefinition(
        UUID(int=901),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (contact,),
    )
    definition = replace(valid_harness, interfaces=(interface,))
    payload = _serialize_definition(
        addin_module,
        monkeypatch,
        definition,
        addin_module.serialize_palette_state,
    )
    projected = payload["harnesses"][0]["interfaces"][0]["contacts"]
    assert projected == [
        {
            "contactId": str(contact.contact_id),
            "kind": "face",
            "name": "face",
            "assignedName": "",
            "pin": "P7",
            "orientationName": "Power side",
            "geometryRevision": addin_module._runtime.contact_geometry_revision,
        }
    ]
    assert payload["harnesses"][0]["interfaces"][0]["connectedConnectionIds"] == []


def test_palette_state_reads_contact_revision_once_for_all_contacts(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Avoid repeated Fusion document lookups while projecting contact metadata.
    """
    interfaces = tuple(
        InterfaceDefinition(
            UUID(int=920 + interface_index),
            f"Socket {interface_index}",
            (InterfaceTarget(InterfaceTargetKind.BODY, f"body-{interface_index}"),),
            tuple(
                InterfaceContact(
                    UUID(int=930 + interface_index * 3 + contact_index),
                    AttachmentTargetKind.FACE,
                    f"face-{interface_index}-{contact_index}",
                )
                for contact_index in range(3)
            ),
        )
        for interface_index in range(2)
    )
    revision = Mock(return_value=17)
    runtime = importlib.import_module("cable_bundler.fusion.ui.runtime").runtime
    monkeypatch.setitem(vars(runtime), "contact_cache_revision", revision)
    payload = _serialize_definition(
        addin_module,
        monkeypatch,
        replace(valid_harness, interfaces=interfaces),
        addin_module.serialize_palette_state,
    )

    revision.assert_called_once()
    assert [
        contact["geometryRevision"]
        for interface in payload["harnesses"][0]["interfaces"]
        for contact in interface["contacts"]
    ] == [17] * 6


def test_palette_state_skips_contact_revision_without_contacts(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Leave contact document lookups out of harnesses without contacts.
    """
    revision = Mock()
    runtime = importlib.import_module("cable_bundler.fusion.ui.runtime").runtime
    monkeypatch.setitem(vars(runtime), "contact_cache_revision", revision)

    _serialize_definition(
        addin_module,
        monkeypatch,
        replace(valid_harness, interfaces=()),
        addin_module.serialize_palette_state,
    )

    revision.assert_not_called()


def test_palette_state_links_interfaces_by_resolved_contact_targets(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Expose saved target matches to the diagram without equating matching pins.
    """
    interface = InterfaceDefinition(
        UUID(int=910),
        "Connector",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body"),),
        (
            InterfaceContact(
                UUID(int=911), AttachmentTargetKind.CONSTRUCTION_POINT, "contact-a", pin="7"
            ),
            InterfaceContact(
                UUID(int=912), AttachmentTargetKind.CONSTRUCTION_POINT, "contact-b", pin="8"
            ),
        ),
    )
    connected = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "contact-a",
        "Connector point",
        attachment_id=UUID(int=913),
        pin_number="different pin",
    )
    unavailable = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "contact-b",
        "Missing point",
        attachment_id=UUID(int=914),
    )
    definition = replace(
        valid_harness,
        interfaces=(interface,),
        connections=(
            replace(valid_harness.connections[0], attachment=connected),
            replace(valid_harness.connections[1], attachment=unavailable),
        ),
    )
    gateway = SimpleNamespace(is_entity_token_resolvable=lambda token: token != "contact-b")
    result = HarnessLoadResult("Harness_001", definition, None, ())
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))

    payload = json.loads(addin_module.serialize_palette_state(object(), ""))

    assert payload["harnesses"][0]["interfaces"][0]["connectedConnectionIds"] == [
        str(valid_harness.connections[0].connection_id)
    ]


def test_palette_state_resolves_shared_tokens_once_per_snapshot(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reuse Fusion lookups across contact matches, attachments, and member status.
    """
    token = valid_harness.connections[0].member_tokens[0]
    attachment = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        token,
        "Connection point",
        attachment_id=UUID(int=915),
    )
    interface = InterfaceDefinition(
        UUID(int=916),
        "Connector",
        (InterfaceTarget(InterfaceTargetKind.BODY, token),),
        (InterfaceContact(UUID(int=917), AttachmentTargetKind.CONSTRUCTION_POINT, token),),
    )
    definition = replace(
        valid_harness,
        interfaces=(interface,),
        connections=(
            replace(valid_harness.connections[0], attachment=attachment),
            valid_harness.connections[1],
        ),
    )
    find_entities = Mock(return_value=())
    design = SimpleNamespace(findEntityByToken=find_entities)
    fusion_module = sys.modules["adsk.fusion"]
    monkeypatch.setitem(
        vars(fusion_module), "Design", SimpleNamespace(cast=lambda _product: design)
    )
    interface_fusion = importlib.import_module("cable_bundler.fusion.interface_targets").adsk.fusion
    for type_name in ("BRepBody", "Sketch", "Occurrence"):
        monkeypatch.setattr(
            interface_fusion, type_name, SimpleNamespace(cast=lambda _entity: None), raising=False
        )
    gateway = SimpleNamespace(is_entity_token_resolvable=Mock())
    result = HarnessLoadResult("Harness_001", definition, None, ())
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))
    application = SimpleNamespace(activeProduct=design)

    first = json.loads(addin_module.serialize_palette_state(application, ""))
    assert first["harnesses"][0]["connections"][0]["hasLinkedGeometry"] is False
    assert [args.args[0] for args in find_entities.call_args_list].count(token) == 1
    gateway.is_entity_token_resolvable.assert_not_called()

    addin_module.serialize_palette_state(application, "")
    assert [args.args[0] for args in find_entities.call_args_list].count(token) == 2


def test_contact_palette_document_scope_survives_save_while_cache_scope_changes(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep saved reads in one document while isolating each version's rendered image.
    """
    module = importlib.import_module("cable_bundler.fusion.ui.palette_state")

    def application(identity: str, version: int) -> SimpleNamespace:
        """
        Represent a saved Fusion document without exposing its file ID to the palette.
        """
        return SimpleNamespace(
            activeDocument=SimpleNamespace(
                dataFile=SimpleNamespace(id=identity, versionNumber=version)
            )
        )

    first = module._contact_palette_document_scope(application("first", 1), None)
    assert len(first) == 64
    assert first == module._contact_palette_document_scope(application("first", 1), None)
    assert first != module._contact_palette_document_scope(application("second", 1), None)
    assert first == module._contact_palette_document_scope(application("first", 2), None)
    assert first == module._contact_palette_document_scope(application("first", 0), None)
    assert module._contact_palette_cache_scope(
        application("first", 1), None
    ) != module._contact_palette_cache_scope(application("first", 2), None)


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


def test_length_units_payload_uses_the_active_design_conversion(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Send the design's preferred unit label and its exact millimeter scale.
    """
    design = SimpleNamespace(
        unitsManager=SimpleNamespace(
            defaultLengthUnits="in",
            convert=lambda value, input_units, output_units: (
                25.4 if value == 1.0 and input_units == "in" and output_units == "mm" else -1.0
            ),
        )
    )

    assert addin_module._length_units_payload(design) == {
        "symbol": "in",
        "millimetersPerUnit": 25.4,
    }
    assert addin_module._length_units_payload(None) == {
        "symbol": "mm",
        "millimetersPerUnit": 1.0,
    }


def test_palette_state_resolves_each_connection_member_once(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Derive connection and member link status from one Fusion token lookup per member.
    """
    resolve = Mock(return_value=True)
    gateway = SimpleNamespace(is_entity_token_resolvable=resolve)
    result = HarnessLoadResult("Harness_001", valid_harness, None, ())
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))

    payload = json.loads(addin_module.serialize_palette_state(object(), ""))

    for connection in payload["harnesses"][0]["connections"]:
        assert connection["hasLinkedGeometry"] is True
        assert connection["members"][0]["hasLinkedGeometry"] is True
    resolved_tokens = [call.args[0] for call in resolve.call_args_list]
    assert resolved_tokens.count("fusion-start-token") == 1
    assert resolved_tokens.count("fusion-end-token") == 1


def test_palette_state_contains_complete_group_definition(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Include group identities and planned route legs without legacy cable payloads.
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
    assert payload["theme"] == {"active": "light", "mode": "fixed"}
    assert "cables" not in harness
    assert "profiles" not in harness
    assert "relationshipMap" not in harness
    assert harness["schemaVersion"] == valid_harness.schema_version
    assert harness["lengthUnits"] == {"symbol": "mm", "millimetersPerUnit": 1.0}
    assert harness["hasRoutePreview"] is False
    assert harness["hasGeneratedSolids"] is False
    assert harness["hasFinalizedGeometry"] is False
    assert harness["minimumClearanceMm"] == valid_harness.minimum_clearance_mm
    assert harness["autoTransitionPreset"] == valid_harness.auto_transition_preset.value
    assert harness["standaloneEnds"] == [
        {
            "connectionId": str(end.connection_id),
            "pathwayId": str(end.pathway_id),
            "endpoint": end.endpoint.value,
            "shape": end.shape.value,
            "orderedControlIds": [str(control_id) for control_id in end.ordered_control_ids],
        }
        for end in valid_harness.standalone_ends
    ]
    assert harness["pathways"][0]["metadata"] == []
    assert harness["pathways"][0]["startMetadata"] == []
    assert harness["pathways"][0]["endMetadata"] == []
    assert harness["connections"][0]["metadata"] == []
    assert harness["materialDefaults"]["pullback"] == {
        "mode": "percent",
        "value": 200.0,
        "color": {
            "name": "Copper",
            "red": 184,
            "green": 115,
            "blue": 51,
            "hex": "#B87333",
        },
        "appearance": None,
    }
    assert harness["materialDefaults"]["weld"] == {
        "value": 150.0,
        "color": {
            "name": "Silver",
            "red": 192,
            "green": 192,
            "blue": 192,
            "hex": "#C0C0C0",
        },
        "appearance": None,
    }
    cable_group = harness["cableGroups"][0]
    assert cable_group["cableGroupId"] == str(valid_harness.cable_groups[0].cable_group_id)
    assert cable_group["name"] == ""
    assert cable_group["groupType"] == "loose"
    assert cable_group["connectionIds"] == [
        str(connection_id) for connection_id in valid_harness.cable_groups[0].connection_ids
    ]
    assert cable_group["diameterMm"] == valid_harness.cable_groups[0].diameter_mm
    assert cable_group["conductorDiameterMm"] is None
    assert cable_group["resolvedConductorDiameterMm"] == (
        valid_harness.cable_groups[0].diameter_mm * 0.75
    )
    assert cable_group["materialOverrides"]["pullback"] is None
    assert cable_group["materialOverrides"]["weld"] is None
    assert harness["metadata"] == []
    assert cable_group["metadata"] == []
    assert cable_group["metadataOverrides"] == []
    assert len(cable_group["routeLegs"]) == 1
    assert cable_group["routeLegs"][0]["pathwayIds"] == [str(valid_harness.pathways[0].pathway_id)]


def test_palette_state_reports_attachment_and_connection_status(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep attached/detached separate from live connected/disconnected resolution.
    """
    attachment = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "attachment-token",
        "Connector datum",
        metadata=(("connector", "J1"),),
        attachment_id=UUID(int=901),
        pin_number="A2",
        shielding_target=CableEndTarget(
            AttachmentTargetKind.CONSTRUCTION_POINT,
            "shield-token",
            "Shield stud",
        ),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], attachment=attachment),
            replace(
                valid_harness.connections[1],
                attachment=CableEndAttachment(None, attachment_id=UUID(int=902)),
            ),
        ),
    )
    gateway = SimpleNamespace(
        is_entity_token_resolvable=lambda token: token in {"attachment-token", "shield-token"}
    )
    result = HarnessLoadResult("Harness_001", definition, None, ())
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: (result,))

    payload = json.loads(addin_module.serialize_palette_state(object(), ""))

    connection = payload["harnesses"][0]["connections"][0]
    assert connection["attachment"] == {
        "attachmentId": str(UUID(int=901)),
        "parentAttachmentId": None,
        "connected": True,
        "shieldingTarget": {
            "targetKind": "construction_point",
            "name": "Shield stud",
            "connected": True,
        },
        "name": "Connector datum",
        "nameOverride": "",
        "pinNumber": "A2",
        "targetKind": "construction_point",
        "metadata": [{"key": "connector", "value": "J1"}],
        "orderedControlIds": [],
        "resolvedDiameterMm": 1.2,
        "visualOverrides": {
            "diameterMm": None,
            "conductorDiameterMm": None,
            "insulationMaterial": None,
            "conductorMaterial": None,
            "shielding": None,
            "dielectricMaterial": None,
            "manufacturer": None,
            "partNumber": None,
            "mainColor": None,
            "appearance": None,
            "stripes": None,
            "pullback": None,
            "weld": None,
        },
    }
    assert connection["attachments"] == [connection["attachment"]]
    assert payload["harnesses"][0]["connections"][1]["attachment"] == {
        "attachmentId": str(UUID(int=902)),
        "parentAttachmentId": None,
        "connected": False,
        "shieldingTarget": None,
        "name": "Connection",
        "nameOverride": "",
        "pinNumber": None,
        "targetKind": None,
        "metadata": [],
        "orderedControlIds": [],
        "resolvedDiameterMm": 1.2,
        "visualOverrides": {
            "diameterMm": None,
            "conductorDiameterMm": None,
            "insulationMaterial": None,
            "conductorMaterial": None,
            "shielding": None,
            "dielectricMaterial": None,
            "manufacturer": None,
            "partNumber": None,
            "mainColor": None,
            "appearance": None,
            "stripes": None,
            "pullback": None,
            "weld": None,
        },
    }


def test_palette_state_resolves_cable_metadata_overrides(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Send both resolved rows and explicit child overrides to the properties editor.
    """
    group = replace(valid_harness.cable_groups[0], metadata_overrides=(("project", "Apollo"),))
    definition = replace(valid_harness, metadata=(("project", "Orion"),), cable_groups=(group,))
    payload = _serialize_definition(
        addin_module,
        monkeypatch,
        definition,
        addin_module.serialize_palette_state,
    )
    cable_group = payload["harnesses"][0]["cableGroups"][0]

    assert cable_group["metadata"] == [{"key": "project", "value": "Apollo"}]
    assert cable_group["metadataOverrides"] == [{"key": "project", "value": "Apollo"}]


def test_palette_state_includes_identity_owned_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Expose identity-owned metadata to both metadata-only property dialogs.
    """
    junction = JunctionDefinition(
        UUID(int=902),
        "Junction 01",
        valid_harness.controls[0].control_id,
        metadata=(("panel", "P2"),),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(valid_harness.connections[0], metadata=(("connector", "J1"),)),
            valid_harness.connections[1],
        ),
        junctions=(junction,),
        pathways=(
            replace(
                valid_harness.pathways[0],
                start_metadata=(("station", "left"),),
                end_metadata=(("station", "right"),),
            ),
        ),
    )
    payload = _serialize_definition(
        addin_module,
        monkeypatch,
        definition,
        addin_module.serialize_palette_state,
    )
    harness = payload["harnesses"][0]

    assert harness["connections"][0]["metadata"] == [{"key": "connector", "value": "J1"}]
    assert harness["junctions"][0]["metadata"] == [{"key": "panel", "value": "P2"}]
    assert harness["pathways"][0]["startMetadata"] == [{"key": "station", "value": "left"}]
    assert harness["pathways"][0]["endMetadata"] == [{"key": "station", "value": "right"}]


@pytest.mark.parametrize(
    ("configured", "active", "expected"),
    (
        ("light", "light", {"mode": "fixed", "active": "light"}),
        ("dark-gray", "dark-gray", {"mode": "fixed", "active": "dark"}),
        ("dark-blue", "dark-blue", {"mode": "fixed", "active": "dark"}),
        ("device", "dark-gray", {"mode": "device", "active": "dark"}),
    ),
)
def test_palette_theme_matches_fusion_configuration_and_active_device_theme(
    addin_module: _PaletteLifecycleModule,
    configured: str,
    active: str,
    expected: dict[str, str],
) -> None:
    """
    Distinguish fixed Fusion themes from the active device-following theme.
    """
    themes = SimpleNamespace(
        LightGrayUserInterfaceTheme="light",
        DarkGrayUserInterfaceTheme="dark-gray",
        DarkBlueUserInterfaceTheme="dark-blue",
        DeviceUserInterfaceTheme="device",
    )
    sys.modules["adsk.core"].UserInterfaceThemes = themes  # type: ignore[attr-defined]
    application = SimpleNamespace(
        preferences=SimpleNamespace(
            generalPreferences=SimpleNamespace(
                userInterfaceTheme=configured,
                activeUserInterfaceTheme=active,
            )
        )
    )

    assert addin_module._palette_theme_payload(application) == expected


def test_palette_theme_request_reads_only_the_current_fusion_theme(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Support lightweight device-theme polling without serializing harness state.
    """
    application = object()
    theme_reader = Mock(return_value={"mode": "device", "active": "dark"})
    state_reader = Mock()
    monkeypatch.setattr(addin_module, "_palette_theme_payload", theme_reader)
    monkeypatch.setattr(addin_module, "serialize_palette_state", state_reader)

    response = json.loads(addin_module._dispatch_palette_action(application, "get_theme", "{}"))

    assert response == {"ok": True, "theme": {"active": "dark", "mode": "device"}}
    theme_reader.assert_called_once_with(application)
    state_reader.assert_not_called()


def test_palette_render_state_reports_preview_or_solids_but_never_both(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Project live Fusion output into the mutually exclusive Render menu checks.
    """
    design = object()
    component = object()
    application = SimpleNamespace(activeProduct=object())
    gateway = SimpleNamespace(harness_component=Mock(return_value=component))
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda _product: design)  # type: ignore[attr-defined]
    occurrences = Mock(return_value=())
    output_mode = Mock(return_value="solids")
    has_preview = Mock(return_value=True)
    monkeypatch.setattr(addin_module, "generated_cable_group_occurrences", occurrences)
    monkeypatch.setattr(addin_module, "generated_cable_group_output_mode", output_mode)
    monkeypatch.setattr(addin_module, "has_route_preview_for_harness", has_preview)

    assert addin_module._harness_render_state(application, gateway, valid_harness) == (
        True,
        False,
        False,
    )

    occurrences.return_value = (object(),)
    has_preview.reset_mock()
    assert addin_module._harness_render_state(application, gateway, valid_harness) == (
        False,
        True,
        False,
    )
    has_preview.assert_not_called()

    output_mode.return_value = "finalized"
    assert addin_module._harness_render_state(application, gateway, valid_harness) == (
        False,
        False,
        True,
    )


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
