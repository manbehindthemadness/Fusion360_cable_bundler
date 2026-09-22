"""
Fusion palette regressions for connection-count geometry updates.
"""

from __future__ import annotations

from cable_bundler.domain import HarnessDefinition
from tests.fusion_ui_support import (
    UUID,
    Mock,
    SimpleNamespace,
    _PaletteLifecycleModule,
    dumps,
    json,
    pytest,
    sys,
)


@pytest.mark.parametrize(
    ("action", "notice"),
    (
        ("add_cable_end_connection", "Added connection."),
        ("remove_cable_end_attachment", "Detached cable end."),
    ),
)
def test_connection_count_edit_rebuilds_affected_generated_geometry(
    addin_module: _PaletteLifecycleModule,
    monkeypatch: pytest.MonkeyPatch,
    valid_harness: HarnessDefinition,
    action: str,
    notice: str,
) -> None:
    """
    Rebuild persisted branch solids when the number of end connections changes.
    """
    document = object()
    harness_id = UUID(int=1)
    connection_id = UUID(int=2)
    design = object()
    component = object()
    gateway = SimpleNamespace(
        read_harness_definition=Mock(return_value=dumps(valid_harness)),
        harness_component=Mock(return_value=component),
    )
    application = SimpleNamespace(activeDocument=document, activeViewport=Mock())
    core_module = sys.modules["adsk.core"]
    core_module.Application = SimpleNamespace(get=lambda: application)  # type: ignore[attr-defined]
    applied = Mock(return_value=notice)
    refreshed_geometry = Mock(return_value=1)
    refreshed_preview = Mock(return_value="")
    reconciled = Mock()
    sent = Mock()
    monkeypatch.setattr(addin_module, "_apply_palette_edit", applied)
    monkeypatch.setattr(addin_module, "_create_harness_gateway", lambda _application: gateway)
    monkeypatch.setattr(addin_module, "_require_active_design", lambda _application: design)
    monkeypatch.setattr(
        addin_module,
        "refresh_generated_cable_groups_for_connection",
        refreshed_geometry,
    )
    monkeypatch.setattr(addin_module, "reconcile_active_refines", reconciled)
    monkeypatch.setattr(addin_module, "_refresh_active_preview", refreshed_preview)
    monkeypatch.setattr(addin_module, "_send_palette_state", sent)
    payload = json.dumps(
        {
            "harnessId": str(harness_id),
            "connectionId": str(connection_id),
            "attachmentId": str(UUID(int=3)),
        }
    )
    args = SimpleNamespace(executeFailed=False, executeFailedMessage="")

    addin_module._PaletteEditExecuteHandler((action, payload, document)).notify(args)

    refreshed_geometry.assert_called_once_with(
        design,
        component,
        valid_harness,
        connection_id,
    )
    refreshed_preview.assert_called_once_with(application, harness_id, ensure_visible=False)
    if action == "remove_cable_end_attachment":
        reconciled.assert_called_once_with(application)
    else:
        reconciled.assert_not_called()
    sent.assert_called_once_with(application, f"{notice} Updated 1 generated cable group.")
    assert not args.executeFailed
