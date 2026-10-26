"""
Detect changed-on-disk analysis modules before reusing a cached Fusion runtime.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_loaded: dict[Path, str] = {}


def mark_loaded(filename: str) -> None:
    """
    Record a module's source digest when its definitions finish loading.
    """
    path = Path(filename).resolve()
    _loaded[path] = hashlib.sha256(path.read_bytes()).hexdigest()


def verify_loaded() -> None:
    """
    Refuse mixed stale code rather than silently reloading live analysis ledgers.
    """
    for path, digest in _loaded.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(
                f"Stale ribbon analysis module:{path.name};preserve existing evidence before refreshing its runtime."
            )


def source_fingerprints() -> dict[str, str]:
    """
    Return repository-relative core-source fingerprints for a fresh run plan.
    """
    verify_loaded()
    directory = Path(__file__).parent
    root = directory.parents[1]
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.glob("*.py"))
    }


mark_loaded(__file__)
