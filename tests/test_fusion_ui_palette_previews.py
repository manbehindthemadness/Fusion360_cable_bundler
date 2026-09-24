"""
Focused Fusion UI regressions for palette.
"""

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


@pytest.mark.parametrize(
    ("action", "generator_name"),
    (
        ("generate_solids", "_generate_solids"),
        ("finalize_solids", "_finalize_solids"),
    ),
)
def test_successful_geometry_generation_clears_preview_after_command_destroy(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    generator_name: str,
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
    monkeypatch.setattr(addin_module, generator_name, generate)
    monkeypatch.setattr(addin_module, "_clear_preview", clear)
    execute = addin_module._PaletteEditExecuteHandler((action, "{}", document))
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


@pytest.mark.parametrize(
    ("action", "launcher_name", "payload"),
    (
        ("add_junction", "_open_add_junction_command", {"harnessId": str(UUID(int=1))}),
        (
            "add_junction_relationship",
            "_open_add_junction_relationship_command",
            {"harnessId": str(UUID(int=1)), "junctionId": str(UUID(int=2))},
        ),
    ),
)
def test_palette_native_selector_launches_after_bridge_response(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    launcher_name: str,
    payload: dict[str, str],
) -> None:
    """
    Return to the palette before opening a requested native Fusion selector.
    """
    application = SimpleNamespace(fireCustomEvent=Mock(return_value=True))
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    opened = Mock()
    monkeypatch.setattr(addin_module, launcher_name, opened)
    data = json.dumps(payload)
    args = SimpleNamespace(action=action, data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    opened.assert_not_called()
    application.fireCustomEvent.assert_called_once_with(
        addin_module._DEFERRED_PALETTE_LAUNCH_EVENT_ID
    )
    assert json.loads(args.returnData) == {"ok": True}

    addin_module._DeferredPaletteLaunchHandler().notify(SimpleNamespace())

    opened.assert_called_once_with(application, data)


@pytest.mark.parametrize("relationship", ("main", "shielding"))
def test_connect_selector_launches_without_custom_event(
    addin_module: _PaletteLifecycleModule,
    relationship: str,
) -> None:
    """
    Open either connection selector without relying on Fusion's custom-event queue.
    """
    command_definition = SimpleNamespace(execute=Mock(return_value=True))
    application = SimpleNamespace(
        fireCustomEvent=Mock(return_value=False),
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda _identity: command_definition)
        ),
    )
    core_module = sys.modules["adsk.core"]
    vars(core_module)["Application"] = SimpleNamespace(get=lambda: application)
    vars(core_module)["HTMLEventArgs"] = SimpleNamespace(cast=lambda value: value)
    harness_id, connection_id, attachment_id = (UUID(int=number) for number in (1, 2, 3))
    data = json.dumps(
        {
            "harnessId": str(harness_id),
            "connectionId": str(connection_id),
            "attachmentId": str(attachment_id),
            "relationship": relationship,
        }
    )
    args = SimpleNamespace(action="connect_cable_end", data=data, returnData="")

    addin_module._PaletteIncomingHandler().notify(args)

    assert json.loads(args.returnData) == {"ok": True}
    application.fireCustomEvent.assert_not_called()
    command_definition.execute.assert_called_once_with()
    assert addin_module._runtime.pending_cable_end_attachment.consume() == (
        harness_id,
        connection_id,
        attachment_id,
        relationship,
    )
    assert addin_module._runtime.pending_native_dialog.value is None


def test_rejected_deferred_event_uses_direct_native_launcher(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep other native selectors usable when Fusion rejects the deferred event.
    """
    application = SimpleNamespace(fireCustomEvent=Mock(return_value=False))
    opened = Mock()
    monkeypatch.setattr(addin_module, "_open_add_junction_command", opened)

    addin_module._request_deferred_palette_launch(application, "add_junction", "{}")

    opened.assert_called_once_with(application, "{}")
    assert addin_module._runtime.pending_native_dialog.value is None
    application.fireCustomEvent.assert_called_once()


def test_rejected_event_clears_request_before_direct_launcher_failure(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Leave no stale selector request if the direct native command cannot open.
    """
    application = SimpleNamespace(fireCustomEvent=Mock(return_value=False))
    monkeypatch.setattr(
        addin_module,
        "_open_add_junction_command",
        Mock(side_effect=RuntimeError("selector unavailable")),
    )

    with pytest.raises(RuntimeError, match="selector unavailable"):
        addin_module._request_deferred_palette_launch(application, "add_junction", "{}")

    assert addin_module._runtime.pending_native_dialog.value is None
    application.fireCustomEvent.assert_called_once()
