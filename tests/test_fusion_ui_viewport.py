"""Focused Fusion UI regressions for viewport."""

from __future__ import annotations

from tests.fusion_ui_support import (
    HarnessDefinition,
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    cast,
    dumps,
    json,
    pytest,
    sys,
)


@pytest.mark.parametrize(
    ("member_type", "identity_attribute", "expected_tokens"),
    [
        ("control", "control_id", ("fusion-gate-token",)),
        ("connection", "connection_id", ("fusion-start-token",)),
        ("wire", "wire_id", ("fusion-start-token", "fusion-end-token")),
    ],
)
def test_resolves_palette_members_to_linked_geometry_tokens(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
    member_type: str,
    identity_attribute: str,
    expected_tokens: tuple[str, ...],
) -> None:
    """
    Resolve stable UI identities without exposing opaque Fusion tokens to HTML.
    """
    collections = {
        "control": valid_harness.controls,
        "connection": valid_harness.connections,
        "wire": valid_harness.wires,
    }
    member_id = getattr(collections[member_type][0], identity_attribute)

    tokens = addin_module._member_entity_tokens(valid_harness, member_type, member_id)

    assert tokens == expected_tokens


def test_highlights_both_wire_endpoint_profiles(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Highlight a wire's generated body together with both endpoint profiles.
    """
    start_profile = object()
    end_profile = object()
    profiles_by_token = {
        "fusion-start-token": [start_profile],
        "fusion-end-token": [end_profile],
    }
    design = SimpleNamespace(
        findEntityByToken=profiles_by_token.get,
        rootComponent=SimpleNamespace(customGraphicsGroups=SimpleNamespace(count=0)),
    )
    selections = SimpleNamespace(clear=Mock(return_value=True), add=Mock(return_value=True))
    viewport = SimpleNamespace(refresh=Mock())
    generated_body = object()
    harness_component = object()
    application = SimpleNamespace(
        userInterface=SimpleNamespace(activeSelections=selections),
        activeViewport=viewport,
    )
    gateway = SimpleNamespace(
        read_harness_definition=lambda _harness_id: dumps(valid_harness),
        harness_component=Mock(return_value=harness_component),
    )
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Profile = SimpleNamespace(cast=lambda entity: entity)  # type: ignore[attr-defined]
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    generated_bodies = Mock(return_value=(generated_body,))
    monkeypatch.setattr(addin_module, "generated_wire_bodies", generated_bodies)
    payload = json.dumps(
        {
            "harnessId": str(valid_harness.harness_id),
            "memberType": "wire",
            "memberId": str(valid_harness.wires[0].wire_id),
        }
    )

    count = addin_module._highlight_member(application, payload)

    assert count == 3
    selections.clear.assert_called_once_with()
    assert [call.args[0] for call in selections.add.call_args_list] == [
        start_profile,
        end_profile,
        generated_body,
    ]
    generated_bodies.assert_called_once_with(
        design.rootComponent,
        harness_component,
        (valid_harness.wires[0].wire_id,),
    )
    viewport.refresh.assert_called_once_with()


def test_connection_highlights_its_generated_wire_group_body(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Select a grouped body together with the physical connection profile.
    """
    from dataclasses import replace
    from uuid import UUID

    from wire_bundler.domain import WireGroupDefinition

    connection = valid_harness.connections[0]
    group = WireGroupDefinition(
        UUID(int=880),
        tuple(item.connection_id for item in valid_harness.connections),
    )
    definition = replace(valid_harness, wire_groups=(group,))
    profile = object()
    group_body = object()
    design = SimpleNamespace(
        findEntityByToken=lambda _token: [profile],
        rootComponent=SimpleNamespace(customGraphicsGroups=SimpleNamespace(count=0)),
    )
    selections = SimpleNamespace(clear=Mock(return_value=True), add=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(activeSelections=selections),
        activeViewport=SimpleNamespace(refresh=Mock()),
    )
    harness_component = object()
    gateway = SimpleNamespace(
        read_harness_definition=lambda _harness_id: dumps(definition),
        harness_component=Mock(return_value=harness_component),
    )
    sys.modules["adsk.fusion"].Profile = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda entity: entity
    )
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "generated_wire_bodies", lambda *_args: ())
    grouped_bodies = Mock(return_value=(group_body,))
    monkeypatch.setattr(addin_module, "generated_wire_group_bodies", grouped_bodies)
    payload = json.dumps(
        {
            "harnessId": str(definition.harness_id),
            "memberType": "connection",
            "memberId": str(connection.connection_id),
        }
    )

    assert addin_module._highlight_member(application, payload) == 2

    assert [call.args[0] for call in selections.add.call_args_list] == [profile, group_body]
    grouped_bodies.assert_called_once_with(
        design.rootComponent,
        harness_component,
        (group.wire_group_id,),
    )


def test_preview_hover_emphasizes_only_matching_centerline(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Emphasize an existing wire preview and clear it without selecting sketch profiles.
    """
    from wire_bundler.fusion import route_preview

    monkeypatch.setitem(vars(route_preview), "adsk", sys.modules["adsk"])
    fusion_module = sys.modules["adsk.fusion"]
    monkeypatch.setitem(
        vars(fusion_module), "CustomGraphicsGroup", SimpleNamespace(cast=lambda item: item)
    )
    monkeypatch.setitem(
        vars(fusion_module), "CustomGraphicsLines", SimpleNamespace(cast=lambda item: item)
    )
    selected = SimpleNamespace(weight=1.0)
    other = SimpleNamespace(weight=1.0)
    child_groups = [
        SimpleNamespace(id=str(valid_harness.wires[0].wire_id), count=1, item=lambda _i: selected),
        SimpleNamespace(id="other-wire", count=1, item=lambda _i: other),
    ]
    group = SimpleNamespace(
        id=route_preview.PREVIEW_GROUP_ID, count=2, item=child_groups.__getitem__
    )
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(
            customGraphicsGroups=SimpleNamespace(count=1, item=lambda _i: group)
        )
    )
    count = addin_module.highlight_route_preview(design, valid_harness.wires[0].wire_id)
    assert count == 1
    assert selected.weight == 5.0
    assert other.weight == 1.0
    assert addin_module.highlight_route_preview(design, None) == 0
    assert selected.weight == 1.0
    design.rootComponent.customGraphicsGroups.count = 0
    assert addin_module.highlight_route_preview(design, valid_harness.wires[0].wire_id) == 0


def test_preview_reports_dynamic_transition_adjustment_as_information(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Continue preview creation and publish a crowded-span adjustment to the palette.
    """
    design = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    gateway = SimpleNamespace(read_harness_definition=Mock(return_value=dumps(valid_harness)))
    send_state = Mock()

    def show(
        _design: object, _definition: HarnessDefinition, **kwargs: object
    ) -> tuple[object, ...]:
        """
        Simulate a successful solve that dynamically corrects one transition.
        """
        notices = cast(list[str], kwargs["notices"])
        notices.append(
            "Wire 001: dynamically adjusted transitions between profiles 2 and 3 "
            "from 5.063 mm to 4.563 mm; the 0.525 mm sweep radius is preserved."
        )
        return object(), object(), object()

    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "show_route_previews", show)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id)})

    assert addin_module._preview_routes(application, payload) == 3

    viewport.refresh.assert_called_once()
    notice = send_state.call_args.args[1]
    assert notice.startswith("Previewing 3 wire-group route legs.\nWire 001:")
    assert "from 5.063 mm to 4.563 mm" in notice


def test_clear_solids_targets_selected_harness_and_refreshes_viewport(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Delete marked output for one harness and report the affected wire count.
    """
    component = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    gateway = SimpleNamespace(harness_component=Mock(return_value=component))
    clear = Mock(return_value=3)
    send_state = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "clear_wire_solids", clear)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id)})

    assert addin_module._clear_solids(application, payload) == 3

    gateway.harness_component.assert_called_once_with(valid_harness.harness_id)
    clear.assert_called_once_with(component)
    viewport.refresh.assert_called_once()
    send_state.assert_called_once_with(application, "Cleared 3 wire solids.")


def test_generate_solids_uses_grouped_geometry_and_reports_group_count(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Route the palette command to grouped generation with rebuild confirmation.
    """
    component = object()
    design = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    gateway = SimpleNamespace(
        read_harness_definition=Mock(return_value=dumps(valid_harness)),
        harness_component=Mock(return_value=component),
    )
    generate = Mock(return_value=2)
    send_state = Mock()
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "generate_wire_group_solids", generate)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id), "replaceExisting": True})

    assert addin_module._generate_solids(application, payload) == 2

    notices = generate.call_args.args[4]
    assert notices == []
    generate.assert_called_once_with(design, component, valid_harness, True, notices)
    viewport.refresh.assert_called_once_with()
    send_state.assert_called_once_with(application, "Generated 2 wire-group solids.")
