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


def test_history_sync_does_not_edit_model_or_redraw(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
) -> None:
    """
    Reconcile restored caches and palette without starting an edit that clears Redo.
    """
    design = object()
    application = SimpleNamespace(activeProduct=design)
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    fusion_module = sys.modules["adsk.fusion"]
    fusion_module.Design = SimpleNamespace(cast=lambda value: value)  # type: ignore[attr-defined]
    gateway = Mock()
    reconcile = Mock()
    sent = Mock()
    refreshed = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(
        addin_module,
        "load_harnesses",
        Mock(return_value=(SimpleNamespace(definition=valid_harness),)),
    )
    monkeypatch.setattr(addin_module, "reconcile_preview_history", reconcile)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    viewport = importlib.import_module("wire_bundler.fusion.ui.viewport")
    monkeypatch.setitem(vars(viewport), "_refresh_active_preview", refreshed)
    addin_module._HistoryChangedHandler().notify(SimpleNamespace(commandId="UndoCommand"))
    reconcile.assert_called_once_with(design, (valid_harness,))
    sent.assert_called_once_with(application)
    refreshed.assert_not_called()
    assert gateway.mock_calls == []


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
    assert addin_module.ADD_WIRES_COMMAND_ID in command_ids
