"""
Retain bounded, readable build-stage evidence across the controller, worker and native host.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append(directory: Path, stage: str, message: str) -> dict[str, str]:
    """
    Append one flushed UTC event to an owned job without copying numerical trial geometry.
    """
    entry = {
        "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        "stage": stage,
        "message": message[:2000],
    }
    with (directory / "build-progress.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, allow_nan=False) + "\n")
    return entry


def tail(path: Path, maximum_bytes: int = 65536) -> str:
    """
    Read only a bounded file suffix, tolerating absent files and partial UTF-8 writes.
    """
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - maximum_bytes))
            return stream.read(maximum_bytes).decode("utf-8", errors="replace")
    except OSError:
        return ""


def read(directory: Path | None) -> list[dict[str, str]]:
    """
    Return at most100complete stage events; incomplete or malformed lines do not break polling.
    """
    if directory is None:
        return []
    entries: list[dict[str, str]] = []
    for line in tail(directory / "build-progress.jsonl").splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and all(
            isinstance(value.get(key), str) for key in ("time", "stage", "message")
        ):
            entries.append({key: value[key] for key in ("time", "stage", "message")})
    return entries[-100:]
