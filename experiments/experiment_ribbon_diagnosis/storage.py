"""
Archive diagnostic geometry before releasing its owned scratch document.
"""

from __future__ import annotations

from pathlib import Path

# noinspection PyUnresolvedReferences
import adsk.fusion


def archive(design: adsk.fusion.Design, path: Path) -> None:
    """
    Require a new, nonempty native archive; leave the document open on failure.
    """
    if path.exists():
        raise FileExistsError(path)
    manager = design.exportManager
    options = manager.createFusionArchiveExportOptions(str(path), design.rootComponent)
    if options is None or not manager.execute(options):
        raise RuntimeError("Diagnostic archive export failed; document retained.")
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Diagnostic archive is missing or empty; document retained.")


def archive_and_close(document: adsk.fusion.FusionDocument, path: Path) -> None:
    """
    Close an explicitly owned scratch only after verifying its native archive.
    """
    archive(document.design, path)
    if not document.close(False):
        raise RuntimeError("Archived diagnostic document could not be closed.")
