"""
Resolve and read the 2D PCB linked to an Interface's selected 3D occurrence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ..application.board_contact_import import BoardPad, read_eagle_board
from ..domain import InterfaceDefinition, InterfaceTargetKind
from .interface_contact_naming import _items
from .interface_targets import resolve_interface_target


@dataclass(frozen=True)
class LinkedBoard:
    """
    Identify one 2D PCB that directly references the selected 3D PCB version.
    """

    data_file: Any
    name: str
    version_id: str


def linked_interface_boards(design: Any, interface: InterfaceDefinition) -> list[LinkedBoard]:
    """
    Find exact reverse references without searching unrelated open documents.

    An imported 3D-only design may have no cloud reference. In that case the
    caller can offer the explicit board-file fallback instead of guessing.
    """
    if (
        len(interface.targets) != 1
        or interface.targets[0].kind is not InterfaceTargetKind.OCCURRENCE
    ):
        raise ValueError("Pos Import requires one Interface board occurrence.")
    occurrence = resolve_interface_target(design, interface.targets[0])
    if occurrence is None:
        raise ValueError("The Interface board occurrence is unavailable.")
    source_file = None
    current = occurrence
    for _depth in range(8):
        if current is None:
            break
        try:
            if current.isReferencedComponent:
                reference = current.documentReference
                source_file = getattr(reference, "dataFile", None)
                if source_file is not None:
                    break
        except (AttributeError, RuntimeError, TypeError):
            pass
        current = getattr(current, "assemblyContext", None)
    if source_file is None:
        source_file = getattr(getattr(design, "parentDocument", None), "dataFile", None)
    if source_file is None:
        return []
    source_id = getattr(source_file, "id", None)
    if not isinstance(source_id, str) or not source_id:
        return []
    boards: dict[str, LinkedBoard] = {}
    for candidate in _items(getattr(source_file, "parentReferences", None)):
        extension = getattr(candidate, "fileExtension", "")
        if not isinstance(extension, str) or extension.lower().lstrip(".") != "fbrd":
            continue
        children = _items(getattr(candidate, "childReferences", None))
        if not any(getattr(child, "id", None) == source_id for child in children):
            continue
        version_id = getattr(candidate, "versionId", None)
        name = getattr(candidate, "name", None)
        if isinstance(version_id, str) and version_id and isinstance(name, str) and name:
            boards[version_id] = LinkedBoard(candidate, name, version_id)
    return sorted(boards.values(), key=lambda board: (board.name, board.version_id))


def read_linked_board_pads(application: Any, linked_board: LinkedBoard) -> list[BoardPad]:
    """
    Export one linked board for all placed pads, then close only our document.

    Signal contact references omit unconnected pads. A temporary Eagle export
    includes those pads and their nominal sizes without changing the PCB.
    """
    try:
        import adsk.electron  # type: ignore[import-not-found]
    except ImportError as error:
        raise ValueError("Live electronics data is unavailable in this Fusion build.") from error
    document = next(
        (
            item
            for item in _items(application.documents)
            if getattr(getattr(item, "dataFile", None), "versionId", None)
            == linked_board.version_id
        ),
        None,
    )
    opened_here = document is None
    active_document = application.activeDocument
    if document is None:
        document = application.documents.open(linked_board.data_file, False)
    if document is None:
        raise ValueError(f"Fusion could not open linked PCB {linked_board.name!r}.")
    try:
        boards = []
        for product in _items(document.products):
            board = adsk.electron.Board.cast(product)
            if board is None:
                design = adsk.electron.EcadDesign.cast(product)
                board = getattr(design, "board", None) if design is not None else None
            if board is not None:
                boards.append(board)
        if len(boards) != 1:
            raise ValueError(f"Linked file {linked_board.name!r} does not expose one 2D PCB.")
        export_manager = boards[0].exportManager
        with TemporaryDirectory(prefix="cable-bundler-pcb-") as directory:
            path = Path(directory) / "linked.brd"
            options = export_manager.createEagleBrdExportOptions(str(path))
            if options is None or not export_manager.execute(options):
                raise ValueError(f"Fusion could not export linked PCB {linked_board.name!r}.")
            pads = read_eagle_board(path)
        if not pads:
            raise ValueError(f"Linked PCB {linked_board.name!r} has no usable contacts.")
    finally:
        if opened_here:
            if not document.close(False):
                raise RuntimeError(f"Fusion could not close temporary PCB {linked_board.name!r}.")
            if application.activeDocument != active_document:
                active_document.activate()
    return pads
