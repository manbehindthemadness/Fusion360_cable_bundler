"""
Derive ordered material-frame references from the pre-planner without angle or position guesses.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from devtools.ribbon_analysis.contracts import Targets
from experiments.experiment_ribbon_fold_route.geometry import Pose
from experiments.experiment_ribbon_reduced_joints.kinematics import rotate
from experiments.experiment_ribbon_spline_guide.guide import Guide


def transport(width: Vector3, before: Vector3, after: Vector3) -> Vector3:
    """
    Carry width through the minimal tangent rotation, rejecting unresolved opposite samples.
    """
    axis = cross(before, after)
    sine, cosine = magnitude(axis), dot(before, after)
    if sine <= 1e-12:
        if cosine < 0:
            raise ValueError("Guide tangent reversal is unresolved between adjacent samples")
        carried = width
    else:
        carried = rotate(width, unit(axis), math.atan2(sine, cosine))
    return unit(carried.translated(after, -dot(carried, after)))


@dataclass(frozen=True)
class Frames:
    """
    Freeze sampled parallel transport and a deterministic endpoint-roll interpolation.

    This is a placement reference, not a physical ribbon following the cubic.
    Endpoint-only inputs specify no extra winding; shortest signed terminal roll
    is a declared convention, with positive pi chosen at an ambiguous half-turn.
    """

    targets: Targets
    guide: Guide
    widths: tuple[Vector3, ...]
    turns: tuple[float, ...]
    terminal_roll: float

    @classmethod
    def create(cls, targets: Targets) -> Frames:
        """
        Build257ordered tangent/width references, rejecting sampled stationary tangents.
        """
        return cls.from_guide(targets, Guide.create(targets))

    @classmethod
    def from_guide(cls, targets: Targets, guide: Guide) -> Frames:
        """
        Transport the same ordered frames along an explicit endpoint-preserving guide.

        A spatial deviation changes the interior reference, never the fixed cap
        positions or directed tangents. The257sample and shortest terminal-roll
        conventions remain identical to ordinary construction.
        """
        if len(guide.parameters) != 257 or len(guide.distances) != 257:
            raise ValueError("Guide frames require257ordered reference samples")
        velocities = tuple(guide.sample(u)[1] for u in guide.parameters)
        if any(magnitude(v) <= 1e-12 for v in velocities):
            raise ValueError("Stationary guide tangent leaves insertion unresolved")
        tangents = tuple(unit(v) for v in velocities)
        if (
            magnitude(difference(guide.sample(0)[0], targets.start)) > 1e-10
            or magnitude(difference(guide.sample(1)[0], targets.end)) > 1e-10
            or magnitude(difference(tangents[0], targets.start_tangent)) > 1e-10
            or magnitude(difference(tangents[-1], targets.end_tangent)) > 1e-10
        ):
            raise ValueError("A deviated guide must preserve both ordered endpoint poses")
        widths, turns = [targets.start_width], [0.0]
        for before, after in zip(tangents, tangents[1:]):
            widths.append(transport(widths[-1], before, after))
            turns.append(
                turns[-1] + math.atan2(magnitude(cross(before, after)), dot(before, after))
            )
        roll = math.atan2(
            dot(cross(widths[-1], targets.end_width), tangents[-1]),
            dot(widths[-1], targets.end_width),
        )
        if abs(abs(roll) - math.pi) <= 1e-12:
            roll = math.pi
        return cls(targets, guide, tuple(widths), tuple(turns), roll)

    def at(self, parameter: float) -> Pose:
        """
        Evaluate an ordered guide point/tangent and its transported, terminal-corrected width.
        """
        if not math.isfinite(parameter) or not 0 <= parameter <= 1:
            raise ValueError("Guide frame parameter must lie in[0,1]")
        point, velocity = self.guide.sample(parameter)
        if magnitude(velocity) <= 1e-12:
            raise ValueError("Stationary insertion tangent")
        tangent = unit(velocity)
        index = max(1, min(bisect_left(self.guide.parameters, parameter), 256))
        low, high = self.guide.parameters[index - 1 : index + 1]
        blend = (parameter - low) / (high - low)
        previous = unit(self.guide.sample(low)[1])
        width = transport(self.widths[index - 1], previous, tangent)
        distance = self.guide.distances[index - 1] + blend * (
            self.guide.distances[index] - self.guide.distances[index - 1]
        )
        width = rotate(width, tangent, self.terminal_roll * distance / self.guide.distances[-1])
        return Pose(point, tangent, width)

    def inserted_parameters(self) -> tuple[float, float] | None:
        """
        Split the stronger guide-turn half at its cumulative-turn midpoint; ties choose entry.

        Keep the baseline parameter1/2. Exactly one additional station is derived;
        no alternative station, heading grid or improvement-angle candidate runs.
        """
        first, last = self.turns[128], self.turns[-1] - self.turns[128]
        if max(first, last) <= 1e-12:
            return None
        begin, end = (0, 128) if first >= last - 1e-12 else (128, 256)
        parameter = self.turn_parameter((self.turns[begin] + self.turns[end]) / 2, begin, end)
        ordered = sorted((parameter, 0.5))
        return ordered[0], ordered[1]

    def turn_parameter(self, wanted: float, begin: int = 0, end: int = 256) -> float:
        """
        Interpolate one ordered cumulative-turn value within the specified sampled guide interval.

        The supplied turn must lie within that interval. Flat sampled intervals
        retain their earlier parameter, without inventing an additional direction.
        """
        if (
            not 0 <= begin < end < len(self.turns)
            or not self.turns[begin] <= wanted <= self.turns[end]
        ):
            raise ValueError("Supply a cumulative turn within an ordered guide interval")
        index = max(begin + 1, min(bisect_left(self.turns, wanted, begin, end + 1), end))
        a, b = self.turns[index - 1 : index + 1]
        fraction = (wanted - a) / (b - a) if b > a else 0.0
        return self.guide.parameters[index - 1] + fraction * (
            self.guide.parameters[index] - self.guide.parameters[index - 1]
        )
