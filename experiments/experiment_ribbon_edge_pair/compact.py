"""
Shorten a supplied valid edge pair through local, constraint-projected deformations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import difference, magnitude
from devtools.ribbon_analysis.pinch import PinchLimit
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve

from .extrema import PeakCheck, check_peaks
from .geometry import EdgeChart
from .growth import within_limit
from .measure import PairMeasure, frames_at, measure


def distance(observed: PairMeasure) -> float:
    """
    Integrate primary material distance with Simpson weights on an odd uniform grid.
    """
    intervals = len(observed.frames) - 1
    if intervals < 2 or intervals % 2 or any(frame is None for frame in observed.frames):
        raise ValueError("Distance requires an odd, regular sampled material grid.")
    return sum(
        (1 if i in (0, intervals) else 4 if i % 2 else 2) * frame.speed
        for i, frame in enumerate(observed.frames)
        if frame is not None
    ) / (3 * intervals)


def _deficits(observed: PairMeasure, width: float, radius: float) -> tuple[float, ...]:
    """
    Expose signed A/B inequalities, retaining the constraints' feasible-side slack.
    """
    result = []
    for frame in observed.frames:
        if frame is None:
            raise ValueError("Cannot differentiate a singular material frame.")
        demand = radius * frame.curvature * (1 + frame.slope**2) / 0.996
        result.extend((demand - 1, demand - 1 + width * frame.slope_rate / frame.speed))
    return tuple(result)


def _active_fractions(observed: PairMeasure, width: float, radius: float) -> tuple[float, ...]:
    """
    Include dense local maxima of both inequalities alongside the uniform correction grid.
    """
    deficits = _deficits(observed, width, radius)
    count = len(observed.frames)
    indices = {0, count - 1}
    for i in range(1, count - 1):
        for side in (0, 1):
            value = deficits[2 * i + side]
            if value >= deficits[2 * (i - 1) + side] and value > deficits[2 * (i + 1) + side]:
                indices.update((i - 1, i, i + 1))
    return tuple(sorted({i / 64 for i in range(65)} | {i / (count - 1) for i in indices}))


def _constraints(
    chart: EdgeChart,
    curve: BoundaryCurve,
    fractions: tuple[float, ...],
    width: float,
    radius: float,
) -> tuple[float, ...]:
    """
    Evaluate signed inequalities at a fixed shared set of current critical locations.
    """
    samples = frames_at(chart, curve, fractions)
    observed = PairMeasure((), samples, 0, 0, None, 0, ())
    return _deficits(observed, width, radius)


def projected_step(
    descent: tuple[float, ...],
    gradients: tuple[tuple[float, ...], ...],
    deficits: tuple[float, ...],
    radius: float,
) -> tuple[float, ...]:
    """
    Project a bounded descent onto linearized feasible halfspaces, without relaxing limits.

    A finite cyclic projection is only a proposed step. Nonlinear paired-edge
    measurements must independently accept the resulting geometry.
    """
    norm = math.sqrt(sum(value * value for value in descent))
    if not norm:
        return descent
    step = [value * radius / norm for value in descent]
    for _ in range(12):
        for row, deficit in zip(gradients, deficits):
            violation = sum(a * b for a, b in zip(row, step)) + deficit
            squared = sum(value * value for value in row)
            if violation > 0 and squared > 1e-24:
                step = [
                    value - violation * component / squared for value, component in zip(step, row)
                ]
        current_norm = math.sqrt(sum(value * value for value in step))
        if current_norm > radius:
            step = [value * radius / current_norm for value in step]
    return tuple(step)


@dataclass(frozen=True)
class LocalShape:
    """
    Allow cap tightness and interior geometry to move around one supplied pair.

    Endpoint positions and ordered material frames remain fixed. Interior control
    displacements use the supplied shape's extent, avoiding a chord-sized step
    that cannot retract an already inflated curve. This is a local chart, not
    a bank of routes or an alternate endpoint discovery method.
    """

    chart: EdgeChart

    def curve(self, values: tuple[float, ...]) -> BoundaryCurve:
        """
        Apply sixteen finite local coordinates without endpoint snapping or side swaps.
        """
        if len(values) != 16 or not all(math.isfinite(value) for value in values):
            raise ValueError("Local shortening requires sixteen finite coordinates.")
        points = self.chart.original.points
        chord = magnitude(difference(points[-1], points[0]))
        if chord <= 1e-8:
            raise ValueError("Coincident edge targets are unsupported.")
        extent = max(magnitude(difference(point, points[0])) for point in points)
        coordinates = values[:4] + tuple(value * extent / chord for value in values[4:])
        return self.chart.curve(coordinates)


@dataclass(frozen=True)
class CompactPair:
    """
    Retain the last densely checked pair and distinguish shortening from physical acceptance.
    """

    curve: BoundaryCurve
    measured: PairMeasure
    accepted: int
    evaluations: int
    disposition: str


def shorten(
    chart: EdgeChart,
    checkpoint: Callable[[], None],
    observe: Callable[[BoundaryCurve, PairMeasure, str], None],
    *,
    rounds: int = 32,
    observe_extrema: Callable[[BoundaryCurve, PeakCheck, str], None] | None = None,
) -> CompactPair:
    """
    Retract supplied valid geometry while recomputing B after each proposed local change.

    A finite-difference length gradient is projected against both signed edge
    inequalities. Only strictly shorter pairs that clear both a 513-station trial
    and a 4097-station check with refined local peaks are retained. Failed proposals stay in the observer
    history. No hard length cap, global minimum or continuous certificate is implied.
    Resource/source/cancellation stops propagate to the caller without retries.
    """
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 0 <= rounds <= 32:
        raise ValueError("Use at most thirty-two bounded local shortening rounds.")
    local = LocalShape(chart)
    limit = PinchLimit(99.6)
    width = chart.case.lines * chart.case.diameter_mm + 0.2 * chart.case.diameter_mm
    values = (0.0,) * 16
    evaluations = accepted = 0

    def evaluate(
        proposal_coordinates: tuple[float, ...], stations: int, stage: str
    ) -> tuple[BoundaryCurve, PairMeasure]:
        """
        Preserve every measured pair before another local deformation is proposed.
        """
        nonlocal evaluations
        checkpoint()
        candidate = local.curve(proposal_coordinates)
        measurement = measure(chart, candidate, stations, limit)
        evaluations += 1
        observe(candidate, measurement, stage)
        return candidate, measurement

    retained, checked = evaluate(values, 4097, "initial-dense")
    if not within_limit(checked, limit):
        return CompactPair(retained, checked, 0, evaluations, "input not sampled-valid")

    def peaks_valid(shape: BoundaryCurve, observation: PairMeasure, stage: str) -> bool:
        """
        Retain extrema witnesses and reject narrow peaks missed by the uniform grid.
        """
        peaks = check_peaks(chart, shape, observation, checkpoint)
        if observe_extrema is not None:
            observe_extrema(shape, peaks, stage)
        return peaks.within(limit)

    if not peaks_valid(retained, checked, "initial-extrema"):
        return CompactPair(retained, checked, 0, evaluations, "input fails refined peaks")
    chord = magnitude(difference(retained.points[-1], retained.points[0]))
    if distance(checked) <= chord * (1 + 1e-10):
        return CompactPair(retained, checked, 0, evaluations, "already at chord lower bound")
    for iteration in range(rounds):
        local = LocalShape(EdgeChart(chart.case, retained))
        values = (0.0,) * 16
        _, base = evaluate(values, 65, f"local:{iteration}")
        length = distance(base)
        fractions = _active_fractions(checked, width, chart.case.diameter_mm / 2)
        deficits = _constraints(chart, retained, fractions, width, chart.case.diameter_mm / 2)
        columns, descent = [], []
        for index in range(16):
            coordinates = list(values)
            coordinates[index] += 1e-5
            perturbed, probe = evaluate(tuple(coordinates), 65, f"sensitivity:{iteration}:{index}")
            columns.append(
                tuple(
                    (b - a) / 1e-5
                    for a, b in zip(
                        deficits,
                        _constraints(
                            chart, perturbed, fractions, width, chart.case.diameter_mm / 2
                        ),
                    )
                )
            )
            descent.append(-(distance(probe) - length) / (1e-5 * length))
        rows = tuple(tuple(column[i] for column in columns) for i in range(len(deficits)))
        direction = projected_step(tuple(descent), rows, deficits, 0.25)
        if sum(a * b for a, b in zip(direction, descent)) <= 1e-12:
            break
        changed = False
        for division in range(10):
            coordinates = tuple(a + b / 2**division for a, b in zip(values, direction))
            proposed, trial = evaluate(coordinates, 513, f"retract:{iteration}:{division}")
            if not within_limit(trial, limit) or distance(trial) >= distance(checked):
                continue
            proposed, dense = evaluate(coordinates, 4097, f"dense:{iteration}:{division}")
            if (
                within_limit(dense, limit)
                and distance(dense) < distance(checked)
                and peaks_valid(proposed, dense, f"extrema:{iteration}:{division}")
            ):
                values, retained, checked = coordinates, proposed, dense
                accepted += 1
                changed = True
                break
        if not changed:
            break
    return CompactPair(
        retained,
        checked,
        accepted,
        evaluations,
        "sampled-valid shortening" if accepted else "no shortening found",
    )
