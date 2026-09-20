"""Focused Fusion UI regressions for palette."""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    json,
    pytest,
    sys,
)


def test_solid_generation_fails_native_transaction_on_kernel_error(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Abort the native command if solid generation fails, preserving Undo/Redo semantics.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    monkeypatch.setitem(
        vars(addin_module), "_generate_solids", Mock(side_effect=RuntimeError("Cable 002 failed"))
    )
    monkeypatch.setattr(addin_module, "_log_to_fusion", Mock())
    args = SimpleNamespace(executeFailed=False)
    handler = addin_module._PaletteEditExecuteHandler(("generate_solids", "{}", document))
    handler.notify(args)
    assert args.executeFailed
    assert args.executeFailedMessage == "Cable 002 failed"
    assert not handler.clear_preview_after_destroy


def test_successful_solid_generation_clears_preview_after_command_destroy(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Remove transient graphics only after Fusion closes the successful transaction.
    """
    document = object()
    application = SimpleNamespace(activeDocument=document)
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    generate = Mock(return_value=3)
    clear = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "_generate_solids", generate)
    monkeypatch.setattr(addin_module, "_clear_preview", clear)
    execute = addin_module._PaletteEditExecuteHandler(("generate_solids", "{}", document))
    destroyed = addin_module._PaletteEditDestroyedHandler(execute)
    args = SimpleNamespace(executeFailed=False)

    execute.notify(args)

    assert execute.clear_preview_after_destroy
    clear.assert_not_called()
    destroyed.notify(SimpleNamespace())
    clear.assert_called_once_with(application)


def test_clear_preview_deletes_graphics_outside_edit_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refresh Fusion after deleting transient graphics so they disappear immediately.
    """
    design = object()
    viewport = Mock()
    application = SimpleNamespace(activeViewport=viewport)
    clear = Mock(return_value=1)
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(addin_module, "_clear_highlight", Mock())
    monkeypatch.setattr(addin_module, "clear_route_previews", clear)

    assert addin_module._clear_preview(application) == 1

    clear.assert_called_once_with(design)
    viewport.refresh.assert_called_once()


def test_clear_preview_palette_event_bypasses_model_edit_command(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Complete transient cleanup synchronously before returning to the palette.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    clear = Mock(return_value=2)
    open_edit = Mock()
    monkeypatch.setattr(addin_module, "_clear_preview", clear)
    monkeypatch.setattr(addin_module, "_open_palette_edit", open_edit)
    args = SimpleNamespace(action="clear_preview", data="{}", returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    clear.assert_called_once_with(application)
    open_edit.assert_not_called()
    assert json.loads(args.returnData) == {
        "ok": True,
        "notice": "Cleared 2 route-preview graphics groups.",
    }


def test_add_junction_palette_event_opens_native_selector(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the background-menu action through the dedicated Fusion command.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    opened = Mock()
    monkeypatch.setattr(addin_module, "_open_add_junction_command", opened)
    data = json.dumps({"harnessId": str(UUID(int=1))})
    args = SimpleNamespace(action="add_junction", data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    opened.assert_called_once_with(application, data)
    assert json.loads(args.returnData) == {"ok": True}


def test_add_junction_relationship_palette_event_opens_native_selector(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the popup action through the pathway-ending geometry command.
    """
    application = object()
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    opened = Mock()
    monkeypatch.setattr(
        addin_module,
        "_open_add_junction_relationship_command",
        opened,
    )
    data = json.dumps({"harnessId": str(UUID(int=1)), "junctionId": str(UUID(int=2))})
    args = SimpleNamespace(action="add_junction_relationship", data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    opened.assert_called_once_with(application, data)
    assert json.loads(args.returnData) == {"ok": True}
