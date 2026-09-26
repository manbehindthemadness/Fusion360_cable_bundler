"""
Compare live connected-pad reading with complete Eagle-board export.

Run in Fusion's active electronics test board through an MCP script. Only a
temporary local .brd file is created; the active design is not changed.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

# noinspection PyUnresolvedReferences
import adsk.core

# noinspection PyUnresolvedReferences
import adsk.electron

from cable_bundler.application.board_contact_import import read_eagle_board
from cable_bundler.fusion.interface_contact_naming import _board_pads


def run(_context: str) -> None:
    """
    Verify the active board exports J4.13–19 and report both read times.
    """
    application = adsk.core.Application.get()
    board = adsk.electron.Board.cast(application.activeProduct)
    if board is None:
        design = adsk.electron.EcadDesign.cast(application.activeProduct)
        board = design.board if design is not None else None
    if board is None:
        raise ValueError("Open the hardware_ble_test electronics board before this probe.")

    started = perf_counter()
    connected = _board_pads(board)
    connected_seconds = perf_counter() - started

    with TemporaryDirectory(prefix="cable-bundler-pad-qa-") as directory:
        path = Path(directory) / "linked.brd"
        manager = board.exportManager
        options = manager.createEagleBrdExportOptions(str(path))
        if options is None:
            raise ValueError("Fusion did not create Eagle board export options.")
        started = perf_counter()
        if not manager.execute(options):
            raise ValueError("Fusion did not export the active electronics board.")
        export_seconds = perf_counter() - started
        started = perf_counter()
        all_pads = read_eagle_board(path)
        parse_seconds = perf_counter() - started

    missing = {f"J4.{pin}" for pin in range(13, 20)} - {
        pad.label for pad in all_pads if not pad.signal
    }
    if missing:
        raise AssertionError(f"Unconnected J4 pads were not exported: {sorted(missing)}")
    exported_by_label = {pad.label: pad for pad in all_pads}
    divergent = [
        pad.label
        for pad in connected
        if (other := exported_by_label.get(pad.label)) is None
        or abs(pad.x - other.x) > 0.1
        or abs(pad.y - other.y) > 0.1
        or pad.layer != other.layer
        or pad.signal != other.signal
    ]
    if divergent:
        raise AssertionError(f"Existing connected pad positions changed: {divergent[:10]}")
    print(
        f"connected={len(connected)} ({connected_seconds:.3f}s); "
        f"complete={len(all_pads)} (export {export_seconds:.3f}s, "
        f"parse {parse_seconds:.3f}s); J4.13–19=NC; "
        f"{len(connected)} connected positions and signals agree"
    )
