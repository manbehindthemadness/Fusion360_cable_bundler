"""
Restore deliberately hidden experiment sources without discarding new import files.
"""

from __future__ import annotations

from pathlib import Path


def restore_offline_directory(folder: Path, offline: Path) -> None:
    """
    Restore original sources, preserving a directory recreated during an import.

    Existing recovery siblings are never overwritten. Missing retained sources or
    exhausted recovery names raise before moving the current directory.
    """
    if not offline.is_dir():
        raise RuntimeError("Retained source directory is missing")
    if folder.exists():
        for index in range(100):
            retained = folder.with_name(f"{folder.name}-import-created-{index}")
            if not retained.exists():
                folder.rename(retained)
                break
        else:
            raise RuntimeError("No unused import recovery directory name")
    offline.rename(folder)
