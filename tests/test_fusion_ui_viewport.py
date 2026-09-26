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


@pytest.fixture(autouse=True)
def hover_widget_adapter(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> Mock:
    """
    Isolate rendering while viewport tests exercise node ownership and selection.
    """
    import importlib

    viewport = importlib.import_module("cable_bundler.fusion.ui.viewport")
    monkeypatch.setitem(vars(viewport), "clear_hover_widgets", Mock())
    shown = Mock()
    monkeypatch.setitem(vars(viewport), "show_hover_widgets", shown)
    monkeypatch.setitem(vars(viewport), "profile_point", lambda profile: profile)
    monkeypatch.setitem(vars(viewport), "target_point", lambda entity, _target: entity)
    return shown


def test_finalize_hides_support_sketches_and_graphics_but_not_face_bodies(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Hide construction aids without resolving or changing face attachment targets.
    """
    from dataclasses import replace

    from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment

    connection = valid_harness.connections[0]
    face_attachment = CableEndAttachment(
        AttachmentTargetKind.FACE,
        "face-token",
        "Target face",
        parameters=(0.25, 0.75),
        attachment_id=UUID(int=910),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=face_attachment),
            *valid_harness.connections[1:],
        ),
    )
    shared_sketch = SimpleNamespace(
        entityToken="shared-sketch-token",
        isValid=True,
        isLightBulbOn=True,
    )
    profile = SimpleNamespace(parentSketch=shared_sketch)
    token_entities = {
        token: [profile]
        for token in {
            *(token for item in definition.connections for token in item.member_tokens),
            *(control.entity_token for control in definition.controls if control.entity_token),
        }
    }
    stale_sketch = SimpleNamespace(
        entityToken="stale-sketch-token",
        isValid=True,
        isLightBulbOn=True,
    )
    stale_profile = SimpleNamespace(isValid=False, parentSketch=stale_sketch)
    first_token = next(iter(token_entities))
    token_entities[first_token] = [stale_profile, profile]
    design = SimpleNamespace(findEntityByToken=lambda token: token_entities.get(token, []))
    hide_routes = Mock(return_value=1)
    hide_refines = Mock(return_value=1)
    resolve_target = Mock(side_effect=AssertionError("Face target body was resolved for hiding."))
    monkeypatch.setattr(addin_module, "hide_route_previews", hide_routes)
    monkeypatch.setattr(addin_module, "hide_refine_graphics", hide_refines)
    monkeypatch.setattr(addin_module, "resolve_attachment_target", resolve_target)

    assert addin_module._hide_finalized_supports(design, definition) == 3

    assert not shared_sketch.isLightBulbOn
    assert stale_sketch.isLightBulbOn
    hide_routes.assert_called_once_with(design)
    hide_refines.assert_called_once_with(design)
    resolve_target.assert_not_called()

    reveal_routes = Mock(return_value=1)
    reveal_refines = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "reveal_route_previews", reveal_routes)
    monkeypatch.setattr(addin_module, "reveal_refine_graphics", reveal_refines)

    assert addin_module._show_render_supports(design, definition) == 3
    assert shared_sketch.isLightBulbOn
    reveal_routes.assert_called_once_with(design)
    reveal_refines.assert_called_once_with(design)
    resolve_target.assert_not_called()


def test_finalize_hides_non_body_attachment_support(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Hide a connected construction point without affecting unrelated model bodies.
    """
    from dataclasses import replace

    from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment

    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        AttachmentTargetKind.CONSTRUCTION_POINT,
        "construction-point-token",
        "Support point",
        attachment_id=UUID(int=911),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(connection, attachment=attachment),
            *valid_harness.connections[1:],
        ),
    )
    support_point = SimpleNamespace(isLightBulbOn=True)
    design = SimpleNamespace(findEntityByToken=lambda _token: [])
    monkeypatch.setattr(addin_module, "hide_route_previews", Mock(return_value=0))
    monkeypatch.setattr(addin_module, "hide_refine_graphics", Mock(return_value=0))
    monkeypatch.setattr(addin_module, "reveal_route_previews", Mock(return_value=0))
    monkeypatch.setattr(addin_module, "reveal_refine_graphics", Mock(return_value=0))
    monkeypatch.setattr(
        addin_module,
        "resolve_attachment_target",
        lambda _design, _target: support_point,
    )

    assert addin_module._hide_finalized_supports(design, definition) == 1
    assert not support_point.isLightBulbOn
    assert addin_module._show_render_supports(design, definition) == 1
    assert support_point.isLightBulbOn


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


# noinspection DuplicatedCode
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


def test_contact_hover_selects_only_its_persistent_fusion_target(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    hover_widget_adapter: Mock,
) -> None:
    """
    Scope contact identity to its Interface and select the matching target kind.
    """
    import importlib
    from dataclasses import replace

    from cable_bundler.domain import (
        AttachmentTargetKind,
        InterfaceContact,
        InterfaceDefinition,
        InterfaceTarget,
        InterfaceTargetKind,
    )

    viewport = importlib.import_module("cable_bundler.fusion.ui.viewport")
    contact = InterfaceContact(UUID(int=900), AttachmentTargetKind.FACE, "face-token")
    interface = InterfaceDefinition(
        UUID(int=901),
        "Socket",
        (InterfaceTarget(InterfaceTargetKind.BODY, "body-token"),),
        (contact,),
    )
    definition = replace(valid_harness, interfaces=(interface,))
    wrong_kind = object()
    face = object()
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(customGraphicsGroups=SimpleNamespace(count=0))
    )
    selections = SimpleNamespace(clear=Mock(return_value=True), add=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(activeSelections=selections),
        activeViewport=SimpleNamespace(refresh=Mock()),
    )
    gateway = SimpleNamespace(read_harness_definition=lambda _id: dumps(definition))
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    resolve = Mock(return_value=(wrong_kind, face))
    monkeypatch.setitem(vars(viewport), "resolve_contact_entities", resolve)
    monkeypatch.setitem(
        vars(viewport),
        "attachment_target_kind",
        lambda entity: (
            AttachmentTargetKind.PROFILE if entity is wrong_kind else AttachmentTargetKind.FACE
        ),
    )
    monkeypatch.setitem(vars(viewport), "highlight_route_members", Mock(return_value=0))
    monkeypatch.setitem(vars(viewport), "highlight_refine_graphics", Mock(return_value=0))
    payload = {
        "harnessId": str(definition.harness_id),
        "memberType": "interface_contact",
        "memberId": str(contact.contact_id),
        "interfaceId": str(interface.interface_id),
    }

    assert addin_module._highlight_member(application, json.dumps(payload)) == 1

    resolve.assert_called_once_with(design, "face-token")
    selections.add.assert_called_once_with(face)
    hover_widget_adapter.assert_called_once_with(design, ())
    payload["interfaceId"] = str(UUID(int=902))
    with pytest.raises(ValueError, match="Interface no longer exists"):
        addin_module._highlight_member(application, json.dumps(payload))


def test_pathway_hover_selects_only_its_gateway_profiles(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    hover_widget_adapter: Mock,
) -> None:
    """
    Highlight only profile-backed gates for a pathway node.
    """
    from cable_bundler.domain import ControlKind

    pathway = valid_harness.pathways[0]
    controls = {control.control_id: control for control in valid_harness.controls}
    profiles = {
        controls[control_id].entity_token: object()
        for control_id in pathway.ordered_control_ids
        if control_id in controls
        and controls[control_id].kind in {ControlKind.ROUTING_GATE, ControlKind.PROFILE_GATE}
        and controls[control_id].entity_token
    }
    design = SimpleNamespace(
        findEntityByToken=lambda token: [profiles[token]],
        rootComponent=SimpleNamespace(customGraphicsGroups=SimpleNamespace(count=0)),
    )
    selections = SimpleNamespace(clear=Mock(return_value=True), add=Mock(return_value=True))
    application = SimpleNamespace(
        userInterface=SimpleNamespace(activeSelections=selections),
        activeViewport=SimpleNamespace(refresh=Mock()),
    )
    gateway = SimpleNamespace(
        read_harness_definition=lambda _harness_id: dumps(valid_harness),
        harness_component=Mock(return_value=object()),
    )
    sys.modules["adsk.fusion"].Profile = SimpleNamespace(  # type: ignore[attr-defined]
        cast=lambda entity: entity
    )
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    cable_groups = Mock(return_value=(UUID(int=881),))
    generated_bodies = Mock(return_value=(object(),))
    route_highlight = Mock(return_value=0)
    refine_highlight = Mock(return_value=0)
    monkeypatch.setattr(addin_module, "_cable_group_ids_for_member", cable_groups)
    monkeypatch.setattr(addin_module, "generated_cable_group_bodies", generated_bodies)
    monkeypatch.setattr(addin_module, "highlight_route_members", route_highlight)
    monkeypatch.setattr(addin_module, "highlight_refine_graphics", refine_highlight)
    payload = json.dumps(
        {
            "harnessId": str(valid_harness.harness_id),
            "memberType": "pathway_gates",
            "memberId": str(pathway.pathway_id),
        }
    )

    result = addin_module._highlight_member(application, payload)

    assert result == len(profiles)
    assert [call.args[0] for call in selections.add.call_args_list] == list(profiles.values())
    cable_groups.assert_not_called()
    generated_bodies.assert_not_called()
    route_highlight.assert_called_once_with(
        design,
        (),
        connection_ids=(),
        control_ids=(),
    )
    refine_highlight.assert_called_once_with(design, ())
    hover_widget_adapter.assert_called_once_with(design, ())


# noinspection DuplicatedCode
def test_attachment_highlight_selects_targets_and_generated_sweep(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    hover_widget_adapter: Mock,
) -> None:
    """
    Select every resolvable Fusion target owned by one connection node.
    """
    from dataclasses import replace

    from cable_bundler.domain import AttachmentTargetKind, CableEndAttachment, CableEndTarget

    connection = valid_harness.connections[0]
    attachment = CableEndAttachment(
        AttachmentTargetKind.PROFILE,
        "main-token",
        "Main target",
        attachment_id=UUID(int=701),
        shielding_target=CableEndTarget(
            AttachmentTargetKind.CONSTRUCTION_POINT,
            "shield-token",
            "Shield target",
        ),
    )
    definition = replace(
        valid_harness,
        connections=(
            replace(
                connection,
                attachment=attachment,
                additional_attachments=(
                    CableEndAttachment(
                        AttachmentTargetKind.PROFILE,
                        "child-token",
                        "Child contact",
                        attachment_id=UUID(int=702),
                        parent_attachment_id=attachment.attachment_id,
                    ),
                ),
            ),
            *valid_harness.connections[1:],
        ),
    )
    main_target = object()
    shielding_target = object()
    resolved = {
        "main-token": main_target,
        "shield-token": shielding_target,
        "child-token": object(),
    }
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(customGraphicsGroups=SimpleNamespace(count=0))
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
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(
        addin_module,
        "resolve_attachment_target",
        lambda _design, target: resolved.get(target.entity_token),
    )
    sweep_body = object()
    generated_bodies = Mock(return_value=(sweep_body,))
    monkeypatch.setattr(addin_module, "generated_attachment_bodies", generated_bodies)
    payload = json.dumps(
        {
            "harnessId": str(definition.harness_id),
            "memberType": "attachment",
            "memberId": str(attachment.attachment_id),
            "connectionId": str(connection.connection_id),
        }
    )

    assert addin_module._highlight_member(application, payload) == 3
    hover_widget_adapter.assert_called_once_with(design, (main_target, shielding_target))
    assert [call.args[0] for call in selections.add.call_args_list] == [
        main_target,
        shielding_target,
        sweep_body,
    ]
    generated_bodies.assert_called_once_with(
        design.rootComponent,
        harness_component,
        attachment.attachment_id,
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
    show_supports = Mock(return_value=4)

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
    monkeypatch.setattr(addin_module, "_show_render_supports", show_supports)
    monkeypatch.setattr(addin_module, "_send_palette_state", send_state)
    payload = json.dumps({"harnessId": str(valid_harness.harness_id)})

    assert addin_module._preview_routes(application, payload) == 3

    clear_solids.assert_called_once_with(component)
    show_supports.assert_called_once_with(design, valid_harness)
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
    hide_supports = Mock(return_value=4)
    show_supports = Mock(return_value=4)
    send_state = Mock()
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "generate_cable_group_solids", generate)
    monkeypatch.setattr(addin_module, "_hide_finalized_supports", hide_supports)
    monkeypatch.setattr(addin_module, "_show_render_supports", show_supports)
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
    if output_mode == "finalized":
        hide_supports.assert_called_once_with(design, valid_harness)
        show_supports.assert_not_called()
    else:
        hide_supports.assert_not_called()
        show_supports.assert_called_once_with(design, valid_harness)
    viewport.refresh.assert_called_once_with()
    send_state.assert_called_once_with(application, expected_notice)
