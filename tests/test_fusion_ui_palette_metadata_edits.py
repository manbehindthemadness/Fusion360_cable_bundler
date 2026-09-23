"""
Focused Fusion UI regressions for palette.
"""

from __future__ import annotations

from tests.fusion_ui_support import (
    UUID,
    Mock,
    PathwayEndpoint,
    SimpleNamespace,
    _PaletteLifecycleModule,
    cast,
    json,
    pytest,
    sys,
)


def _mock_palette_service(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
) -> tuple[object, Mock]:
    """
    Install one named palette service with a shared synthetic gateway.
    """
    gateway = object()
    service = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, service_name, service)
    return gateway, service


def test_palette_edit_saves_pathway_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse pathway key/value rows independently of routing controls.
    """
    harness_id = UUID(int=1)
    pathway_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_pathway_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_pathway_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "pathwayId": str(pathway_id),
                "metadata": [{"key": "zone", "value": "forward"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        pathway_id,
        (("zone", "forward"),),
        gateway,
    )
    assert notice == "Saved pathway properties."


def test_palette_edit_saves_pathway_end_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the selected boundary and its key/value rows without changing routing.
    """
    harness_id = UUID(int=1)
    pathway_id = UUID(int=2)
    gateway = object()
    save = Mock()
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "set_pathway_end_properties", save)

    notice = addin_module._apply_palette_edit(
        object(),
        "set_pathway_end_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "pathwayId": str(pathway_id),
                "endpoint": "end",
                "metadata": [{"key": "station", "value": "right"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        pathway_id,
        PathwayEndpoint.END,
        (("station", "right"),),
        gateway,
    )
    assert notice == "Saved pathway-end properties."


@pytest.mark.parametrize(
    ("action", "identity_key", "service_name", "notice"),
    (
        (
            "set_junction_properties",
            "junctionId",
            "set_junction_properties",
            "Saved junction properties.",
        ),
        (
            "set_cable_end_properties",
            "connectionId",
            "set_cable_end_properties",
            "Saved cable-end properties.",
        ),
    ),
)
def test_palette_edit_saves_identity_owned_metadata(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    identity_key: str,
    service_name: str,
    notice: str,
) -> None:
    """
    Parse identity-owned metadata through its dedicated edit service.
    """
    harness_id = UUID(int=1)
    identity = UUID(int=2)
    gateway, save = _mock_palette_service(addin_module, monkeypatch, service_name)

    result = addin_module._apply_palette_edit(
        object(),
        action,
        json.dumps(
            {
                "harnessId": str(harness_id),
                identity_key: str(identity),
                "metadata": [{"key": "location", "value": "P2"}],
            }
        ),
    )

    save.assert_called_once_with(harness_id, identity, (("location", "P2"),), gateway)
    assert result == notice


def test_palette_edit_saves_connection_properties(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse branch construction overrides and metadata through one atomic edit.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    gateway, save = _mock_palette_service(
        addin_module, monkeypatch, "set_cable_end_attachment_properties"
    )

    result = addin_module._apply_palette_edit(
        object(),
        "set_cable_end_attachment_properties",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "attachmentId": str(attachment_id),
                "diameterMm": 0.6,
                "conductorDiameterMm": 0.45,
                "insulationMaterial": "ETFE",
                "conductorMaterial": None,
                "shielding": "",
                "dielectricMaterial": None,
                "manufacturer": "Branch maker",
                "partNumber": "BR-01",
                "metadata": [{"key": "location", "value": "P2"}],
            }
        ),
    )

    save.assert_called_once_with(
        harness_id,
        connection_id,
        attachment_id,
        (("location", "P2"),),
        gateway,
        diameter_mm=0.6,
        conductor_diameter_mm=0.45,
        insulation_material="ETFE",
        conductor_material=None,
        shielding="",
        dielectric_material=None,
        manufacturer="Branch maker",
        part_number="BR-01",
    )
    assert result == "Saved cable-end connection properties."


def test_palette_edit_saves_connection_shielding_override(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Preserve an explicit empty shielding value as an inheritance interruption.
    """
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    attachment_id = UUID(int=3)
    gateway, save = _mock_palette_service(
        addin_module, monkeypatch, "set_cable_end_attachment_shielding"
    )

    result = addin_module._apply_palette_edit(
        object(),
        "set_cable_end_attachment_shielding",
        json.dumps(
            {
                "harnessId": str(harness_id),
                "connectionId": str(connection_id),
                "attachmentId": str(attachment_id),
                "shielding": "",
                "dielectricMaterial": None,
            }
        ),
    )

    save.assert_called_once_with(harness_id, connection_id, attachment_id, "", None, (), gateway)
    assert result == "Saved cable-end connection shielding."


@pytest.mark.parametrize("action", ["rename_pathway", "set_interpolation"])
def test_palette_edit_waits_for_execute_and_releases_handlers(
    addin_module: _PaletteLifecycleModule, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    """
    Queue without changing data, then group persistence and preview in execute.
    """
    document = object()
    definition = Mock(execute=Mock(return_value=True))
    application = SimpleNamespace(
        activeDocument=document,
        activeViewport=Mock(),
        userInterface=SimpleNamespace(
            commandDefinitions=Mock(itemById=Mock(return_value=definition))
        ),
    )
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Renamed cable.")
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(UUID(int=1))})
    addin_module._open_palette_edit(application, action, payload)
    applied.assert_not_called()
    handlers: list[object] = []
    cleanup: list[object] = []
    command = SimpleNamespace(
        execute=Mock(add=Mock(side_effect=lambda handler: handlers.append(handler) or True)),
        destroy=Mock(add=Mock(side_effect=lambda handler: cleanup.append(handler) or True)),
    )
    addin_module._PaletteEditCreatedHandler().notify(SimpleNamespace(command=command))
    applied.assert_not_called()
    args = SimpleNamespace(executeFailed=False)
    cast(Mock, handlers[0]).notify(args)
    applied.assert_called_once_with(application, action, payload)
    refreshed.assert_called_once_with(application, UUID(int=1), ensure_visible=False)
    assert not args.executeFailed
    cast(Mock, cleanup[0]).notify(SimpleNamespace())
    assert handlers[0] not in addin_module._runtime.handlers
    assert cleanup[0] not in addin_module._runtime.handlers


# noinspection DuplicatedCode
def test_pathway_deletion_runs_in_one_native_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reconcile deleted refine graphics before the native deletion command commits.
    """
    document = object()
    harness_id = UUID(int=1)
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Deleted pathway branch.")
    reconciled = Mock()
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "reconcile_active_refines", reconciled)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id), "pathwayId": str(UUID(int=2))})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(("remove_pathway", payload, document)).notify(args)

    applied.assert_called_once_with(application, "remove_pathway", payload)
    reconciled.assert_called_once_with(application)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=False)
    application.activeViewport.refresh.assert_called_once_with()
    sent.assert_called_once_with(application, "Deleted pathway branch.")
    assert not args.executeFailed


# noinspection DuplicatedCode
def test_junction_deletion_runs_in_one_native_transaction(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Reconcile deleted refine graphics before the native junction deletion commits.
    """
    document = object()
    harness_id = UUID(int=1)
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value="Deleted junction.")
    reconciled = Mock()
    refreshed = Mock(return_value="")
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "reconcile_active_refines", reconciled)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps({"harnessId": str(harness_id), "junctionId": str(UUID(int=2))})
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler(("remove_junction", payload, document)).notify(args)

    applied.assert_called_once_with(application, "remove_junction", payload)
    reconciled.assert_called_once_with(application)
    refreshed.assert_called_once_with(application, harness_id, ensure_visible=False)
    application.activeViewport.refresh.assert_called_once_with()
    sent.assert_called_once_with(application, "Deleted junction.")
    assert not args.executeFailed
