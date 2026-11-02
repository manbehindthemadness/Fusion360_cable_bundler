"""
Assign existing bends to ordered guide turning stations without fixing spatial joints.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute, PlacedPiece
from experiments.experiment_ribbon_spline_guide.guide import Guide


def centers(pieces: tuple[PlacedPiece, ...]) -> tuple[Vector3, ...]:
    """
    Locate the center-lane midpoint of each actual curved interval in material order.
    """
    output = []
    for piece in pieces:
        if isinstance(piece.geometry, CylindricalFold):
            low, high = piece.geometry.bend_interval(0.0)
            output.append(piece.surface((low + high) / 2, 0.0)[0])
    return tuple(output)


@dataclass(frozen=True)
class Placement:
    """
    Freeze turning-weighted targets for the existing bends, normalized by guide length.

    Absolute heading variation preserves ordered stations through guide reversals;
    this does not certify that a fold follows the desired signed turn or width frame.
    Stationary sampled guide tangents leave placement unresolved, never fabricated.
    """

    targets: tuple[Vector3, ...]
    weights: tuple[float, ...]
    parameters: tuple[float, ...]
    scale_mm: float

    @classmethod
    def create(cls, route: FoldRoute, guide: Guide) -> Placement | None:
        """
        Match bend-turn mid-quantiles to cumulative guide heading change with257fixed samples.
        """
        velocities = [guide.sample(u)[1] for u in guide.parameters]
        if any(magnitude(v) <= 1e-12 for v in velocities):
            return None
        tangents = [unit(v) for v in velocities]
        cumulative = [0.0]
        for a, b in zip(tangents, tangents[1:]):
            cumulative.append(cumulative[-1] + math.atan2(magnitude(cross(a, b)), dot(a, b)))
        turns = tuple(
            abs(p.geometry.angle_radians * math.cos(p.geometry.bank_radians))
            for p in route.pieces
            if isinstance(p.geometry, CylindricalFold)
        )
        total = math.fsum(turns)
        if total <= 1e-12 or cumulative[-1] <= 1e-12 or guide.distances[-1] <= 1e-12:
            return None
        weights = tuple(turn / total for turn in turns)
        parameters = []
        preceding = 0.0
        for weight in weights:
            wanted = (preceding + weight / 2) * cumulative[-1]
            index = max(1, min(bisect_left(cumulative, wanted), len(cumulative) - 1))
            first, last = cumulative[index - 1 : index + 1]
            blend = (wanted - first) / (last - first) if last > first else 0.0
            parameters.append(
                guide.parameters[index - 1]
                + blend * (guide.parameters[index] - guide.parameters[index - 1])
            )
            preceding += weight
        return cls(
            tuple(guide.sample(u)[0] for u in parameters),
            weights,
            tuple(parameters),
            guide.distances[-1],
        )

    def score(self, pieces: tuple[PlacedPiece, ...]) -> float:
        """
        Return dimensionless weighted squared position error with fixed feature correspondence.
        """
        actual = centers(pieces)
        if len(actual) != len(self.targets):
            raise ValueError("Guide placement cannot silently change feature count")
        return math.fsum(
            weight * dot(delta, delta) / self.scale_mm**2
            for point, target, weight in zip(actual, self.targets, self.weights)
            for delta in (difference(point, target),)
        )
