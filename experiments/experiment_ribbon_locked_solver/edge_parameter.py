"""
Verify a sample against an actual trimmed native edge before expensive minimum-distance fallback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, cast


@dataclass(frozen=True)
class Witness:
    """
    Retain one actual finite-edge parameter and independently measured native sample error.
    """

    parameter: float
    error_mm: float


def inspect(
    edge: Any, point: Any, goal_mm: float, checkpoint: Callable[[], None]
) -> Witness | None:
    """
    Verify a goal-accurate native curve point inside the actual edge's parameter extents.

    Inverse lookup alone grants nothing. Clamp its finite proposal to the
    actual bounded edge range, evaluate the real native support there, and
    independently measure its three-dimensional error. A valid close point
    is a sufficient distance witness, not a globally nearest-point claim.
    Missing or failed inverse information and warning-only errors return
    no witness; callers retain their unchanged minimum-distance fallback.
    """
    evaluator = getattr(edge, "evaluator", None)
    raw_extents = getattr(evaluator, "getParameterExtents", None)
    raw_parameter = getattr(evaluator, "getParameterAtPoint", None)
    raw_point = getattr(evaluator, "getPointAtParameter", None)
    if not all(callable(method) for method in (raw_extents, raw_parameter, raw_point)):
        return None
    extents = cast(Callable[[], tuple[bool, float, float]], raw_extents)
    parameter_at = cast(Callable[[Any], tuple[bool, float]], raw_parameter)
    point_at = cast(Callable[[float], tuple[bool, Any]], raw_point)
    checkpoint()
    ok, low, high = extents()
    if not ok or not all(math.isfinite(value) for value in (low, high)) or low > high:
        return None
    ok, parameter = parameter_at(point)
    if not ok or not math.isfinite(parameter):
        return None
    parameter = min(high, max(low, parameter))
    ok, actual = point_at(parameter)
    if not ok or actual is None:
        return None
    error = actual.distanceTo(point) * 10
    if not math.isfinite(error) or not 0.0 <= error <= goal_mm:
        return None
    return Witness(parameter, error)
