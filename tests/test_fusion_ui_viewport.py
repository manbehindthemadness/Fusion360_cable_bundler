"""
Focused Fusion UI regressions for viewport.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
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
    Resolve stable group-era UI identities without exposing Fusion tokens to HTML.
    """
    collections = {
        "control": valid_harness.controls,
        "connection": valid_harness.connections,
    }
    member_id = getattr(collections[member_type][0], identity_attribute)

    assert (
        addin_module._member_entity_tokens(valid_harness, member_type, member_id) == expected_tokens
    )


def test_connection_highlights_its_generated_cable_group_body(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Select a grouped body together with the physical connection profile.
    """
    from dataclasses import replace
    from uuid import UUID

    from cable_bundler.domain import CableGroupDefinition

    connection = valid_harness.connections[0]
    group = CableGroupDefinition(
        UUID(int=880),
        tuple(item.connection_id for item in valid_harness.connections),
    )
    definition = replace(valid_harness, cable_groups=(group,))
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
    grouped_bodies = Mock(return_value=(group_body,))
    monkeypatch.setattr(addin_module, "generated_cable_group_bodies", grouped_bodies)
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
        (group.cable_group_id,),
    )


def test_preview_hover_emphasizes_only_matching_centerline(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Emphasize one group route leg and clear it without selecting sketch profiles.
    """
    from cable_bundler.fusion import route_preview

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
    route_id = UUID(int=777)
    child_groups = [
        SimpleNamespace(
            id=str(route_id),
            count=1,
            item=lambda _i: selected,
        ),
        SimpleNamespace(id="other-cable", count=1, item=lambda _i: other),
    ]
    group = SimpleNamespace(
        id=route_preview.PREVIEW_GROUP_ID, count=2, item=child_groups.__getitem__
    )
    group_id = valid_harness.cable_groups[0].cable_group_id
    monkeypatch.setitem(
        route_preview._preview_states,
        group.id,
        SimpleNamespace(
            route_group_ids={route_id: group_id},
            route_connection_ids={},
            route_pathway_ids={},
            route_control_ids={},
        ),
    )
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(
            customGraphicsGroups=SimpleNamespace(count=1, item=lambda _i: group)
        )
    )
    count = addin_module.highlight_route_preview(design, group_id)
    assert count == 1
    assert selected.weight == 5.0
    assert other.weight == 1.0
    assert addin_module.highlight_route_preview(design, None) == 0
    assert selected.weight == 1.0
    design.rootComponent.customGraphicsGroups.count = 0
    assert addin_module.highlight_route_preview(design, group_id) == 0


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
    component = object()
    gateway = SimpleNamespace(
        read_harness_definition=Mock(return_value=dumps(valid_harness)),
        harness_component=Mock(return_value=component),
    )
    send_state = Mock()
    clear_solids = Mock(return_value=2)

    def show(
        _design: object, _definition: HarnessDefinition, **kwargs: object
    ) -> tuple[object, ...]:
        """
        Simulate a successful solve that dynamically corrects one transition.
        """
        notices = cast(list[str], kwargs["notices"])
        notices.append(
            "Cable 001: dynamically adjusted transitions between profiles 2 and 3 "
            "from 5.063 mm to 4.563 mm; the 0.525 mm sweep radius is preserved."
        )
        return object(), object(), object()

    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "show_route_previews", show)
    monkeypatch.setattr(addin_module, "clear_cable_solids", clear_solids)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id)})

    assert addin_module._preview_routes(application, payload) == 3

    clear_solids.assert_called_once_with(component)
    viewport.refresh.assert_called_once()
    notice = send_state.call_args.args[1]
    assert notice.startswith(
        "Previewing 3 cable-group route legs.\nCleared 2 cable solids.\nCable 001:"
    )
    assert "from 5.063 mm to 4.563 mm" in notice


def test_clear_solids_targets_selected_harness_and_refreshes_viewport(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Delete marked output for one harness and report the affected cable count.
    """
    component = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    gateway = SimpleNamespace(harness_component=Mock(return_value=component))
    clear = Mock(return_value=3)
    send_state = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "clear_cable_solids", clear)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id)})

    assert addin_module._clear_solids(application, payload) == 3

    gateway.harness_component.assert_called_once_with(valid_harness.harness_id)
    clear.assert_called_once_with(component)
    viewport.refresh.assert_called_once()
    send_state.assert_called_once_with(application, "Cleared 3 cable solids.")


@pytest.mark.parametrize(
    ("entrypoint_name", "output_mode", "expected_notice"),
    (
        ("_generate_solids", "solids", "Generated 2 cable-group solids."),
        ("_finalize_solids", "finalized", "Finalized 2 cable-group geometries."),
    ),
)
def test_generated_output_uses_selected_geometry_mode_and_reports_group_count(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    entrypoint_name: str,
    output_mode: str,
    expected_notice: str,
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
    monkeypatch.setattr(addin_module, "generate_cable_group_solids", generate)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id), "replaceExisting": True})

    entrypoint = (
        addin_module._generate_solids
        if entrypoint_name == "_generate_solids"
        else addin_module._finalize_solids
    )
    assert entrypoint(application, payload) == 2

    notices = generate.call_args.args[4]
    assert notices == []
    generate.assert_called_once_with(
        design,
        component,
        valid_harness,
        True,
        notices,
        output_mode,
    )
    viewport.refresh.assert_called_once_with()
    send_state.assert_called_once_with(application, expected_notice)
