"""Focused Fusion UI regressions for lifecycle."""

from __future__ import annotations

from tests.fusion_ui_support import (
    Any,
    HarnessDefinition,
    Mock,
    SimpleNamespace,
    _configure_save_test,
    _PaletteLifecycleModule,
    cast,
    importlib,
    pytest,
    sys,
)


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
