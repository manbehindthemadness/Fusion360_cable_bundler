"""
Measure a component-local point against the same face in an explicit assembly context.
"""

from __future__ import annotations

import math
from typing import Any


def trimmed_distance_mm(point: Any, face: Any, occurrence: Any, manager: Any) -> float:
    """
    Transform a temporary point and proxy the face together, preserving all source geometry.

    Fusion MeasureManager resolves design entities in root assembly context. Native
    component-local faces are ambiguous and can be rejected as invalid arguments.
    Point and occurrence transforms use centimeters; only the measured scalar is
    converted to millimeters. No geometric offset, fitting or correction is applied.
    """
    world = point.copy()
    if not world.transformBy(occurrence.transform2):
        raise RuntimeError("Native distance point could not enter assembly context")
    proxy = face.createForAssemblyContext(occurrence)
    if proxy is None:
        raise RuntimeError("Native distance face has no assembly-context proxy")
    measured = manager.measureMinimumDistance(world, proxy)
    value = getattr(measured, "value", None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError("Native trimmed distance is unavailable or invalid")
    if not math.isfinite(value) or value < 0:
        raise RuntimeError("Native trimmed distance is unavailable or invalid")
    return value * 10
