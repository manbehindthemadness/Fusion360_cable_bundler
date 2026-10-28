"""
Guide compatible ribbon routes around a finite reserved terminal approach.

Waypoints and the reserved strip are search hypotheses, not new physical rules.
Final original contact, intrinsic and endpoint checks remain the caller's duty.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import endpoint_metrics
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from . import broad_chart
from .solver import errors_for


def segment_rectangle_distance(
    a: tuple[float, ...], b: tuple[float, ...], length: float, half: float
) -> float:
    """
    Measure an entire segment against the finite rectangle [-L,0] x [-h,h] x {0}.

    Split at box-plane crossings and minimize each quadratic distance interval.
    This covers full segment width, not only its endpoints or a center proxy.
    """
    bounds = ((-length, 0.0), (-half, half), (0.0, 0.0))
    delta = tuple(y - x for x, y in zip(a, b))
    cuts = {0.0, 1.0}
    for x, d, limits in zip(a, delta, bounds):
        if d:
            cuts.update(t for v in limits if 0 < (t := (v - x) / d) < 1)
    ordered = sorted(cuts)

    def squared(t: float) -> float:
        """
        Evaluate squared point-to-rectangle distance at a segment fraction.
        """
        return sum(
            (v - min(hi, max(lo, v))) ** 2
            for x, d, (lo, hi) in zip(a, delta, bounds)
            for v in (x + t * d,)
        )

    best = min(squared(t) for t in ordered)
    for lo_t, hi_t in zip(ordered, ordered[1:]):
        mid = (lo_t + hi_t) / 2
        numerator = denominator = 0.0
        for x, d, (lo, hi) in zip(a, delta, bounds):
            value = x + mid * d
            if value < lo or value > hi:
                edge = lo if value < lo else hi
                numerator += d * (x - edge)
                denominator += d * d
        if denominator:
            t = min(hi_t, max(lo_t, -numerator / denominator))
            best = min(best, squared(t))
    return math.sqrt(best)


@dataclass(frozen=True)
class Approach:
    """
    Retain finite terminal reservation and frame-relative spatial detour targets.
    """

    case: EndpointCase
    side: int

    @property
    def width(self) -> float:
        """
        Return occupied ribbon width including the established edge padding.
        """
        return (self.case.lines + 0.2) * self.case.diameter_mm

    @property
    def targets(self) -> tuple[tuple[float, Vector3], ...]:
        """
        Request an outward loop and a tangent-aligned final approach.
        """
        case, width = self.case, self.width
        direction = unit(cross(case.start_tangent, case.start_width))
        return (
            (
                0.3,
                case.start.translated(case.start_tangent, width / 2).translated(
                    direction, self.side * width
                ),
            ),
            (
                0.6,
                case.end.translated(case.end_tangent, -1.5 * width).translated(
                    direction, self.side * width
                ),
            ),
            (0.85, case.end.translated(case.end_tangent, -width / 2)),
        )

    def distances(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Compare seventeen early full-width rulings with the finite approach rectangle.

        The final thirty percent is intentionally free to enter its own arrival region.
        Sampling in carrier parameter is not continuous obstacle certification.
        """
        case = self.case
        normal = unit(cross(case.end_tangent, case.end_width))
        axes = (case.end_tangent, case.end_width, normal)
        half = path.field.half_width_mm
        result = []
        for i in range(17):
            ends = tuple(
                tuple(
                    dot(difference(path.lane(0.7 * i / 16, q)[0], case.end), axis) for axis in axes
                )
                for q in (-half, half)
            )
            result.append(segment_rectangle_distance(ends[0], ends[1], self.width, half))
        return tuple(result)

    def residual(self, path: CompatiblePath, weight: float) -> tuple[float, ...]:
        """
        Combine fading positional guidance with finite approach occupancy guidance.
        """
        waypoint = tuple(
            weight * value / self.width
            for u, target in self.targets
            for delta in (difference(path.lane(u, 0)[0], target),)
            for value in (delta.x, delta.y, delta.z)
        )
        corridor = tuple(
            max(0.0, self.case.diameter_mm - d) / self.case.diameter_mm
            for d in self.distances(path)
        )
        return waypoint + corridor


def refine(
    case: EndpointCase, original: tuple[float, ...], side: int, checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Fit two coarse guidance stages and one fine closure stage under520transports.

    The ten original compatible coordinates can all change. Three stalled rounds
    stop each stage. Five line-search fractions allow smaller spatial updates.
    """
    started = perf_counter()
    guide = Approach(case, side)
    points = (case.start,) + tuple(p for _, p in guide.targets) + (case.end,)
    required = sum(magnitude(difference(b, a)) for a, b in zip(points, points[1:]))
    chord = magnitude(difference(case.end, case.start))
    maximum = broad_chart.carrier_maximum(case)
    values = original[:9] + (min(maximum, max(original[9], required / chord)),)
    lower, upper = broad_chart.bounds(case)
    evaluations = 0
    trials: list[dict[str, Any]] = []

    def transport(parameters: tuple[float, ...], grid: int) -> CompatiblePath:
        """
        Charge every derivative, baseline and trial transport to the same cap.
        """
        nonlocal evaluations
        if evaluations >= 520:
            raise RuntimeError("Spatial approach transport cap")
        evaluations += 1
        return broad_chart.integrate(case, parameters, grid, checkpoint)

    for grid, rounds, weight in ((64, 12, 1.0), (64, 12, 0.15), (512, 8, 0.0)):
        path = transport(values, grid)
        errors = errors_for(case, path) + guide.residual(path, weight)
        score = sum(v * v for v in errors)
        damping, stalled = 1e-3, 0
        for outer in range(rounds):
            if max(abs(v) for v in errors) < 1e-9:
                break
            columns = []
            for index in range(10):
                _, parameters = probe_coordinates(values, index, maximum)
                probe = transport(parameters, grid)
                observed = errors_for(case, probe) + guide.residual(probe, weight)
                step = parameters[index] - values[index]
                columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
            result = constrained_step(columns, errors, damping, [()] * 10, (), values, lower, upper)
            accepted = False
            for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625):
                _, proposed = trial_coordinates(values, result.values, fraction, maximum)
                candidate = transport(proposed, grid)
                observed = errors_for(case, candidate) + guide.residual(candidate, weight)
                after = sum(v * v for v in observed)
                take = after < score
                trials.append(
                    dict(
                        grid=grid,
                        weight=weight,
                        outer=outer,
                        fraction=fraction,
                        before=score,
                        after=after,
                        accepted=take,
                        coordinates=proposed,
                    )
                )
                if take:
                    values, path, errors, score = proposed, candidate, observed, after
                    accepted = True
                    break
            damping = max(1e-10, damping / 3) if accepted else damping * 10
            stalled = 0 if accepted else stalled + 1
            if stalled >= 3:
                break
    baseline = transport(original, 512)
    movement = [
        magnitude(difference(path.lane(i / 32, 0)[0], baseline.lane(i / 32, 0)[0]))
        for i in range(33)
    ]
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        coordinates=values,
        evaluations=evaluations,
        seconds=perf_counter() - started,
        score=sum(v * v for v in errors_for(case, path)),
        trials=trials,
        side=side,
        maximum_center_displacement_mm=max(movement),
        rms_center_displacement_mm=math.sqrt(sum(v * v for v in movement) / len(movement)),
        approach_minimum_mm=min(guide.distances(path)),
        waypoint_targets=[dict(u=u, x=p.x, y=p.y, z=p.z) for u, p in guide.targets],
    )
    return path, metrics
