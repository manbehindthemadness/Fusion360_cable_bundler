"""
Focused Fusion UI regressions for lifecycle.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Any,
    HarnessDefinition,
    Mock,
    SimpleNamespace,
    _configure_save_test,
    _PaletteLifecycleModule,
    cast,
    importlib,
    json,
    pytest,
    replace,
    sys,
)


def test_lifecycle_checkpoint_reports_dirty_transition_without_editing_design(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Compare document state across lifecycle stages without writing to the model.
    """
    attribute = SimpleNamespace(value='{"name":"Harness"}')
    design = SimpleNamespace(
        allComponents=SimpleNamespace(count=2),
        timeline=SimpleNamespace(count=3),
        findAttributes=Mock(return_value=(attribute,)),
    )
    document = SimpleNamespace(
        isModified=False,
        dataFile=SimpleNamespace(versionNumber=75),
    )
    application = SimpleNamespace(activeDocument=document, activeProduct=design)
    fusion_module = sys.modules["adsk.fusion"]
    monkeypatch.setitem(vars(fusion_module), "Design", SimpleNamespace(cast=lambda value: value))
    log = Mock()
    monkeypatch.setattr(addin_module, "_log_to_fusion", log)

    addin_module._log_document_checkpoint(application, "stop:entry")
    document.isModified = True
    addin_module._log_document_checkpoint(application, "start:entry")

    before = json.loads(log.call_args_list[0].args[0].split(": ", 1)[1])
    after = json.loads(log.call_args_list[1].args[0].split(": ", 1)[1])
    assert before["modified"] is False
    assert after["modified"] is True
    assert before["harnessDigest"] == after["harnessDigest"]
    assert before["harnessDefinitions"] == after["harnessDefinitions"] == 1
    assert before["components"] == after["components"] == 2
    assert before["timeline"] == after["timeline"] == 3
    assert after["savedVersion"] == 75
    design.findAttributes.assert_called_with(
        addin_module.ATTRIBUTE_GROUP,
        addin_module.DEFINITION_ATTRIBUTE_NAME,
    )


def test_lifecycle_checkpoint_keeps_digest_when_timeline_is_unavailable(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A host-side timeline failure must not hide independent harness evidence.
    """

    class _UnavailableTimeline:
        """
        Model a Fusion timeline property that cannot be read in this state.
        """

        @property
        def count(self) -> int:
            """
            Raise as the Fusion proxy does for an unavailable timeline.
            """
            raise RuntimeError("unavailable")

    design = SimpleNamespace(
        allComponents=SimpleNamespace(count=2),
        timeline=_UnavailableTimeline(),
        findAttributes=Mock(return_value=(SimpleNamespace(value="harness"),)),
    )
    application = SimpleNamespace(activeProduct=design, activeDocument=None)
    fusion_module = sys.modules["adsk.fusion"]
    monkeypatch.setitem(vars(fusion_module), "Design", SimpleNamespace(cast=lambda value: value))
    log = Mock()
    monkeypatch.setattr(addin_module, "_log_to_fusion", log)

    addin_module._log_document_checkpoint(application, "start:entry")

    snapshot = json.loads(log.call_args.args[0].split(": ", 1)[1])
    assert snapshot["timelineError"] == "RuntimeError"
    assert snapshot["harnessDefinitions"] == 1
    assert "harnessDigest" in snapshot


def test_save_with_active_preview_temporarily_disables_graphics_cache(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep Custom Graphics out of the saved OGS cache and restore user settings.
    """
    document, compatibility = _configure_save_test(addin_module, monkeypatch, True)

    args = SimpleNamespace(document=document)
    addin_module._DocumentSavingHandler().notify(args)
    assert not compatibility.isCacheGraphicsOnDocumentSave

    addin_module._DocumentSavedHandler().notify(args)
    assert compatibility.isCacheGraphicsOnDocumentSave
    assert addin_module._runtime.graphics_cache_restore_value is None


def test_save_without_active_preview_preserves_graphics_cache_setting(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Leave unrelated document saves and the user's cache preference untouched.
    """
    document, compatibility = _configure_save_test(addin_module, monkeypatch, False)

    addin_module._DocumentSavingHandler().notify(SimpleNamespace(document=document))

    assert compatibility.isCacheGraphicsOnDocumentSave
    assert addin_module._runtime.graphics_cache_restore_value is None


@pytest.mark.parametrize("command_id", ("UndoCommand", "RedoCommand"))
def test_history_sync_defers_stripes_until_replaced_component_settles(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    command_id: str,
) -> None:
    """
    Reconcile restored state and recreate session-only stripes after history travel.
    """
    design = object()
    application = SimpleNamespace(
        activeProduct=design,
        activeViewport=SimpleNamespace(refresh=Mock()),
        fireCustomEvent=Mock(return_value=True),
    )
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    gateway = Mock()
    harness_component = object()
    reconcile = Mock()
    sent = Mock()
    refreshed = Mock()
    restore = Mock(return_value=2)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(
        addin_module,
        "load_harnesses",
        Mock(
            return_value=(
                SimpleNamespace(
                    component_name="Harness A",
                    definition=valid_harness,
                    component_handle=harness_component,
                ),
            )
        ),
    )
    monkeypatch.setattr(addin_module, "reconcile_preview_history", reconcile)
    monkeypatch.setattr(addin_module, "restore_cable_group_stripe_graphics", restore)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    viewport = importlib.import_module("cable_bundler.fusion.ui.viewport")
    monkeypatch.setitem(vars(viewport), "_refresh_active_preview", refreshed)
    addin_module._HistoryChangedHandler().notify(SimpleNamespace(commandId=command_id))
    reconcile.assert_called_once_with(design, (valid_harness,))
    application.fireCustomEvent.assert_called_once_with(
        addin_module._DEFERRED_STRIPE_RESTORE_EVENT_ID
    )
    restore.assert_not_called()
    sent.assert_called_once_with(application)
    refreshed.assert_not_called()

    addin_module._DeferredStripeRestoreHandler().notify(SimpleNamespace())

    restore.assert_called_once_with(harness_component, valid_harness)
    application.activeViewport.refresh.assert_called_once()
    assert gateway.mock_calls == []


@pytest.mark.parametrize("command_id", ("MoveCommand", "DeleteCommand"))
def test_native_command_termination_does_not_create_an_undo_entry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    command_id: str,
) -> None:
    """
    Keep post-command synchronization read-only for ordinary and destructive edits.
    """
    design = object()
    application = SimpleNamespace(activeProduct=design)
    harness_component = object()
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    gateway = object()
    reconcile = Mock()
    send = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(
        addin_module,
        "load_harnesses",
        Mock(
            return_value=(
                SimpleNamespace(
                    component_name="Harness A",
                    definition=valid_harness,
                    component_handle=harness_component,
                ),
            )
        ),
    )
    monkeypatch.setattr(addin_module, "reconcile_preview_history", reconcile)
    monkeypatch.setattr(addin_module, "_send_palette_state", send)

    addin_module._HistoryChangedHandler().notify(SimpleNamespace(commandId=command_id))

    reconcile.assert_called_once_with(design, (valid_harness,))
    send.assert_called_once_with(application)


@pytest.mark.parametrize(
    "command_id",
    (
        "PanCommand",
        "OrbitCommand",
        "ZoomCommand",
        "ZoomWindowCommand",
        "FitCommand",
        "SelectCommand",
        "ClearSelectionCommand",
        "ViewCubeOrbitCommand",
        "ScriptsManagerCommand",
    ),
)
def test_view_navigation_keeps_contact_geometry_and_skips_palette_refresh(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    command_id: str,
) -> None:
    """
    Camera, selection, and add-in management leave the contact diagram unchanged.
    """
    cache = importlib.import_module("cable_bundler.fusion.interface_contact_cache")
    design = SimpleNamespace(rootComponent=SimpleNamespace(entityToken="active"))
    entity = SimpleNamespace(entityToken="contact", isValid=True)
    cache.remember_contact_entity(design, entity)
    application = SimpleNamespace(activeProduct=design)
    monkeypatch.setitem(
        vars(sys.modules["adsk.core"]), "Application", SimpleNamespace(get=lambda: application)
    )
    read_harnesses = Mock()
    send = Mock()
    monkeypatch.setattr(addin_module, "load_harnesses", read_harnesses)
    monkeypatch.setattr(addin_module, "_send_palette_state", send)
    revision = addin_module._runtime.contact_geometry_revision
    try:
        addin_module._HistoryChangedHandler().notify(SimpleNamespace(commandId=command_id))
        assert addin_module._runtime.contact_geometry_revision == revision
        assert cache._entries["contact"] == (entity,)
        read_harnesses.assert_not_called()
        send.assert_not_called()
    finally:
        cache.clear_contact_resolutions()


@pytest.mark.parametrize("reason", (2, 3, 4, 5))
def test_noncompleted_native_command_does_not_reload_contact_geometry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    reason: int,
) -> None:
    """
    A canceled or pre-empted command leaves the model and diagram unchanged.
    """
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(
        vars(core), "CommandTerminationReason", SimpleNamespace(CompletedTerminationReason=1)
    )
    application = SimpleNamespace(activeProduct=object())
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    read_harnesses = Mock()
    send = Mock()
    monkeypatch.setattr(addin_module, "load_harnesses", read_harnesses)
    monkeypatch.setattr(addin_module, "_send_palette_state", send)
    clear = Mock()
    monkeypatch.setitem(vars(addin_module), "clear_contact_resolutions", clear)
    revision = addin_module._runtime.contact_geometry_revision

    addin_module._HistoryChangedHandler().notify(
        SimpleNamespace(commandId="MoveCommand", terminationReason=reason)
    )

    assert addin_module._runtime.contact_geometry_revision == revision
    clear.assert_not_called()
    read_harnesses.assert_not_called()
    send.assert_not_called()


def test_completed_native_command_still_reloads_contact_geometry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A successful edit must invalidate the diagram's geometry snapshot.
    """
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(
        vars(core), "CommandTerminationReason", SimpleNamespace(CompletedTerminationReason=1)
    )
    application = SimpleNamespace(activeProduct=object())
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(
        vars(sys.modules["adsk.fusion"]), "Design", SimpleNamespace(cast=lambda value: value)
    )
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: object())
    monkeypatch.setattr(addin_module, "load_harnesses", Mock(return_value=()))
    monkeypatch.setattr(addin_module, "reconcile_preview_history", Mock())
    send = Mock()
    monkeypatch.setattr(addin_module, "_send_palette_state", send)
    clear = Mock()
    monkeypatch.setitem(vars(addin_module), "clear_contact_resolutions", clear)
    revision = addin_module._runtime.contact_geometry_revision

    addin_module._HistoryChangedHandler().notify(
        SimpleNamespace(commandId="MoveCommand", terminationReason=1)
    )

    assert addin_module._runtime.contact_geometry_revision == revision + 1
    clear.assert_called_once_with()
    send.assert_called_once_with(application)


def test_deferred_stripe_restore_event_registers_and_releases(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Retain the idle callback for the add-in lifetime and unregister it on cleanup.
    """
    event = SimpleNamespace(add=Mock(return_value=True), remove=Mock(return_value=True))
    application = SimpleNamespace(
        registerCustomEvent=Mock(return_value=event),
        unregisterCustomEvent=Mock(return_value=True),
    )

    addin_module._register_deferred_stripe_restore(application)

    handler = addin_module._runtime.deferred_stripe_restore_handler
    assert handler is not None
    event.add.assert_called_once_with(handler)

    addin_module._remove_deferred_stripe_restore(application)

    event.remove.assert_called_once_with(handler)
    application.unregisterCustomEvent.assert_called_once_with(
        addin_module._DEFERRED_STRIPE_RESTORE_EVENT_ID
    )
    assert addin_module._runtime.deferred_stripe_restore_event is None
    assert addin_module._runtime.deferred_stripe_restore_handler is None


def test_deferred_palette_launch_event_registers_and_releases(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep native dialogs outside the palette bridge callback lifetime.
    """
    event = SimpleNamespace(add=Mock(return_value=True), remove=Mock(return_value=True))
    application = SimpleNamespace(
        registerCustomEvent=Mock(return_value=event),
        unregisterCustomEvent=Mock(return_value=True),
    )

    addin_module._register_deferred_palette_launch(application)

    handler = addin_module._runtime.deferred_palette_launch_handler
    assert handler is not None
    event.add.assert_called_once_with(handler)

    addin_module._remove_deferred_palette_launch(application)

    event.remove.assert_called_once_with(handler)
    application.unregisterCustomEvent.assert_called_once_with(
        addin_module._DEFERRED_PALETTE_LAUNCH_EVENT_ID
    )
    assert addin_module._runtime.deferred_palette_launch_event is None
    assert addin_module._runtime.deferred_palette_launch_handler is None


def test_reload_restores_stripes_for_each_readable_harness(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Rebuild session-only stripe graphics when the add-in starts again.
    """
    application = SimpleNamespace(activeViewport=SimpleNamespace(refresh=Mock()))
    harness_component = object()
    damaged_component = object()
    gateway = object()
    restore = Mock(return_value=3)
    results = (
        SimpleNamespace(
            component_name="Harness A",
            definition=valid_harness,
            component_handle=harness_component,
        ),
        SimpleNamespace(
            component_name="Damaged",
            definition=None,
            component_handle=damaged_component,
        ),
    )
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "load_harnesses", lambda _gateway: results)
    monkeypatch.setattr(addin_module, "restore_cable_group_stripe_graphics", restore)

    assert addin_module._restore_active_stripe_graphics(application) == 3

    restore.assert_called_once_with(harness_component, valid_harness)
    application.activeViewport.refresh.assert_called_once()


def test_reload_hides_previews_only_for_finalized_harnesses(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Keep working previews visible when another harness is finalized.
    """
    lifecycle = importlib.import_module("cable_bundler.fusion.ui.lifecycle")
    working = object()
    finalized = object()
    working_definition = replace(
        valid_harness,
        harness_id=UUID("30000000-0000-0000-0000-000000000096"),
        name="Working Harness",
    )
    results = (
        SimpleNamespace(definition=working_definition, component_handle=working),
        SimpleNamespace(definition=valid_harness, component_handle=finalized),
        SimpleNamespace(definition=None, component_handle=object()),
    )
    hide = Mock(return_value=1)
    monkeypatch.setitem(
        vars(lifecycle),
        "has_finalized_cable_group_output",
        lambda component: component is finalized,
    )
    monkeypatch.setitem(vars(lifecycle), "hide_route_preview_for_harness", hide)
    design = object()

    assert lifecycle._hide_loaded_finalized_previews(design, results) == 1

    hide.assert_called_once_with(design, valid_harness)


def test_restored_route_preview_visibility_is_scoped_by_harness(
    addin_module: _PaletteLifecycleModule,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Hide a recovered finalized preview without touching another harness.
    """
    from cable_bundler.fusion import route_preview

    finalized_group = SimpleNamespace(
        id=f"{route_preview.PREVIEW_GROUP_ID}:finalized",
        name=f"{valid_harness.name} Route Preview",
        isVisible=True,
    )
    working_group = SimpleNamespace(
        id=f"{route_preview.PREVIEW_GROUP_ID}:working",
        name="Working Route Preview",
        isVisible=True,
    )
    groups = SimpleNamespace(
        count=2,
        item=lambda index: (finalized_group, working_group)[index],
    )
    design = SimpleNamespace(
        rootComponent=SimpleNamespace(customGraphicsGroups=groups),
        allComponents=SimpleNamespace(count=0),
    )

    assert route_preview.hide_route_preview_for_harness(design, valid_harness) == 1
    assert finalized_group.isVisible is False
    assert working_group.isVisible is True


@pytest.mark.parametrize(
    ("modes", "expected"),
    (
        ((), False),
        (("finalized",), True),
        (("finalized", "solids"), False),
    ),
)
def test_loaded_harness_is_finalized_only_when_all_generated_groups_are(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    modes: tuple[str, ...],
    expected: bool,
) -> None:
    """
    Base restored graphics visibility on persisted generated-output modes.
    """
    from cable_bundler.fusion import cable_solid_visibility

    occurrences = tuple(
        SimpleNamespace(
            component=SimpleNamespace(
                attributes=SimpleNamespace(
                    itemByName=lambda _group, _key, mode=mode: SimpleNamespace(
                        value=json.dumps({"output_mode": mode})
                    )
                )
            )
        )
        for mode in modes
    )
    monkeypatch.setattr(
        cable_solid_visibility,
        "_cable_solid_services",
        lambda: SimpleNamespace(generated_cable_group_occurrences=lambda _harness: occurrences),
    )

    assert cable_solid_visibility.has_finalized_cable_group_output(object()) is expected


@pytest.mark.parametrize("metadata", ([], None, 1, "finalized"))
def test_generated_output_mode_treats_non_object_json_as_legacy_solids(
    addin_module: _PaletteLifecycleModule,
    metadata: object,
) -> None:
    """
    Keep malformed generated metadata from aborting add-in startup.
    """
    from cable_bundler.fusion import cable_solid_visibility

    occurrence = SimpleNamespace(
        component=SimpleNamespace(
            attributes=SimpleNamespace(
                itemByName=lambda _group, _key: SimpleNamespace(value=json.dumps(metadata))
            )
        )
    )

    assert cable_solid_visibility.generated_cable_group_output_mode(occurrence) == "solids"


def test_pending_slot_consumes_once_and_rejects_overlap(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Preserve one native-command request without allowing silent replacement.
    """
    slot = addin_module.PendingSlot()
    request = object()
    slot.prepare(request)

    with pytest.raises(RuntimeError, match="already starting"):
        slot.prepare(object())

    assert slot.consume() is request
    assert slot.consume() is None


def test_runtime_releases_ordinary_command_handlers_on_destroy(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Retain ordinary callbacks only through their owning command's lifetime.
    """
    runtime = addin_module.UiRuntime()
    cleanup_handlers: list[object] = []
    command = SimpleNamespace(
        destroy=SimpleNamespace(add=lambda handler: cleanup_handlers.append(handler) or True)
    )
    execute_handler = object()
    validate_handler = object()

    runtime.retain_command_handlers(command, execute_handler, validate_handler)

    assert runtime.handlers == [execute_handler, validate_handler, cleanup_handlers[0]]
    cast(Any, cleanup_handlers[0]).notify(SimpleNamespace())
    assert runtime.handlers == []


def test_registered_command_specs_have_unique_stable_ids(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Keep declarative command registration complete and collision-free.
    """
    command_ids = tuple(spec.command_id for spec in addin_module.COMMAND_SPECS)

    assert len(command_ids) == len(set(command_ids))
    assert addin_module.COMMAND_ID in command_ids
    assert addin_module.ADD_END_COMMAND_ID in command_ids


def test_ui_cleanup_removes_every_registered_command_definition(
    addin_module: _PaletteLifecycleModule,
) -> None:
    """
    Prevent newly registered commands from surviving an add-in stop and blocking restart.
    """
    deleted_ids: list[str] = []

    def command_definition(command_id: str) -> object:
        return SimpleNamespace(deleteMe=lambda: deleted_ids.append(command_id))

    user_interface = SimpleNamespace(
        workspaces=SimpleNamespace(itemById=lambda _identity: None),
        commandDefinitions=SimpleNamespace(itemById=command_definition),
        palettes=SimpleNamespace(itemById=lambda _identity: None),
    )

    addin_module._remove_user_interface(user_interface)

    registered_ids = {spec.command_id for spec in addin_module.COMMAND_SPECS}
    attachment_id = importlib.import_module(
        "cable_bundler.fusion.ui.constants"
    ).ATTACH_CABLE_END_COMMAND_ID
    assert registered_ids <= set(deleted_ids)
    assert attachment_id in deleted_ids
