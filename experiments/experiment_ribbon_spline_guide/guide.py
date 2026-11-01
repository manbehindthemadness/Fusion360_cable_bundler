"""
Build one unconstrained endpoint-tangent cubic and measure ordered route agreement.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.geometry import ZERO, FoldRoute


@dataclass(frozen=True)
class Guide:
    """
    Retain an exact cubic and a bounded polyline arc-length lookup, without Fusion.

    Each Bezier handle is one third of endpoint separation, so endpoint derivative
    magnitudes equal that separation. This is a scale-invariant shape convention,
    not a shortest-path computation or physical ribbon geometry. The arrival
    derivative follows material travel into the end, not its outward face normal.
    """

    controls: tuple[Vector3, Vector3, Vector3, Vector3]
    parameters: tuple[float, ...]
    distances: tuple[float, ...]

    @classmethod
    def create(cls, targets: Targets) -> Guide:
        """
        Match both fixed endpoint positions and directed tangents with257samples.
        """
        chord = magnitude(difference(targets.end, targets.start))
        if chord <= 1e-8:
            raise ValueError("Distinct endpoints required for the chord-scaled guide.")
        controls = (
            targets.start,
            targets.start.translated(targets.start_tangent, chord / 3),
            targets.end.translated(targets.end_tangent, -chord / 3),
            targets.end,
        )
        provisional = cls(controls, (), ())
        parameters = tuple(i / 256 for i in range(257))
        points = [provisional.sample(u)[0] for u in parameters]
        distances = [0.0]
        for a, b in zip(points, points[1:]):
            distances.append(distances[-1] + magnitude(difference(b, a)))
        return cls(controls, parameters, tuple(distances))

    def sample(self, u: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate the exact cubic and its derivative on the closed unit interval.
        """
        if not math.isfinite(u) or not 0 <= u <= 1:
            raise ValueError("Guide parameter must lie in[0,1].")
        a, b, c, d = self.controls
        v = 1 - u
        point = (
            ZERO.translated(a, v**3)
            .translated(b, 3 * v * v * u)
            .translated(c, 3 * v * u * u)
            .translated(d, u**3)
        )
        velocity = (
            ZERO.translated(difference(b, a), 3 * v * v)
            .translated(difference(c, b), 6 * v * u)
            .translated(difference(d, c), 3 * u * u)
        )
        return point, velocity

    def arc_sample(self, fraction: float) -> tuple[Vector3, Vector3]:
        """
        Evaluate monotonically in approximate arc length; never jump to a near branch.
        """
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Guide arc fraction must lie in[0,1].")
        wanted = fraction * self.distances[-1]
        index = max(1, min(bisect_left(self.distances, wanted), len(self.distances) - 1))
        first, last = self.distances[index - 1 : index + 1]
        blend = (wanted - first) / (last - first) if last > first else 0.0
        u = self.parameters[index - 1] + blend * (
            self.parameters[index] - self.parameters[index - 1]
        )
        return self.sample(u)


@dataclass(frozen=True)
class Agreement:
    """
    Separate sampled guide distance/direction preferences from physical acceptance.
    """

    rms_mm: float
    maximum_mm: float
    mean_direction_loss: float


def agreement(route: FoldRoute, guide: Guide) -> Agreement:
    """
    Compare65matching normalized arc stations, with pointwise order fixed.

    This inexpensive correspondence can penalize differently placed route features;
    it is not a nearest-distance, continuous deviation or optimal alignment proof.
    Stationary guide tangents contribute zero direction preference, not a rejection.
    """
    distances = []
    directions = []
    for i in range(65):
        u = i / 64
        point, velocity = route.lane(u, 0.0)
        target, tangent = guide.arc_sample(u)
        distances.append(magnitude(difference(point, target)))
        if magnitude(tangent) > 1e-12:
            directions.append(max(0.0, 1 - dot(unit(velocity), unit(tangent))))
    return Agreement(
        math.sqrt(math.fsum(d * d for d in distances) / len(distances)),
        max(distances),
        math.fsum(directions) / len(directions) if directions else 0.0,
    )
