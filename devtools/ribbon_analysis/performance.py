"""
Expose recorded layout-specific timings without running work or counting optional appearance costs.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contracts import Targets
from .inspection.archive import canonical

_KEYS = {
    "plan.json": ("targets", "gym", "settings"),
    "numerical-result.json": (
        "elapsed_seconds",
        "cpu_seconds",
        "first_pass_seconds",
        "smoothing_seconds",
        "material_uv_seconds",
        "status",
        "contact_warning",
    ),
    "native-result.json": (
        "generation_seconds",
        "audit_seconds",
        "material_uv_seconds",
        "status",
    ),
}


@lru_cache(maxsize=24)
def _load(path: Path, modified: int, size: int) -> dict[str, Any]:
    """
    Cache only counter fields, keyed by file revision, tolerating incomplete in-flight writes.
    """
    del modified, size
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {key: payload.get(key) for key in _KEYS[path.name]}


def _document(path: Path) -> dict[str, Any]:
    """
    Read a bounded owned job record; absent/malformed counters remain unmeasured.
    """
    try:
        stat = path.stat()
    except OSError:
        return {}
    if stat.st_size > 16 * 1024 * 1024:
        return {}
    return _load(path, stat.st_mtime_ns, stat.st_size)


def _seconds(payload: dict[str, Any], key: str) -> float | None:
    """
    Reject missing, negative, boolean or nonfinite timings rather than displaying zero.
    """
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        seconds = float(value)
    except OverflowError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _contact_warning(payload: dict[str, Any]) -> bool:
    """
    Recognize only an explicit warning boolean in a recorded numerical result.
    """
    warning = payload.get("contact_warning")
    return isinstance(warning, bool) and warning


def for_layout(targets: Targets, gym: dict[str, Any] | None, job: Path | None) -> dict[str, Any]:
    """
    Show the latest matching job only; different layouts never inherit stale performance.

    Generation is numerical solve/check wall time minus optional UV preparation,
    plus native geometry construction. First-pass and smoothing timers are subsets.
    CPU is the numerical worker only; audit and optional UV costs remain separate.
    This read-only view never polls a worker, constructs geometry or edits archives.
    """
    numerical: dict[str, Any] = {}
    native: dict[str, Any] = {}
    settings: dict[str, Any] = {}
    status = "No measured run for this layout"
    if job is not None:
        plan = _document(job / "plan.json")
        try:
            matches = plan.get("targets") == asdict(targets) and canonical(
                plan.get("gym")
            ) == canonical(gym)
        except (TypeError, ValueError):
            # A malformed or partially written record must not break layout controls.
            matches = False
        if matches:
            numerical = _document(job / "numerical-result.json")
            native = _document(job / "native-result.json")
            raw_settings = plan.get("settings")
            settings = raw_settings if isinstance(raw_settings, dict) else {}
            disposition = native.get("status") or numerical.get("status")
            if not isinstance(disposition, str):
                disposition = ""
            status = {
                "built_and_named_fidelity_checks_pass": "Latest run: completed; named fidelity passed",
                "stopped": "Latest run: stopped; partial measurements",
                "numerically_accepted": "Latest run: numerical checks completed",
                "unresolved": "Latest run: unresolved",
                "geometry_ready_contact_unmeasured": "Latest run: geometry ready",
            }.get(disposition, "Latest run: awaiting measurements")
            if _contact_warning(numerical):
                status += "; contact measurement incomplete (pair limit)"
    elapsed = _seconds(numerical, "elapsed_seconds")
    uv_prepare = _seconds(numerical, "material_uv_seconds")
    route = (
        elapsed - uv_prepare
        if elapsed is not None and uv_prepare is not None and elapsed >= uv_prepare
        else None
    )
    geometry = _seconds(native, "generation_seconds")
    total = route + geometry if route is not None and geometry is not None else None

    def value(seconds: float | None) -> str:
        """
        Render missing measurements explicitly and retain measured zero.
        """
        return f"{seconds:.3f} s" if seconds is not None else "—"

    uv = settings.get("material_uv")
    optimization = settings.get("first_pass_optimization")
    rows = [
        ("Conductors", str(targets.lines)),
        (
            "First-pass optimization",
            "On" if optimization is True else "Off" if optimization is False else "—",
        ),
        ("Generation total", value(total)),
        ("Route + checks", value(route)),
        ("Numerical CPU", value(_seconds(numerical, "cpu_seconds"))),
        ("First pass · subset", value(_seconds(numerical, "first_pass_seconds"))),
        ("Smoothing · subset", value(_seconds(numerical, "smoothing_seconds"))),
        ("Geometry build", value(geometry)),
        ("Fidelity audit", value(_seconds(native, "audit_seconds"))),
        ("UV preparation", "Off" if uv is False else value(uv_prepare)),
        ("UV storage", "Off" if uv is False else value(_seconds(native, "material_uv_seconds"))),
    ]
    return {"status": status, "rows": [{"label": label, "value": text} for label, text in rows]}


def from_execution(
    targets: Targets, gym: dict[str, Any] | None, execution: dict[str, Any] | None
) -> dict[str, Any]:
    """
    Resolve only an explicitly supplied controller job, without discovering historical runs.
    """
    job = execution.get("job") if isinstance(execution, dict) else None
    return for_layout(targets, gym, Path(job) if isinstance(job, str) and job else None)
