"""
Refine sampled paired-edge extrema without changing the curve or physical limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve, BoundaryFrame

from .geometry import EdgeChart
from .measure import PairMeasure, frames_at


@dataclass(frozen=True)
class PeakCheck:
    """
    Retain refined local extrema and witnesses; this remains a finite numerical check.
    """

    minimum_j: float
    peak_a: float
    peak_b: float | None
    witnesses: tuple[tuple[str, float, float], ...]

    def within(self, limit: PinchLimit) -> bool:
        """
        Reject folded material progress and either edge's excessive pinch.
        """
        return (
            self.minimum_j > 0
            and self.peak_a <= limit.fraction
            and self.peak_b is not None
            and self.peak_b <= limit.fraction
        )


def _maximum(
    function: Callable[[float], float], low: float, high: float, checkpoint: Callable[[], None]
) -> tuple[float, float]:
    """
    Refine a sampled local-maximum bracket with twenty-four bounded golden steps.
    """
    ratio = (5**0.5 - 1) / 2
    left, right = high - ratio * (high - low), low + ratio * (high - low)
    a, b = function(left), function(right)
    for i in range(24):
        if i % 8 == 0:
            checkpoint()
        if a < b:
            low, left, a = left, right, b
            right = low + ratio * (high - low)
            b = function(right)
        else:
            high, right, b = right, left, a
            left = high - ratio * (high - low)
            a = function(left)
    return (left, a) if a >= b else (right, b)


def check_peaks(
    chart: EdgeChart, curve: BoundaryCurve, observed: PairMeasure, checkpoint: Callable[[], None]
) -> PeakCheck:
    """
    Refine dense local maxima of A pinch, B pinch and negative material progress.

    Uniform samples only establish brackets. The check adds interior extrema
    witnesses without claiming all extrema or continuous compliance. Singular or
    nonpositive progress can never count as a safe negative B utilization.
    """
    width = chart.case.lines * chart.case.diameter_mm + 0.2 * chart.case.diameter_mm
    radius = chart.case.diameter_mm / 2

    def values(sample: BoundaryFrame) -> tuple[float, float, float]:
        """
        Express the three checks as quantities whose maxima need inspection.
        """
        j = 1 - width * sample.slope_rate / sample.speed
        demand = radius * sample.curvature * (1 + sample.slope**2)
        return demand, demand / j if j > 0 else float("inf"), -j

    if (
        len(observed.frames) < 3
        or len(observed.frames) % 2 == 0
        or any(sample is None for sample in observed.frames)
    ):
        raise ValueError("Peak refinement needs a regular uniform sampled pair.")
    rows = tuple(values(sample) for sample in observed.frames if sample is not None)
    intervals = len(rows) - 1
    maxima = [max(row[side] for row in rows) for side in range(3)]
    witnesses = []
    for side, name in enumerate(("A", "B", "negative-J")):
        for i in range(1, intervals):
            if rows[i][side] < rows[i - 1][side] or rows[i][side] <= rows[i + 1][side]:
                continue

            def evaluate(u: float, component: int = side) -> float:
                """
                Re-evaluate the same material curve inside the current extremum bracket.
                """
                return values(frames_at(chart, curve, (u,))[0])[component]

            fraction, maximum = _maximum(
                evaluate, (i - 1) / intervals, (i + 1) / intervals, checkpoint
            )
            maxima[side] = max(maxima[side], maximum)
            witnesses.append((name, fraction, maximum))
    return PeakCheck(-maxima[2], maxima[0], maxima[1] if maxima[2] < 0 else None, tuple(witnesses))
