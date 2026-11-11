"""
Bound positive-weight source seams against actual finite native straight edges.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, cast

from experiments.experiment_ribbon_fold_route.contact_bounds import Span

LINE_TYPE = "adsk::core::Line3D"


@dataclass(frozen=True)
class Certificate:
    """
    Retain an outward control-hull/sample distance bound for the supplied actual edge.
    """

    controls: int
    samples: int
    maximum_error_mm: float


def _distance_bound(point: Any, start: Any, end: Any) -> float:
    """
    Bound distance to one actual point on the finite edge, using outward interval arithmetic.

    An approximate clamped projection only chooses a parameter in [0,1]; it
    need not be the exact nearest point. Every such parameter names a real
    point on the finite straight edge. Ill-conditioned selection uses its
    actual trimmed start point, never the supporting infinite line.
    Coordinates are native centimeters; return an outward millimeter bound.
    """
    a = tuple(getattr(start, axis, math.nan) for axis in "xyz")
    b = tuple(getattr(end, axis, math.nan) for axis in "xyz")
    p = tuple(getattr(point, axis, math.nan) for axis in "xyz")
    if any(
        type(value) not in (int, float) or not math.isfinite(value)
        for triple in (a, b, p)
        for value in triple
    ):
        return math.inf
    direction = tuple(y - x for x, y in zip(a, b))
    offset = tuple(y - x for x, y in zip(a, p))
    products = tuple(x * x for x in direction)
    mixed = tuple(x * y for x, y in zip(direction, offset))
    parameter = 0.0
    if all(math.isfinite(value) for value in (*products, *mixed)):
        denominator = math.fsum(value / 4 for value in products)
        numerator = math.fsum(value / 4 for value in mixed)
        if math.isfinite(denominator) and denominator > 0 and math.isfinite(numerator):
            parameter = min(1.0, max(0.0, numerator / denominator))
    squared = Span(0.0, 0.0)
    for x, y, target in zip(a, b, p):
        position = (
            Span(x, x)
            if parameter == 0.0
            else Span(y, y)
            if parameter == 1.0
            else Span(x, x).add(Span(y, y).add(Span(-x, -x)).scale(parameter))
        )
        residual = Span(target, target).add(position.scale(-1.0))
        magnitude = max(abs(residual.low), abs(residual.high))
        squared = squared.add(Span(magnitude, magnitude).multiply(Span(magnitude, magnitude)))
    bound_cm = math.nextafter(math.sqrt(max(0.0, squared.high)), math.inf)
    return Span(bound_cm, bound_cm).scale(10.0).high


def certify(
    edge: Any,
    controls: tuple[Any, ...],
    points: tuple[Any, ...],
    goal_mm: float,
    checkpoint: Callable[[], None],
) -> Certificate | None:
    """
    Certify a positive-weight control hull and every original sample on one real shared straight edge.

    The caller supplies assembly-space controls/samples and an actual shared
    native edge proxy. Positive rational weights are the authored seam contract.
    Its curve lies in the convex control hull; the epsilon-neighborhood of a
    finite straight segment is convex. Outward bounds for every control therefore
    bound the entire source seam. Original evaluated samples are bounded too.
    Curved/unknown geometry, missing data or warning-only bounds decline to the
    original native-distance search. No native entity, trim or tolerance changes.
    """
    if (
        not controls
        or not points
        or getattr(getattr(edge, "geometry", None), "objectType", None) != LINE_TYPE
    ):
        return None
    evaluator = getattr(edge, "evaluator", None)
    extents = getattr(evaluator, "getParameterExtents", None)
    evaluate = getattr(evaluator, "getPointAtParameter", None)
    if not callable(extents) or not callable(evaluate):
        return None
    read_extents = cast(Callable[[], tuple[bool, float, float]], extents)
    read_point = cast(Callable[[float], tuple[bool, Any]], evaluate)
    checkpoint()
    ok, low, high = read_extents()
    if not ok or not math.isfinite(low) or not math.isfinite(high) or not low < high:
        return None
    checkpoint()
    first_ok, start = read_point(low)
    checkpoint()
    last_ok, end = read_point(high)
    if not first_ok or not last_ok or start is None or end is None:
        return None
    maximum = 0.0
    for point in (*controls, *points):
        checkpoint()
        bound = _distance_bound(point, start, end)
        if not math.isfinite(bound) or not 0.0 <= bound <= goal_mm:
            return None
        maximum = max(maximum, bound)
    return Certificate(len(controls), len(points), maximum)
