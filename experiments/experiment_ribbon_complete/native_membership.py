"""
Use an actual trimmed-face witness before requesting an expensive minimum-distance search.
"""

from __future__ import annotations

import math
from typing import Any

from .native_distance import trimmed_distance_mm


def witness_distance_mm(point: Any, face: Any, occurrence: Any, manager: Any) -> float:
    """
    Bound distance by a native on-trim witness; measure the actual minimum on membership misses.

    A positive native membership query plus evaluation at that unchanged parameter
    provides a real point on the trimmed face. Its distance is an upper bound on
    minimum distance, sufficient for the same0.01mm correspondence gate. It is not
    relabeled as an exact minimum. Rejected membership retains the established
    assembly-context measurement. No source point or native parameter is repaired.
    """
    evaluator = face.evaluator
    ok, parameter = evaluator.getParameterAtPoint(point)
    if not ok or not evaluator.isParameterOnFace(parameter):
        return trimmed_distance_mm(point, face, occurrence, manager)
    ok, witness = evaluator.getPointAtParameter(parameter)
    if not ok or witness is None:
        raise RuntimeError("Native on-trim correspondence witness is unavailable")
    distance = point.distanceTo(witness)
    if not math.isfinite(distance) or distance < 0:
        raise RuntimeError("Native on-trim witness distance is invalid")
    return distance * 10
