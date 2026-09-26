"""
Exact linked-PCB discovery and temporary document ownership regressions.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from cable_bundler.application.board_contact_import import BoardPad
from cable_bundler.domain import InterfaceTargetKind


def _collection(*items: object) -> SimpleNamespace:
    """
    Mimic Fusion's indexed collection.
    """
    return SimpleNamespace(count=len(items), item=lambda index: items[index])


def test_linked_board_discovery_rejects_unrelated_and_unlinked_files(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Offer only 2D boards with a verified reverse reference to the selected 3D file.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_board_source")
    source = SimpleNamespace(id="selected-3d")
    linked = SimpleNamespace(
        name="Selected PCB",
        versionId="board-version",
        fileExtension="fbrd",
        childReferences=_collection(source),
    )
    unrelated = SimpleNamespace(
        name="Other PCB",
        versionId="other-version",
        fileExtension="fbrd",
        childReferences=_collection(SimpleNamespace(id="other-3d")),
    )
    source.parentReferences = _collection(linked, unrelated)
    occurrence = SimpleNamespace(
        isReferencedComponent=True,
        documentReference=SimpleNamespace(dataFile=source),
    )
    monkeypatch.setitem(vars(module), "resolve_interface_target", lambda *_: occurrence)
    interface = SimpleNamespace(targets=(SimpleNamespace(kind=InterfaceTargetKind.OCCURRENCE),))
    assert module.linked_interface_boards(object(), interface) == [
        module.LinkedBoard(linked, "Selected PCB", "board-version")
    ]
    source.parentReferences = _collection(unrelated)
    assert module.linked_interface_boards(object(), interface) == []


def test_active_imported_3d_board_uses_its_own_data_file(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Resolve an active F3D board even when its Interface occurrence is not external.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_board_source")
    source = SimpleNamespace(id="active-3d")
    linked = SimpleNamespace(
        name="Active PCB",
        versionId="pcb-version",
        fileExtension="fbrd",
        childReferences=_collection(source),
    )
    source.parentReferences = _collection(linked)
    occurrence = SimpleNamespace(isReferencedComponent=False, assemblyContext=None)
    monkeypatch.setitem(vars(module), "resolve_interface_target", lambda *_: occurrence)
    design = SimpleNamespace(parentDocument=SimpleNamespace(dataFile=source))
    interface = SimpleNamespace(targets=(SimpleNamespace(kind=InterfaceTargetKind.OCCURRENCE),))
    assert module.linked_interface_boards(design, interface) == [
        module.LinkedBoard(linked, "Active PCB", "pcb-version")
    ]


def test_temporary_linked_board_is_closed_after_pads_are_read(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Read the chosen document and restore the user's original active document.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_board_source")
    electron = ModuleType("adsk.electron")
    options = object()
    export_manager = SimpleNamespace(
        createEagleBrdExportOptions=Mock(return_value=options),
        execute=Mock(return_value=True),
    )
    board = SimpleNamespace(exportManager=export_manager)
    electron.Board = SimpleNamespace(cast=lambda product: product if product is board else None)
    electron.EcadDesign = SimpleNamespace(cast=lambda _product: None)
    monkeypatch.setitem(sys.modules, "adsk.electron", electron)
    monkeypatch.setitem(vars(sys.modules["adsk"]), "electron", electron)
    expected = [BoardPad("J1.1", 1, 2, 1, 1, 1)]
    reader = Mock(return_value=expected)
    monkeypatch.setitem(vars(module), "read_eagle_board", reader)
    original = SimpleNamespace(activate=Mock())
    linked_file = SimpleNamespace(versionId="pcb-version")
    document = SimpleNamespace(products=_collection(board), close=Mock(return_value=True))
    application = SimpleNamespace(activeDocument=original)

    def open_document(data_file: object, visible: bool) -> object:
        """
        Model Fusion activating a temporarily opened hidden board.
        """
        assert (data_file, visible) == (linked_file, False)
        application.activeDocument = document
        return document

    application.documents = SimpleNamespace(count=0, item=None, open=open_document)
    linked = module.LinkedBoard(linked_file, "Selected PCB", "pcb-version")
    assert module.read_linked_board_pads(application, linked) == expected
    export_path = reader.call_args.args[0]
    assert export_path.name == "linked.brd"
    export_manager.createEagleBrdExportOptions.assert_called_once_with(str(export_path))
    export_manager.execute.assert_called_once_with(options)
    assert not export_path.parent.exists()
    document.close.assert_called_once_with(False)
    original.activate.assert_called_once_with()


def test_failed_linked_export_closes_only_its_temporary_document(
    addin_module: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Refuse an incomplete PCB export without leaking the opened document.
    """
    module = importlib.import_module("cable_bundler.fusion.interface_board_source")
    electron = ModuleType("adsk.electron")
    board = SimpleNamespace(
        exportManager=SimpleNamespace(createEagleBrdExportOptions=Mock(return_value=None))
    )
    electron.Board = SimpleNamespace(cast=lambda product: product if product is board else None)
    electron.EcadDesign = SimpleNamespace(cast=lambda _product: None)
    monkeypatch.setitem(sys.modules, "adsk.electron", electron)
    monkeypatch.setitem(vars(sys.modules["adsk"]), "electron", electron)
    original = SimpleNamespace(activate=Mock())
    document = SimpleNamespace(products=_collection(board), close=Mock(return_value=True))
    linked_file = SimpleNamespace(versionId="pcb-version")
    application = SimpleNamespace(activeDocument=original)

    def open_document(_data_file: object, _visible: bool) -> object:
        """
        Model Fusion activating the temporary electronics document.
        """
        application.activeDocument = document
        return document

    application.documents = SimpleNamespace(count=0, item=None, open=open_document)
    linked = module.LinkedBoard(linked_file, "Selected PCB", "pcb-version")
    with pytest.raises(ValueError, match="could not export linked PCB"):
        module.read_linked_board_pads(application, linked)
    document.close.assert_called_once_with(False)
    original.activate.assert_called_once_with()
