"""
Format measured candidate timings without treating absent work as zero time.
"""

from __future__ import annotations

import math
from collections.abc import Mapping


def _seconds(row: Mapping[str, object], key: str) -> float | None:
    """
    Validate an optional finite, nonnegative recorded duration.
    """
    value = row.get(key)
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"Invalid timing value: {key}")
    return float(value)


def timing_values(row: Mapping[str, object]) -> dict[str, float | None]:
    """
    Separate solver/preflight from authoring-plus-native construction and audit time.

    Geometry excludes component setup, audits, labeling, archive and display.
    A recorded partial profile/loft duration remains partial when built is false.
    """
    section = _seconds(row, "section_seconds")
    loft, sweep = _seconds(row, "loft_seconds"), _seconds(row, "sweep_seconds")
    if loft is not None and sweep is not None:
        raise ValueError("A timing row cannot mix loft and sweep construction.")
    native = sweep if sweep is not None else loft
    return {
        "solver_seconds": _seconds(row, "numerical_seconds"),
        "geometry_seconds": None if section is None else section + (native or 0),
        "audit_seconds": _seconds(row, "audit_seconds"),
    }


def timing_label(row: Mapping[str, object]) -> str:
    """
    Produce a compact per-candidate counter label, marking incomplete geometry.
    """
    name = row.get("case_id")
    if not isinstance(name, str) or not name:
        raise ValueError("A timing label requires a candidate ID.")
    values = timing_values(row)
    solver, geometry = values["solver_seconds"], values["geometry_seconds"]
    solver_text = "not attempted" if solver is None else f"{solver * 1000:.2f} ms"
    geometry_text = "not attempted" if geometry is None else f"{geometry:.3f} s"
    if geometry is not None and not row.get("built"):
        geometry_text += " partial"
    return f"{name} | solve {solver_text} | geometry {geometry_text}"
