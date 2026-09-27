"""
Focused regressions for Interface contact picking and diagram projection.
"""

from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from cable_bundler.application.interface_contact_rows import ContactSelectionMode
from cable_bundler.domain import AttachmentTargetKind


def test_contact_name_edit_routes_to_transactional_application_service(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Route the clicked contact identity and text through the normal edit command.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    rename = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "name_interface_contacts", rename)
    notice = edits._apply_palette_edit(
        object(),
        "set_interface_contact_name",
        json.dumps(
            {
                "harnessId": str(UUID(int=1)),
                "interfaceId": str(UUID(int=2)),
                "contactId": str(UUID(int=3)),
                "name": "J5.2",
            }
        ),
    )
    assert notice == "Interface contact name updated."
    rename.assert_called_once_with(UUID(int=1), UUID(int=2), {UUID(int=3): "J5.2"}, gateway)


def test_reviewed_pos_import_applies_names_and_blank_in_one_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Apply final autocomplete decisions without keeping PCB conflict metadata.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    rename = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "name_interface_contacts", rename)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactNames": [
            {"contactId": str(UUID(int=3)), "name": "J1.2"},
            {"contactId": str(UUID(int=4)), "name": ""},
        ],
    }
    notice = edits._apply_palette_edit(
        object(), "pos_import_interface_contacts", json.dumps(payload)
    )
    assert notice == "Applied 2 reviewed Interface contact names."
    rename.assert_called_once_with(
        UUID(int=1), UUID(int=2), {UUID(int=3): "J1.2", UUID(int=4): ""}, gateway
    )
    with pytest.raises(ValueError, match="duplicate or invalid"):
        edits._apply_palette_edit(
            object(),
            "pos_import_interface_contacts",
            json.dumps(
                {
                    **payload,
                    "contactNames": payload["contactNames"] * 2,
                }
            ),
        )


def test_pos_import_preview_reads_only_the_selected_linked_board(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep preview read-only and bind suggestions to the selected PCB version.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    harness_id, interface_id = UUID(int=1), UUID(int=2)
    interface = SimpleNamespace(interface_id=interface_id)
    boards = [SimpleNamespace(name="A", version_id="a"), SimpleNamespace(name="B", version_id="b")]
    read = Mock(return_value=[])
    preview = Mock(return_value={"autoNames": [], "unresolved": []})
    edit = Mock()
    monkeypatch.setitem(
        vars(palette_module),
        "_create_harness_gateway",
        lambda _: SimpleNamespace(read_harness_definition=lambda _id: "saved"),
    )
    monkeypatch.setitem(
        vars(palette_module), "loads", lambda _: SimpleNamespace(interfaces=(interface,))
    )
    monkeypatch.setitem(vars(palette_module), "_require_active_design", lambda _: object())
    monkeypatch.setitem(vars(palette_module), "linked_interface_boards", lambda *_: boards)
    monkeypatch.setitem(vars(palette_module), "read_linked_board_pads", read)
    monkeypatch.setitem(vars(palette_module), "preview_interface_contact_names", preview)
    monkeypatch.setitem(vars(palette_module), "_open_palette_edit", edit)
    result = json.loads(
        palette_module._dispatch_palette_action(
            object(),
            "preview_pos_import_interface_contacts",
            json.dumps(
                {
                    "harnessId": str(harness_id),
                    "interfaceId": str(interface_id),
                    "boardVersionId": "b",
                    "project": True,
                }
            ),
        )
    )
    assert result == {"ok": True, "autoNames": [], "unresolved": []}
    assert read.call_args.args[1] is boards[1]
    assert preview.call_args.args[-1] is True
    edit.assert_not_called()


def test_local_board_preview_returns_names_to_palette_without_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Send a picked file's preview through the palette before any edit command.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    harness_id, interface_id = UUID(int=1), UUID(int=2)
    send_html = Mock(return_value=True)
    palette = SimpleNamespace(sendInfoToHTML=send_html)
    application = SimpleNamespace(
        userInterface=SimpleNamespace(palettes=SimpleNamespace(itemById=lambda _id: palette))
    )
    preview = Mock(
        return_value={
            "autoNames": [{"contactId": "pad", "name": "J1.1 (GND)"}],
            "unresolved": [],
        }
    )
    monkeypatch.setitem(vars(palette_module), "preview_board_file_contact_names", preview)
    palette_module._send_board_file_preview(
        application,
        json.dumps(
            {"harnessId": str(harness_id), "interfaceId": str(interface_id), "project": True}
        ),
    )
    preview.assert_called_once_with(application, harness_id, interface_id, True)
    event, data = send_html.call_args.args
    assert event == "board_file_preview"
    assert json.loads(data) == {
        "harnessId": str(harness_id),
        "interfaceId": str(interface_id),
        "autoNames": [{"contactId": "pad", "name": "J1.1 (GND)"}],
        "unresolved": [],
    }


@pytest.mark.parametrize(
    "action",
    (
        "get_state",
        "get_interface_contact_signatures",
        "get_interface_contacts_cached",
        "get_interface_contacts",
        "get_interface_contact_cache_status",
        "rebuild_interface_contacts_cache",
    ),
)
def test_closing_document_drops_queued_contact_requests_without_error_log(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    """
    A palette callback can arrive after the design closes and before Untitled opens.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    application = SimpleNamespace(activeProduct=None)
    core = sys.modules["adsk.core"]
    fusion = sys.modules["adsk.fusion"]
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(vars(core), "HTMLEventArgs", SimpleNamespace(cast=lambda value: value))
    monkeypatch.setitem(vars(fusion), "Design", SimpleNamespace(cast=lambda _: None))
    gateway = Mock()
    failure = Mock()
    monkeypatch.setitem(vars(palette_module), "_create_harness_gateway", gateway)
    monkeypatch.setitem(vars(palette_module), "_report_failure", failure)
    args = SimpleNamespace(
        action=action,
        data=json.dumps(
            {
                "harnessId": str(UUID(int=1)),
                "interfaceId": str(UUID(int=2)),
                "contactDocumentScope": "closing-document",
            }
        ),
        returnData="",
    )

    palette_module._PaletteIncomingHandler().notify(args)

    assert json.loads(args.returnData) == {"ok": False, "stale": True}
    gateway.assert_not_called()
    failure.assert_not_called()


def test_late_contact_signature_request_cannot_read_replacement_document(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reject an old dialog's request even after Fusion activates another design.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    design = object()
    monkeypatch.setitem(
        vars(sys.modules["adsk.fusion"]), "Design", SimpleNamespace(cast=lambda _: design)
    )
    scope_module = importlib.import_module("cable_bundler.fusion.ui.palette_request_scope")
    monkeypatch.setitem(
        vars(scope_module), "_contact_palette_document_scope", lambda *_: "new-document"
    )
    gateway = Mock()
    monkeypatch.setitem(vars(palette_module), "_create_harness_gateway", gateway)
    result = json.loads(
        palette_module._dispatch_palette_action(
            SimpleNamespace(activeProduct=design),
            "get_interface_contact_signatures",
            json.dumps({"contactDocumentScope": "closed-document"}),
        )
    )

    assert result == {"ok": False, "stale": True}
    gateway.assert_not_called()


def test_closing_document_is_stale_even_while_its_product_proxy_remains(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Fusion may release the document before its active-product proxy disappears.
    """
    palette_module = importlib.import_module("cable_bundler.fusion.ui.palette")
    design = object()
    monkeypatch.setitem(
        vars(sys.modules["adsk.fusion"]), "Design", SimpleNamespace(cast=lambda _: design)
    )
    gateway = Mock()
    monkeypatch.setitem(vars(palette_module), "_create_harness_gateway", gateway)

    result = json.loads(
        palette_module._dispatch_palette_action(
            SimpleNamespace(activeDocument=None, activeProduct=design), "get_state", "{}"
        )
    )

    assert result == {"ok": False, "stale": True}
    gateway.assert_not_called()


def test_contact_details_edit_routes_value_and_pin_together(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Save both popup fields through one transactional application edit.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    update = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "set_interface_contact_details", update)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactId": str(UUID(int=3)),
        "value": "J5.2",
        "pin": "P7",
    }

    notice = edits._apply_palette_edit(
        object(), "set_interface_contact_details", json.dumps(payload)
    )

    assert notice == "Interface contact updated."
    update.assert_called_once_with(UUID(int=1), UUID(int=2), UUID(int=3), "J5.2", "P7", gateway)
    with pytest.raises(ValueError, match="value and pin must be text"):
        edits._apply_palette_edit(
            object(), "set_interface_contact_details", json.dumps({**payload, "pin": None})
        )


def test_auto_pin_routes_order_and_policy_without_value(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Pass the visible contact sequence to one transactional pin-only edit.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    gateway = object()
    update = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(edits), "auto_pin_interface_contacts", update)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactIds": [str(UUID(int=4)), str(UUID(int=3))],
        "start": 7,
        "overwrite": False,
    }
    notice = edits._apply_palette_edit(object(), "auto_pin_interface_contacts", json.dumps(payload))
    assert notice == "Interface contacts pinned."
    update.assert_called_once_with(
        UUID(int=1),
        UUID(int=2),
        (UUID(int=4), UUID(int=3)),
        7,
        False,
        gateway,
        hopscotch=True,
    )
    update.reset_mock()
    edits._apply_palette_edit(
        object(), "auto_pin_interface_contacts", json.dumps({**payload, "hopscotch": False})
    )
    update.assert_called_once_with(
        UUID(int=1),
        UUID(int=2),
        (UUID(int=4), UUID(int=3)),
        7,
        False,
        gateway,
        hopscotch=False,
    )
    assert "value" not in payload


def test_name_locals_routes_selected_contact_scope(
    addin_module: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Pass contact identities and field choices to the guarded naming edit.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    application = object()
    rename = Mock(return_value="Named 1 local geometry.")
    monkeypatch.setitem(vars(edits), "name_interface_contact_locals", rename)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactIds": [str(UUID(int=3))],
    }
    notice = edits._apply_palette_edit(
        application, "name_interface_contact_locals", json.dumps(payload)
    )
    assert notice == "Named 1 local geometry."
    rename.assert_called_once_with(
        application, UUID(int=1), UUID(int=2), (UUID(int=3),), True, True
    )
    rename.reset_mock()
    edits._apply_palette_edit(
        application,
        "name_interface_contact_locals",
        json.dumps({**payload, "includeValues": False, "includePins": True}),
    )
    rename.assert_called_once_with(
        application, UUID(int=1), UUID(int=2), (UUID(int=3),), False, True
    )


def test_geo_import_routes_selected_ids_as_one_metadata_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Pass an empty or selected scope to the live geometry-name importer.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    importer = Mock(return_value="Imported geometry Values for 1 of 1 Interface contacts.")
    monkeypatch.setitem(vars(edits), "import_interface_contact_geometry_names", importer)
    application = object()
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactIds": [str(UUID(int=3))],
    }
    notice = edits._apply_palette_edit(
        application, "geo_import_interface_contacts", json.dumps(payload)
    )
    assert notice == importer.return_value
    importer.assert_called_once_with(
        application, UUID(int=1), UUID(int=2), (UUID(int=3),), True, False
    )
    importer.reset_mock()
    edits._apply_palette_edit(
        application,
        "geo_import_interface_contacts",
        json.dumps({**payload, "importValues": False, "importPins": True}),
    )
    importer.assert_called_once_with(
        application, UUID(int=1), UUID(int=2), (UUID(int=3),), False, True
    )
    with pytest.raises(ValueError, match="contact IDs"):
        edits._apply_palette_edit(
            application,
            "geo_import_interface_contacts",
            json.dumps({**payload, "contactIds": None}),
        )


def test_projected_import_preserves_field_choices_through_picker_and_review(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep a Pins-only choice across the native picker and conflict resolution.
    """
    launchers = importlib.import_module("cable_bundler.fusion.ui.launchers")
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    definition = SimpleNamespace(execute=Mock(return_value=True))
    document = object()
    application = SimpleNamespace(
        activeDocument=document,
        userInterface=SimpleNamespace(
            commandDefinitions=SimpleNamespace(itemById=lambda _id: definition)
        ),
    )
    harness_id, interface_id, contact_id, source_id = (UUID(int=index) for index in range(1, 5))
    payload = {
        "harnessId": str(harness_id),
        "interfaceId": str(interface_id),
        "contactIds": [str(contact_id)],
        "copyValues": False,
        "copyPins": True,
    }
    launchers._open_select_source_interface_command(application, json.dumps(payload))
    assert launchers._runtime.pending_source_interface.consume() == (
        harness_id,
        interface_id,
        (contact_id,),
        False,
        True,
        document,
    )
    copy = Mock(return_value=("Copied 0 Values and 1 Pins.", ()))
    monkeypatch.setitem(vars(edits), "copy_projected_interface_details", copy)
    notice = edits._apply_palette_edit(
        application,
        "resolve_projected_interface_contacts",
        json.dumps(
            {
                **payload,
                "sourceId": str(source_id),
                "choices": [{"contactId": str(contact_id), "sourceContactId": str(UUID(int=5))}],
            }
        ),
    )
    assert notice == "Copied 0 Values and 1 Pins."
    copy.assert_called_once_with(
        application,
        harness_id,
        interface_id,
        source_id,
        (contact_id,),
        True,
        {contact_id: UUID(int=5)},
        copy_values=False,
    )


def test_contact_deletion_routes_selected_ids_as_one_edit(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Parse the selected identities before issuing one transactional removal.
    """
    edits = importlib.import_module("cable_bundler.fusion.ui.edits")
    topology_edits = importlib.import_module("cable_bundler.fusion.ui.topology_edits")
    gateway = object()
    remove = Mock()
    monkeypatch.setitem(vars(edits), "_create_harness_gateway", lambda _app: gateway)
    monkeypatch.setitem(vars(topology_edits), "remove_interface_contacts", remove)
    payload = {
        "harnessId": str(UUID(int=1)),
        "interfaceId": str(UUID(int=2)),
        "contactIds": [str(UUID(int=3)), str(UUID(int=4))],
    }
    notice = edits._apply_palette_edit(object(), "remove_interface_contacts", json.dumps(payload))
    assert notice == "Deleted selected Interface contacts."
    remove.assert_called_once_with(UUID(int=1), UUID(int=2), (UUID(int=3), UUID(int=4)), gateway)
    with pytest.raises(ValueError, match="selected contact IDs"):
        edits._apply_palette_edit(
            object(), "remove_interface_contacts", json.dumps({**payload, "contactIds": []})
        )
    assert remove.call_count == 1


def test_live_board_reader_uses_placed_signal_contacts(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Convert real ECAD units without applying element placement a second time.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_contact_naming")
    electron = ModuleType("adsk.electron")
    electron.Board = SimpleNamespace(cast=lambda product: product)
    monkeypatch.setitem(sys.modules, "adsk.electron", electron)
    monkeypatch.setitem(vars(sys.modules["adsk"]), "electron", electron)
    pad = SimpleNamespace(x=569920, y=13574720, diameter=438400, drill=326400)
    contact = SimpleNamespace(name="03", pad=pad)
    element = SimpleNamespace(name="J3", x=100, y=200, angle=270, mirror=True)
    reference = SimpleNamespace(element=element, contact=contact)
    smd_reference = SimpleNamespace(
        element=SimpleNamespace(name="U1"),
        contact=SimpleNamespace(
            name="1",
            pad=None,
            smd=SimpleNamespace(x=320000, y=640000, dx=160000, dy=320000, angle=90, layer=1),
        ),
    )
    malformed_reference = SimpleNamespace(contact=None)
    board = SimpleNamespace(
        signals=_collection(
            SimpleNamespace(
                name="P1.09", contactRefs=_collection(reference, smd_reference, malformed_reference)
            )
        )
    )
    application = SimpleNamespace(
        documents=_collection(SimpleNamespace(products=_collection(board)))
    )
    pads = module._live_board_pads(application)
    assert len(pads) == 2
    assert pads[0].label == "J3.03"
    assert pads[0].signal == "P1.09"
    assert (pads[0].x, pads[0].y, pads[0].layer) == pytest.approx((1.781, 42.421, 0))
    assert (pads[0].width, pads[0].height, pads[0].drill_diameter_mm) == pytest.approx(
        (1.37, 1.37, 1.02)
    )
    assert pads[1].label == "U1.1"
    assert (pads[1].x, pads[1].y, pads[1].width, pads[1].height) == pytest.approx((1, 2, 1, 0.5))
    board.signals = _collection(
        SimpleNamespace(name="GND", contactRefs=_collection(malformed_reference))
    )
    with pytest.raises(ValueError, match="no connected pad data"):
        module._live_board_pads(application)


def _collection(*items: object) -> SimpleNamespace:
    """
    Mimic a Fusion indexed collection.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def test_picker_accepts_multiple_connection_targets_across_occurrences(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep picker order without requiring a brittle owner/proxy match.
    """
    command = importlib.import_module("cable_bundler.fusion.ui.commands.interface_contacts")
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(
        vars(core), "SelectionCommandInput", SimpleNamespace(cast=lambda item: item)
    )
    face = SimpleNamespace(entityToken="face", kind=AttachmentTargetKind.FACE)
    edge = SimpleNamespace(entityToken="edge", kind=AttachmentTargetKind.CIRCULAR_EDGE)
    monkeypatch.setitem(vars(command), "attachment_target_kind", lambda entity: entity.kind)
    picker = SimpleNamespace(
        selectionCount=2,
        selection=lambda index: SimpleNamespace(entity=(face, edge)[index]),
    )
    inputs = SimpleNamespace(itemById=lambda _identifier: picker)
    contacts = command._selected_contacts(inputs)
    assert [contact.kind for contact in contacts] == [
        AttachmentTargetKind.FACE,
        AttachmentTargetKind.CIRCULAR_EDGE,
    ]
    assert [contact.entity_token for contact in contacts] == ["face", "edge"]


@pytest.mark.parametrize(
    "mode, limits",
    [
        (ContactSelectionMode.MANUAL, (1, 0)),
        (ContactSelectionMode.ROW, (2, 2)),
        (ContactSelectionMode.PLANE, (2, 2)),
    ],
)
def test_native_picker_uses_filters_without_a_preselect_veto(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
    mode: ContactSelectionMode,
    limits: tuple[int, int],
) -> None:
    """
    Let Fusion offer all supported targets without an owner-dependent callback.
    """
    command_module = importlib.import_module("cable_bundler.fusion.ui.commands.interface_contacts")
    application = object()
    core = sys.modules["adsk.core"]
    monkeypatch.setitem(vars(core), "Application", SimpleNamespace(get=lambda: application))
    monkeypatch.setitem(vars(command_module), "_require_active_design", lambda _app: object())
    monkeypatch.setitem(
        vars(command_module),
        "_create_harness_gateway",
        lambda _app: SimpleNamespace(read_harness_definition=lambda _id: "definition"),
    )
    interface_id = UUID(int=911)
    monkeypatch.setitem(
        vars(command_module),
        "loads",
        lambda _text: SimpleNamespace(interfaces=(SimpleNamespace(interface_id=interface_id),)),
    )
    filters: list[str] = []
    picker = SimpleNamespace(
        addSelectionFilter=lambda value: filters.append(value) or True,
        setSelectionLimits=Mock(return_value=True),
    )
    inputs = SimpleNamespace(addSelectionInput=Mock(return_value=picker))
    native_command = SimpleNamespace(
        commandInputs=inputs,
        preSelect=SimpleNamespace(add=Mock(return_value=True)),
        validateInputs=SimpleNamespace(add=Mock(return_value=True)),
        execute=SimpleNamespace(add=Mock(return_value=True)),
        destroy=SimpleNamespace(add=Mock(return_value=True)),
    )
    command_module._runtime.pending_interface_contacts.prepare((UUID(int=910), interface_id, mode))
    command_module.SelectInterfaceContactsCreatedHandler().notify(
        SimpleNamespace(command=native_command)
    )
    assert filters == list(command_module._FILTERS)
    picker.setSelectionLimits.assert_called_once_with(*limits)
    native_command.preSelect.add.assert_not_called()
    native_command.validateInputs.add.assert_called_once()
    native_command.execute.add.assert_called_once()
