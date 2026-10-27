"""
Turn remote full-width proximity witnesses into bounded separating-plane guidance.

Planes are routing hypotheses,not physical laws or continuous contact certificates.
They steer compatible field coordinates;they never move sampled mesh vertices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

# noinspection PyProtectedMember
from cable_bundler.routing.avoidance import _segment_distance
from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.edge_clearance import Ruling
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .contact import audit


@dataclass(frozen=True)
class DistancePair:
    """
    Penalize actual full-width segment distance without preserving a separating side.

    Distance is nonsmooth at changes of closest feature and exact intersections.
    This is sampled guidance,not a continuous surface or swept-update certificate.
    """

    first_u: float
    second_u: float
    thickness_mm: float

    def margin(self, first: tuple[Vector3, Vector3], second: tuple[Vector3, Vector3]) -> float:
        """
        Return closest segment distance minus thickness,independent of orientation.
        """
        distance, _, _ = _segment_distance(first[0], first[1], second[0], second[1])
        return distance - self.thickness_mm

    def violation(self, path: CompatiblePath) -> float:
        """
        Compare current full-width segments at the retained material coordinates.
        """
        a, b = _segments(path, self.first_u, self.second_u)
        return max(0.0, -self.margin(a, b)) / self.thickness_mm


def _segments(
    path: CompatiblePath, first_u: float, second_u: float
) -> tuple[tuple[Vector3, Vector3], tuple[Vector3, Vector3]]:
    """
    Evaluate full-width segment endpoints for one retained material pair.
    """
    half = path.field.half_width_mm
    return (
        (path.lane(first_u, -half)[0], path.lane(first_u, half)[0]),
        (path.lane(second_u, -half)[0], path.lane(second_u, half)[0]),
    )


@dataclass(frozen=True)
class PlanePair:
    """
    Request separation of two entire ruling segments along a fixed unit direction.

    The thickness offset conservatively treats each ruling as a radiusD/2capsule.
    A positive margin certifies only this sampled pair along this chosen direction.
    Rulings between samples and evolving surface normals require separate checks.
    """

    first_u: float
    second_u: float
    normal: Vector3
    thickness_mm: float

    def __post_init__(self) -> None:
        """
        Refuse invalid material coordinates,nonunit directions or thickness.
        """
        if (
            not 0 <= self.first_u < self.second_u <= 1
            or not math.isfinite(self.thickness_mm)
            or self.thickness_mm <= 0
            or not math.isfinite(magnitude(self.normal))
            or abs(magnitude(self.normal) - 1) > 1e-8
        ):
            raise ValueError(
                "A plane pair needs ordered fractions,unit normal and positive thickness."
            )

    def margin(self, first: tuple[Vector3, Vector3], second: tuple[Vector3, Vector3]) -> float:
        """
        Measure the projected gap between complete segments minus their thickness.
        """
        origin = second[0]
        left = min(dot(self.normal, difference(p, origin)) for p in first)
        right = max(dot(self.normal, difference(p, origin)) for p in second)
        return left - right - self.thickness_mm

    def violation(self, path: CompatiblePath) -> float:
        """
        Return dimensionless clearance deficit using the current compatible rulings.
        """
        first, second = _segments(path, self.first_u, self.second_u)
        return max(0.0, -self.margin(first, second)) / self.thickness_mm


def from_witness(
    first: Ruling,
    second: Ruling,
    closest_points: tuple[Vector3, Vector3],
    thickness_mm: float,
) -> PlanePair:
    """
    Prefer closest-point separation,using a deterministic cross-ruling fallback.

    At exact coincident parallel rulings no separating side is inferred. Reject
    that ambiguity rather than invent a world-axis displacement. The cross-ruling
    fallback at a transverse intersection chooses one side as a search hypothesis.
    """
    direction = difference(*closest_points)
    if magnitude(direction) <= 1e-10 * thickness_mm:
        direction = cross(difference(first.end, first.start), difference(second.end, second.start))
        if magnitude(direction) <= 1e-12:
            raise ValueError("Coincident parallel rulings need an explicit alternative route.")
    return PlanePair(first.fraction, second.fraction, unit(direction), thickness_mm)


def distance_from_witness(
    first: Ruling,
    second: Ruling,
    _closest_points: tuple[Vector3, Vector3],
    thickness_mm: float,
) -> DistancePair:
    """
    Freeze material fractions only,recomputing distance as geometry changes.
    """
    return DistancePair(first.fraction, second.fraction, thickness_mm)


@dataclass
class ContactGuide:
    """
    Retain up to eight witness planes,keeping residual dimensions stable in a fit.

    Observe only between linearizations or before rescoring both trial/current
    paths. Never discover planes independently inside finite-difference columns.
    Neighboring witnesses within1/32of both fractions share one routing hypothesis.
    Reaching eight planes stops adding guidance;final independent screening still
    rejects unhandled contacts. No barrier or collision-free-update claim is made.
    """

    case: EndpointCase
    checkpoint: Callable[[], None]
    factory: Callable[
        [Ruling, Ruling, tuple[Vector3, Vector3], float], PlanePair | DistancePair
    ] = from_witness
    constraints: list[PlanePair | DistancePair] = field(default_factory=list)
    observations: int = 0

    def observe(self, path: CompatiblePath) -> bool:
        """
        Add the closest eligible near-contact witness when its region is new.
        """
        self.observations += 1
        result, samples = audit(self.case, path, self.checkpoint)
        witness = result["witness"]
        if witness is None or len(self.constraints) >= 8:
            return False
        first: Ruling = samples[witness["stations"][0]]
        second: Ruling = samples[witness["stations"][1]]
        if any(
            abs(p.first_u - first.fraction) <= 1 / 32
            and abs(p.second_u - second.fraction) <= 1 / 32
            for p in self.constraints
        ):
            return False
        points = tuple(Vector3(*p) for p in witness["points_mm"])
        self.constraints.append(
            self.factory(first, second, (points[0], points[1]), self.case.diameter_mm)
        )
        return True

    def residuals(self, path: CompatiblePath) -> tuple[float, ...]:
        """
        Return eight fixed slots,with zeros for unused guidance hypotheses.
        """
        return tuple(p.violation(path) for p in self.constraints) + (0.0,) * (
            8 - len(self.constraints)
        )
