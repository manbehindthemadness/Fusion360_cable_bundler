"""
Normalize both material edges by growing one endpoint-anchored curve.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import difference
from devtools.ribbon_analysis.bernstein import elevate_controls
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

from .geometry import EdgeChart
from .measure import PairMeasure, measure


def grow(original: BoundaryCurve, factor: float) -> BoundaryCurve:
    """
    Grow the supplied geometry while fixing endpoint positions and frame directions.

    Q=P+(factor-1)*(P-C), where C is a clamped degree-seven endpoint bridge.
    C has zero first, second and third derivatives at both caps. Consequently
    Q's first three endpoint derivatives scale together, retaining tangent,
    binormal and zero terminal ruling slope. The actual interior is re-evaluated;
    this is geometric growth, not a parameter-speed change or an offset-only fix.
    No length penalty or maximum physical length is imposed.
    """
    if (
        isinstance(factor, bool)
        or not isinstance(factor, (float, int))
        or not math.isfinite(factor)
        or factor < 1
    ):
        raise ValueError("Growth requires a finite factor of at least one.")
    return rescale(original, factor)


def rescale(original: BoundaryCurve, factor: float) -> BoundaryCurve:
    """
    Scale displacement from the endpoint bridge, preserving ordered cap positions/frames.

    Positive factors below one contract the geometry; factors above one grow it.
    First three cap derivatives scale together. A zero factor would collapse the
    prescribed cap directions and is rejected. This is not a feasibility test.
    """
    if (
        isinstance(factor, bool)
        or not isinstance(factor, (float, int))
        or not math.isfinite(factor)
        or factor <= 0
    ):
        raise ValueError("Endpoint-anchored rescaling requires a finite positive factor.")
    if factor == 1:
        return original
    start, end = original.points[0], original.points[-1]
    bridge = elevate_controls((start,) * 4 + (end,) * 4, len(original.points) - 1)
    points = tuple(
        point.translated(difference(point, anchor), factor - 1)
        for point, anchor in zip(original.points, bridge)
    )
    return BoundaryCurve(points)


@dataclass(frozen=True)
class NormalizedPair:
    """
    Retain a shared growth factor and sampled paired-edge disposition, without native PASS.
    """

    curve: BoundaryCurve
    factor: float
    measured: PairMeasure
    evaluations: int
    disposition: str


def within_limit(measured: PairMeasure, limit: PinchLimit) -> bool:
    """
    Require positive material progress and both strict sampled thickness limits.
    """
    return (
        measured.failed == 0
        and measured.minimum_j > 0
        and measured.peak_a <= limit.fraction
        and measured.peak_b is not None
        and measured.peak_b <= limit.fraction
    )


def normalize(
    chart: EdgeChart,
    checkpoint: Callable[[], None],
    observe: Callable[[BoundaryCurve, PairMeasure, float, str], None],
    *,
    doublings: int = 18,
    refinements: int = 12,
) -> NormalizedPair:
    """
    Reset to the supplied edge and find a sampled-valid common growth bracket.

    Both guides derive from the grown primary curve and its new material frame.
    A scalar feasibility bracket grows that same curve, never a seed bank or a
    coefficient fit. Refinement retains a valid upper bracket; it is not a proof
    of the globally shortest path or globally minimal growth. A separate 4097-point grid
    must pass before success is reported. If it fails, growth continues within
    the same frozen doubling budget. Exhaustion remains unresolved.
    Time, RSS, source and cancellation limits belong to the caller's checkpoint.
    """
    if (
        isinstance(doublings, bool)
        or not isinstance(doublings, int)
        or not 0 <= doublings <= 18
        or isinstance(refinements, bool)
        or not isinstance(refinements, int)
        or not 0 <= refinements <= 12
    ):
        raise ValueError("Use at most eighteen growth doublings and twelve refinements.")
    limit = PinchLimit(99.6)
    evaluations = 0

    def evaluate(factor: float, grid_size: int, stage: str) -> tuple[BoundaryCurve, PairMeasure]:
        """
        Recompute the common frame and both edge demands after every geometric change.
        """
        nonlocal evaluations
        checkpoint()
        evaluated_curve = grow(chart.original, factor)
        observation = measure(chart, evaluated_curve, grid_size, limit)
        evaluations += 1
        observe(evaluated_curve, observation, factor, stage)
        return evaluated_curve, observation

    high = 1.0
    stations = 513
    curve, current = evaluate(high, stations, "reset-original")
    if within_limit(current, limit):
        curve, current = evaluate(high, 4097, "dense-check")
        if within_limit(current, limit):
            return NormalizedPair(curve, high, current, evaluations, "sampled limits satisfied")
        stations = 4097
    for step in range(doublings):
        low, high = high, high * 2
        curve, current = evaluate(high, stations, f"grow:{step}")
        if not within_limit(current, limit):
            continue
        for refinement in range(refinements):
            middle = (low + high) / 2
            candidate, measured = evaluate(middle, stations, f"normalize:{step}:{refinement}")
            if within_limit(measured, limit):
                high, curve, current = middle, candidate, measured
            else:
                low = middle
        curve, current = evaluate(high, 4097, "dense-check")
        if within_limit(current, limit):
            return NormalizedPair(curve, high, current, evaluations, "sampled limits satisfied")
        stations = 4097
    curve, current = evaluate(high, 4097, "exhausted-dense-check")
    return NormalizedPair(curve, high, current, evaluations, "unresolved")
