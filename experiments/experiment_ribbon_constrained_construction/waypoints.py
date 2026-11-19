"""
Describe soft spatial waypoint regions for an ordered finite-radius hinge chain.

Only connector frames are exact targets. Waypoint balls guide material landmarks
without prescribing intermediate frames. Their feasibility is not assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, difference, magnitude
from devtools.ribbon_analysis.prepath import controls
from experiments.experiment_ribbon_bend_relocation.model import MovableBends
from experiments.experiment_ribbon_fold_route.geometry import FoldRoute
from experiments.experiment_ribbon_spatial_inspection.landmarks import Landmark, locate
from experiments.experiment_ribbon_terminal_hardware.reversal_model import ordered_residual


class Hinges(MovableBends):
    """
    Free fold angles, crease banks and straight slots with exact ordered-cap residuals.

    Radius, width and fold order stay fixed. Unlike SignedJoints this model does
    not lock turn signs. A vanished fold cannot silently inherit a different
    landmark identity; waypoint evaluation explicitly rejects that topology.
    """

    def residual(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Measure full ordered orientation, including nonzero half-turn mismatch.
        """
        return ordered_residual(self, values)


@dataclass(frozen=True)
class Waypoint:
    """
    Associate one ordered material landmark with a finite spatial preference ball.
    """

    landmark: Landmark
    center: Vector3
    radius_mm: float

    def __post_init__(self) -> None:
        """
        Reject malformed regions before evaluating or differentiating material.
        """
        if (
            not math.isfinite(self.radius_mm)
            or self.radius_mm <= 0
            or any(not math.isfinite(v) for v in (self.center.x, self.center.y, self.center.z))
        ):
            raise ValueError("Waypoint regions require finite centers and positive radii")

    def point(self, route: FoldRoute) -> Vector3:
        """
        Resolve the same ordered fold location without nearest-point substitution.
        """
        found = locate(route, self.landmark)
        if found is None:
            raise ValueError("Waypoint landmark disappeared from the ordered hinge chain")
        index, fraction = found
        return route.pieces[index].surface(fraction, 0.0)[0]

    def excess(self, point: Vector3) -> Vector3:
        """
        Return radial displacement outside the ball, with zero cost inside it.
        """
        offset = difference(point, self.center)
        distance = magnitude(offset)
        return (
            offset.translated(offset, -self.radius_mm / distance)
            if distance > self.radius_mm
            else Vector3(0, 0, 0)
        )


def approaches(route: FoldRoute, split: int) -> tuple[Waypoint, Waypoint]:
    """
    Place two soft regions at the fixed endpoint guide's outward approach handles.

    The split identifies the last departure hinge and first arrival hinge in an
    existing two-group construction. Region radius is the original half width;
    this is a planning convention, not a required physical corridor or proof.
    """
    count = len(Hinges(route).folds)
    if type(split) is not int or not 0 < split < count:
        raise ValueError("Split two nonempty ordered terminal hinge groups")
    _, start, end, _ = controls(route.targets)
    return (
        Waypoint(Landmark("fold", split - 1, 1.0, count), start, route.half_width_mm),
        Waypoint(Landmark("fold", split, 0.0, count), end, route.half_width_mm),
    )


@dataclass(frozen=True)
class Objective:
    """
    Combine waypoint-region excess with full material length at one immutable scale.
    """

    model: Hinges
    waypoints: tuple[Waypoint, ...]

    def observations(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Return normalized world landmark positions and complete material length.
        """
        route = self.model.route(values)
        if route is None:
            raise ValueError("Waypoint kinematics requires nonempty material")
        points = tuple(waypoint.point(route) for waypoint in self.waypoints)
        scale = self.model.scale
        return tuple(v / scale for p in points for v in (p.x, p.y, p.z)) + (
            route.material_length_mm / scale,
        )

    def errors(self, values: tuple[float, ...]) -> tuple[float, ...]:
        """
        Return the objective's radial residuals and normalized total length.

        Multiplying position sensitivities by these radial excesses gives the
        exact first derivative of squared distance to each ball. Inside a ball
        its position preference vanishes; length and cap constraints remain.
        """
        route = self.model.route(values)
        if route is None:
            raise ValueError("Waypoint kinematics requires nonempty material")
        excesses = tuple(w.excess(w.point(route)) for w in self.waypoints)
        scale = self.model.scale
        return tuple(v / scale for p in excesses for v in (p.x, p.y, p.z)) + (
            route.material_length_mm / scale,
        )

    def score(self, values: tuple[float, ...]) -> float:
        """
        Measure the declared dimensionless squared planning objective.
        """
        return math.fsum(v * v for v in self.errors(values)) / 2
