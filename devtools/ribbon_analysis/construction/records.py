"""
Validate solver-independent feature lineage, display geometry and append-only trace records.
"""

from __future__ import annotations

import json
import math
from typing import Any

SCHEMA = "ribbon-construction-v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_STEPS = 512
MAX_POINTS = 300000
PHASES = {
    "input",
    "preplot",
    "primitive",
    "placement",
    "bend",
    "proposal",
    "correction",
    "audit",
    "output",
}
BASES = {"observed", "reconstructed", "unavailable"}
STATUSES = {"reference", "attempted", "accepted", "rejected", "unresolved", "unavailable", "error"}


def canonical(value: Any) -> str:
    """
    Freeze JSON-compatible finite data without retaining caller-owned mutable values.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def text(value: Any) -> str:
    """
    Reject missing, blank and excessive external labels before display or indexing.
    """
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Trace labels must contain1..4096characters")
    return value


def point(value: Any) -> None:
    """
    Require three finite millimeter coordinates, excluding booleans.
    """
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 3
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
    ):
        raise ValueError("Trace points require three finite numbers")


def feature(value: dict[str, Any], known: dict[str, Any]) -> None:
    """
    Require explicit prior parents, source attribution and unique stable feature identity.
    """
    if set(value) != {"id", "label", "kind", "parents", "source"}:
        raise ValueError("Malformed feature definition")
    for name in ("id", "label", "kind", "source"):
        text(value[name])
    if value["id"] in known or not isinstance(value["parents"], (tuple, list)):
        raise ValueError("Duplicate feature identity or malformed parents")
    if any(not isinstance(parent, str) or parent not in known for parent in value["parents"]):
        raise ValueError("Feature parents must already exist; lineage cycles are forbidden")


def objects(values: Any, known: dict[str, Any]) -> int:
    """
    Validate sampled polylines, explicit local/world space, frames and material intervals.
    """
    if not isinstance(values, (list, tuple)) or len(values) > 256:
        raise ValueError("A stage allows at most256display objects")
    total = 0
    ids: set[str] = set()
    for item in values:
        if not isinstance(item, dict) or set(item) != {
            "feature",
            "space",
            "paths",
            "frame",
            "material_mm",
            "details",
        }:
            raise ValueError("Malformed trace display object")
        identity = item["feature"]
        if not isinstance(identity, str) or identity not in known or identity in ids:
            raise ValueError("Unknown or duplicated stage feature")
        ids.add(identity)
        if item["space"] not in ("local", "world"):
            raise ValueError("Declare local or world geometry explicitly")
        paths = item["paths"]
        if not isinstance(paths, (list, tuple)) or len(paths) > 64:
            raise ValueError("A feature allows at most64sampled polylines")
        for path in paths:
            if not isinstance(path, (list, tuple)) or not 2 <= len(path) <= 2049:
                raise ValueError("Display paths require2..2049points")
            for vertex in path:
                point(vertex)
            total += len(path)
        frame = item["frame"]
        if frame is not None:
            if not isinstance(frame, dict) or set(frame) != {"origin", "forward", "across"}:
                raise ValueError("Malformed local material frame")
            for vector in frame.values():
                point(vector)
            forward, across = frame["forward"], frame["across"]
            if (
                any(abs(sum(v * v for v in axis) - 1) > 1e-7 for axis in (forward, across))
                or abs(sum(a * b for a, b in zip(forward, across))) > 1e-7
            ):
                raise ValueError("Display frame must be orthonormal; no frame repair is performed")
        interval = item["material_mm"]
        if interval is not None and (
            not isinstance(interval, (list, tuple))
            or len(interval) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in interval)
            or not 0 <= interval[0] < interval[1]
        ):
            raise ValueError("Material intervals must advance in millimeters")
        if not isinstance(item["details"], dict):
            raise ValueError("Object details must be an explicit JSON object")
    return total
