"""
Contract one supplied edge pair to an observed constraint boundary with fixed cap poses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

from .extrema import PeakCheck, check_peaks
from .geometry import EdgeChart
from .growth import rescale, within_limit
from .measure import PairMeasure, measure


@dataclass(frozen=True)
class ContractionTrial:
    """
    Retain one common contraction and the measured reason it passes or fails.
    """

    factor: float
    curve: BoundaryCurve
    measured: PairMeasure
    peaks: PeakCheck | None

    @property
    def passes(self) -> bool:
        """
        Require both the uniform and refined-peak checks, with strictly positive progress.
        """
        limit = PinchLimit(99.6)
        return (
            within_limit(self.measured, limit)
            and self.peaks is not None
            and self.peaks.within(limit)
        )

    @property
    def triggers(self) -> tuple[str, ...]:
        """
        Report local rule failures without interpreting a finite failure as impossibility.
        """
        if any(sample is None for sample in self.measured.frames):
            return ("singular material frame",)
        j = self.peaks.minimum_j if self.peaks is not None else self.measured.minimum_j
        a = self.peaks.peak_a if self.peaks is not None else self.measured.peak_a
        b = self.peaks.peak_b if self.peaks is not None else self.measured.peak_b
        rules = []
        if j <= 0:
            rules.append("material fold reversal")
        if a > 0.996:
            rules.append("A macaroni pinch")
        if b is not None and b > 0.996:
            rules.append("B macaroni pinch")
        return tuple(rules)


@dataclass(frozen=True)
class Contraction:
    """
    Retain both sides of an observed boundary; no minimum-length claim is implied.
    """

    passing: ContractionTrial | None
    failing: ContractionTrial | None
    evaluations: int
    disposition: str


def contract(
    chart: EdgeChart,
    checkpoint: Callable[[], None],
    observe: Callable[[ContractionTrial, str], None],
    *,
    steps: int = 12,
    refinements: int = 24,
) -> Contraction:
    """
    Pull the supplied curve toward its endpoint bridge until a measured rule triggers.

    Both guides derive from each changed primary curve. Halve its interior scale
    until a failure is observed, then bisect that passing/failing interval. Fixed
    target positions, tangent/width directions and terminal ruling slope survive.
    No coefficient fitting, seed bank, hard length cap or relaxed rule is used.
    The bracket is evidence along this contraction family, not proof of the first
    continuous crossing, globally shortest route or global physical feasibility.
    Caller checkpoints enforce resource/source/cancellation limits and propagate stops.
    """
    if (
        isinstance(steps, bool)
        or not isinstance(steps, int)
        or not 1 <= steps <= 12
        or isinstance(refinements, bool)
        or not isinstance(refinements, int)
        or not 0 <= refinements <= 24
    ):
        raise ValueError("Use one to twelve contractions and at most twenty-four refinements.")
    evaluations = 0
    limit = PinchLimit(99.6)

    def evaluate(factor: float, stage: str) -> ContractionTrial:
        """
        Recompute both edges and retain every tested shape before proceeding.
        """
        nonlocal evaluations
        checkpoint()
        shape = rescale(chart.original, factor)
        observed = measure(chart, shape, 4097, limit)
        peaks = None
        if observed.minimum_j > 0 and all(sample is not None for sample in observed.frames):
            peaks = check_peaks(chart, shape, observed, checkpoint)
        trial = ContractionTrial(factor, shape, observed, peaks)
        evaluations += 1
        observe(trial, stage)
        return trial

    passing = evaluate(1.0, "original")
    if not passing.passes:
        return Contraction(None, passing, evaluations, "input fails local checks")
    failing = None
    for step in range(steps):
        candidate = evaluate(passing.factor / 2, f"contract:{step}")
        if candidate.passes:
            passing = candidate
        else:
            failing = candidate
            break
    if failing is None:
        return Contraction(passing, None, evaluations, "no trigger within contraction budget")
    for refinement in range(refinements):
        candidate = evaluate((passing.factor + failing.factor) / 2, f"boundary:{refinement}")
        if candidate.passes:
            passing = candidate
        else:
            failing = candidate
    return Contraction(passing, failing, evaluations, "observed constraint boundary bracketed")
