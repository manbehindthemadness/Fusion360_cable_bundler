"""
Move a frozen edge's shape while preserving both ordered target poses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, difference, magnitude, unit
from devtools.ribbon_analysis.bernstein import elevate_controls
from devtools.ribbon_analysis.contracts import Targets
from devtools.ribbon_analysis.edge_frames import ruling_kinematics
from experiments.experiment_ribbon_cap_transition.edge_first import BoundaryCurve
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

ZERO = Vector3(0, 0, 0)


def elevate(curve: BoundaryCurve) -> BoundaryCurve:
    """
    Preserve an existing polynomial exactly while exposing four interior controls.
    """
    return BoundaryCurve(elevate_controls(curve.points, 11))


def _cap(
    point: Vector3, velocity: Vector3, acceleration: Vector3, jerk: Vector3
) -> tuple[Vector3, ...]:
    """
    Encode position and three derivatives as the first four degree-eleven controls.
    """
    return (
        point,
        point.translated(velocity, 1 / 11),
        point.translated(velocity, 2 / 11).translated(acceleration, 1 / 110),
        point.translated(velocity, 3 / 11)
        .translated(acceleration, 3 / 110)
        .translated(jerk, 1 / 990),
    )


@dataclass(frozen=True)
class EdgeChart:
    """
    Describe local deviations of a supplied curve, never a bank of route guesses.

    Four log parameters vary terminal speeds and bend magnitudes. Twelve coordinates
    move interior controls in chord units. Directions, ordering, cap torsion and fixed
    positions remain inherited from the supplied geometry; no endpoint is snapped.
    """

    case: EndpointCase
    original: BoundaryCurve

    def __post_init__(self) -> None:
        """
        Require a finite ribbon edge attached to the corresponding ordered target sides.
        """
        Targets.capture(self.case)
        if self.case.lines < 2:
            raise ValueError("This paired material-strip prototype requires multiple conductors.")
        if any(
            not math.isfinite(value)
            for point in self.original.points
            for value in (point.x, point.y, point.z)
        ):
            raise ValueError("Original edge controls must be finite.")
        half = self.case.lines * self.case.diameter_mm / 2 + self.case.diameter_mm * 0.1
        chord = difference(self.original.points[-1], self.original.points[0])
        straight = all(
            magnitude(cross(difference(point, self.original.points[0]), chord)) <= 1e-10
            for point in self.original.points
        )
        for fraction, center, tangent, width in (
            (0.0, self.case.start, self.case.start_tangent, self.case.start_width),
            (1.0, self.case.end, self.case.end_tangent, self.case.end_width),
        ):
            point, velocity, acceleration, jerk, snap = self.original.jet(fraction)
            if magnitude(difference(point, center.translated(width, half))) > 1e-8:
                raise ValueError("The supplied A edge does not match its ordered target side.")
            if (
                magnitude(velocity) <= 1e-10
                or magnitude(difference(unit(velocity), tangent)) > 1e-8
            ):
                raise ValueError("The supplied edge tangent disagrees with its target.")
            if straight:
                if magnitude(difference(self.case.start_width, self.case.end_width)) > 1e-8:
                    raise ValueError("A straight edge needs a consistent explicit width frame.")
            else:
                observed = ruling_kinematics(velocity, acceleration, jerk, snap)
                if magnitude(difference(observed.width, width)) > 1e-8 or abs(observed.eta) > 1e-8:
                    raise ValueError("The supplied edge cap frame disagrees with its target.")

    def curve(self, values: tuple[float, ...]) -> BoundaryCurve:
        """
        Return one endpoint-preserving deviation, requiring sixteen finite coordinates.
        """
        if len(values) != 16 or not all(math.isfinite(value) for value in values):
            raise ValueError("A paired-edge deviation needs sixteen finite coordinates.")
        base = elevate(self.original)
        scale = magnitude(difference(base.points[-1], base.points[0]))
        if scale <= 1e-8:
            raise ValueError("Coincident edge targets are unsupported.")
        points = list(base.points)
        for end, fraction in enumerate((0.0, 1.0)):
            point, velocity, acceleration, jerk, _ = self.original.jet(fraction)
            speed_log, curvature_log = values[2 * end : 2 * end + 2]
            forward = 1 if end == 0 else -1
            cap = _cap(
                point,
                ZERO.translated(velocity, forward * math.exp(speed_log)),
                ZERO.translated(acceleration, math.exp(2 * speed_log + curvature_log)),
                ZERO.translated(jerk, forward * math.exp(3 * speed_log + 2 * curvature_log)),
            )
            if end == 0:
                points[:4] = cap
            else:
                points[-4:] = reversed(cap)
        for i in range(4):
            shift = Vector3(*(scale * value for value in values[4 + 3 * i : 7 + 3 * i]))
            points[4 + i] = points[4 + i].translated(shift, 1)
        return BoundaryCurve(tuple(points))
