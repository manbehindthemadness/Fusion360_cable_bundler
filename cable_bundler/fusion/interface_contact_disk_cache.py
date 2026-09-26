"""
Persist bounded contact projections only for an unchanged saved Fusion version.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence
from uuid import UUID

from ..domain import InterfaceContact

_CACHE_FORMAT = 1
_MAX_SNAPSHOT_BYTES = 8_000_000
_MAX_TOTAL_BYTES = 64_000_000


def _cache_root() -> Path:
    """
    Keep generated projections in an absolute per-user OS cache directory.
    """
    if sys.platform == "darwin":
        parent = Path.home() / "Library" / "Caches"
    elif os.name == "nt":
        configured = os.environ.get("LOCALAPPDATA", "")
        parent = Path(configured) if configured else Path.home() / "AppData" / "Local"
        if not parent.is_absolute():
            parent = Path.home() / "AppData" / "Local"
    else:
        # Placeholder for a future native Fusion client on Linux.
        configured = os.environ.get("XDG_CACHE_HOME", "")
        parent = Path(configured) if configured else Path.home() / ".cache"
        if not parent.is_absolute():
            parent = Path.home() / ".cache"
    return parent / "Fusion360_cable_bundler" / "contact_outlines_v1"


def _snapshot_path(
    application: Any,
    harness_id: UUID,
    interface_id: UUID,
    *,
    require_clean: bool = True,
) -> Path | None:
    """
    Scope disk data to a cloud file version, not a copied document creation ID.
    """
    if sys.platform.startswith("linux"):
        return None  # No native Fusion client currently supports this cache path.
    try:
        document = application.activeDocument
        if document is None or (require_clean and document.isModified):
            return None
        data_file = document.dataFile
        identity = data_file.id
        version = data_file.versionNumber
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    if not isinstance(identity, str) or not identity or isinstance(version, bool):
        return None
    if not isinstance(version, int) or version < 1:
        return None
    scope = json.dumps(
        [identity, version, str(harness_id), str(interface_id), _CACHE_FORMAT],
        separators=(",", ":"),
    )
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    return _cache_root() / f"contact-{digest}.json"


def disk_cache_available(application: Any, harness_id: UUID, interface_id: UUID) -> bool:
    """
    Report whether the current saved document can safely use a disk snapshot.
    """
    return _snapshot_path(application, harness_id, interface_id) is not None


def clear_interface_contact_snapshot(
    application: Any, harness_id: UUID, interface_id: UUID
) -> bool:
    """
    Delete only the current Interface's own versioned cache file.

    Return false when disk caching is unavailable. Propagate I/O failures so
    rebuild cannot silently serve a stale snapshot.
    """
    path = _snapshot_path(application, harness_id, interface_id, require_clean=False)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True


def _read_snapshot(path: Path | None) -> dict[str, object]:
    """
    Reject oversized, corrupt, or obsolete cache files without failing the picker.
    """
    if path is None:
        return {}
    try:
        if path.stat().st_size > _MAX_SNAPSHOT_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("format") != _CACHE_FORMAT:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def _valid_projection(value: object, contact: InterfaceContact) -> bool:
    """
    Accept only bounded finite outlines belonging to the requested contact.
    """
    if not isinstance(value, dict) or value.get("contactId") != str(contact.contact_id):
        return False
    if value.get("kind") != contact.kind.value or value.get("linked") is not True:
        return False
    loops = value.get("loops")
    if not isinstance(loops, list) or len(loops) > 128 or not loops:
        return False
    point_count = 0
    for loop in loops:
        if not isinstance(loop, list) or not loop or len(loop) > 8192:
            return False
        point_count += len(loop)
        if point_count > 32768:
            return False
        for point in loop:
            if (
                not isinstance(point, list)
                or len(point) != 3
                or any(
                    isinstance(coordinate, bool)
                    or not isinstance(coordinate, (int, float))
                    or not math.isfinite(coordinate)
                    for coordinate in point
                )
            ):
                return False
    normal = value.get("normal")
    axes = value.get("parentAxes")
    vectors = [normal] if axes is None else [normal, *axes] if isinstance(axes, list) else []
    return bool(vectors) and all(
        isinstance(vector, list)
        and len(vector) == 3
        and all(
            not isinstance(number, bool)
            and isinstance(number, (int, float))
            and math.isfinite(number)
            for number in vector
        )
        for vector in vectors
    )


def _prune_snapshots(root: Path) -> None:
    """
    Bound disk use by evicting the oldest files owned by this cache format.
    """
    try:
        snapshots = sorted(
            (
                (path.stat().st_mtime, path.stat().st_size, path)
                for path in root.glob("contact-*.json")
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda item: item[0],
        )
        total = sum(size for _time, size, _path in snapshots)
        for _time, size, path in snapshots:
            if total <= _MAX_TOTAL_BYTES:
                break
            path.unlink()
            total -= size
    except OSError:
        return


def _write_snapshot(path: Path, entries: dict[str, object]) -> None:
    """
    Atomically replace one small snapshot and leave no partial JSON on failure.
    """
    try:
        encoded = json.dumps(
            {"format": _CACHE_FORMAT, "entries": entries}, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError):
        return
    if len(encoded) > _MAX_SNAPSHOT_BYTES:
        return
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="contact-", delete=False) as file:
            temporary = Path(file.name)
            file.write(encoded)
        os.replace(temporary, path)
        _prune_snapshots(path.parent)
    except OSError:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def project_cached_contact_batch(
    application: Any,
    design: Any,
    harness_id: UUID,
    interface_id: UUID,
    contacts: Sequence[InterfaceContact],
    projector: Callable[[Any, InterfaceContact], dict[str, object]],
) -> list[dict[str, object]]:
    """
    Reuse versioned disk outlines; project and persist only eligible misses.

    Unsaved or modified designs bypass disk entirely. Names are always merged from
    current harness data, while Fusion references and SVG nodes remain memory-only.
    """
    path = _snapshot_path(application, harness_id, interface_id)
    entries = _read_snapshot(path)
    changed = False
    projections: list[dict[str, object]] = []
    for contact in contacts:
        key = str(contact.contact_id)
        record = entries.get(key)
        payload = None
        if isinstance(record, dict) and record.get("token") == contact.entity_token:
            candidate = record.get("projection")
            if _valid_projection(candidate, contact):
                payload = dict(candidate)
                payload["assignedName"] = contact.name
                source_name = payload.get("sourceName")
                payload["name"] = contact.name or (
                    source_name if isinstance(source_name, str) else contact.kind.value
                )
        if payload is None:
            payload = projector(design, contact)
            if path is not None and _valid_projection(payload, contact):
                stable = dict(payload)
                source_name = stable.get("sourceName")
                stable["name"] = source_name if isinstance(source_name, str) else contact.kind.value
                stable.pop("assignedName", None)
                entries[key] = {"token": contact.entity_token, "projection": stable}
                changed = True
        projections.append(payload)
    if path is not None and changed:
        _write_snapshot(path, entries)
    return projections
