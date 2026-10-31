"""
Measure local rigid-sweep collapse using exact circular arcs and helix transport.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import Vector3, cross, dot, unit
from devtools.ribbon_analysis.isometric_fold import CylindricalFold

from .geometry import FoldRoute


@dataclass(frozen=True)
class ProfileArc:
    """
    Retain a circular contour arc in the departure profile's width/normal plane.
    """

    center: tuple[float, float]
    radius: float
    low: float
    high: float

    def __post_init__(self) -> None:
        """
        Refuse nonfinite, reversed or multiple-revolution arc intervals.
        """
        if (
            not all(
                math.isfinite(value) for value in (*self.center, self.radius, self.low, self.high)
            )
            or self.radius <= 0
            or not 0 <= self.high - self.low <= 2 * math.pi
        ):
            raise ValueError("A profile arc requires finite regular circular geometry.")

    def point(self, angle: float) -> tuple[float, float]:
        """
        Locate a point without modifying the archived profile geometry.
        """
        return (
            self.center[0] + self.radius * math.cos(angle),
            self.center[1] + self.radius * math.sin(angle),
        )


def equivalent_angle(angle: float, low: float, high: float) -> float | None:
    """
    Locate the first equivalent angle inside a closed unwrapped interval.
    """
    candidate = angle + 2 * math.pi * math.ceil((low - angle) / (2 * math.pi))
    return candidate if low <= candidate <= high else None


def maximum_support(
    arcs: tuple[ProfileArc, ...], low: float, high: float
) -> tuple[float, float, tuple[float, float]]:
    """
    Maximize contour reach over a continuous interval of curvature directions.

    Extrema occur at a direction endpoint, arc endpoint or radial stationary
    contour point. Enumerate all three, including wrapped intervals; no angular
    sampling or enclosing disk is used. Return reach, direction and contour point.
    """
    if not arcs or not all(math.isfinite(value) for value in (low, high)) or low > high:
        raise ValueError("A contour and ordered finite direction interval are required.")
    candidates: list[tuple[float, float, tuple[float, float]]] = []

    def retain(witness: tuple[float, float], direction_angle: float) -> None:
        """
        Preserve a physical witness for each possible extremum.
        """
        reach = witness[0] * math.cos(direction_angle) + witness[1] * math.sin(direction_angle)
        candidates.append((reach, direction_angle, witness))

    for arc in arcs:
        for direction in (low, high):
            angles = [arc.low, arc.high]
            stationary = equivalent_angle(direction, arc.low, arc.high)
            if stationary is not None:
                angles.append(stationary)
            for angle in angles:
                retain(arc.point(angle), direction)
        for angle in (arc.low, arc.high):
            point = arc.point(angle)
            direction = equivalent_angle(math.atan2(point[1], point[0]), low, high)
            if direction is not None:
                retain(point, direction)
        if math.hypot(*arc.center) > 0:
            phase = math.atan2(arc.center[1], arc.center[0])
            for angle in (phase, phase + math.pi):
                stationary = equivalent_angle(angle, arc.low, arc.high)
                if stationary is not None:
                    point = arc.point(stationary)
                    direction = equivalent_angle(math.atan2(point[1], point[0]), low, high)
                    if direction is not None:
                        retain(point, direction)
    return max(candidates, key=lambda item: item[0])


def rotate(vector: Vector3, axis: Vector3, angle: float) -> Vector3:
    """
    Apply Rodrigues rotation about a unit axis, preserving orientation and length.
    """
    cosine, sine = math.cos(angle), math.sin(angle)
    return (
        Vector3(vector.x * cosine, vector.y * cosine, vector.z * cosine)
        .translated(cross(axis, vector), sine)
        .translated(axis, dot(axis, vector) * (1 - cosine))
    )


@dataclass(frozen=True)
class SweepTurn:
    """
    Preserve one continuous local limit and its actual contour/direction witness.
    """

    piece_index: int
    label: str
    cylinder_radius_mm: float
    center_radius_mm: float
    maximum_reach_mm: float
    maximum_utilization: float
    material_fraction: float
    contour_point_mm: tuple[float, float]


def inspect_sweep(
    route: FoldRoute, arcs: tuple[ProfileArc, ...], *, reverse: bool = True
) -> tuple[tuple[SweepTurn, ...], Vector3]:
    """
    Transport the departure profile exactly across a G1 plane/cylinder chain.

    A helical tangent rotates about its fixed cylinder axis A. Remove the axial
    spin alpha*(A dot T) to obtain parallel transport. Curvature direction in
    that transported profile changes linearly, permitting continuous arc support
    extrema. Straight intervals add no rotation. This models an ordinary rigid
    perpendicular sweep, not equal native material lengths or global clearance.
    """
    width = route.targets.end_width if reverse else route.targets.start_width
    sequence = list(enumerate(route.pieces))
    if reverse:
        sequence.reverse()
    turns = []
    for index, placed in sequence:
        geometry = placed.geometry
        if not isinstance(geometry, CylindricalFold):
            continue
        angle = abs(geometry.angle_radians)
        sign = math.copysign(1, geometry.angle_radians)
        cosine, sine = math.cos(geometry.bank_radians), math.sin(geometry.bank_radians)
        begin, finish = (angle, 0.0) if reverse else (0.0, angle)
        velocity = placed.surface(1.0 if reverse else 0.0, 0.0)[1]
        tangent = unit(velocity)
        if reverse:
            tangent = Vector3(-tangent.x, -tangent.y, -tangent.z)
        axis = placed.pose.direction(Vector3(-sine, cosine, 0))
        normal = placed.pose.direction(
            Vector3(-cosine * math.sin(begin), -sine * math.sin(begin), sign * math.cos(begin))
        )
        phase = math.atan2(dot(normal, cross(tangent, width)), dot(normal, width))
        alpha = -sign * (finish - begin)
        beta = -alpha * dot(axis, tangent)
        reach, direction, point = maximum_support(
            arcs, min(phase, phase - beta), max(phase, phase - beta)
        )
        portion = (phase - direction) / beta if abs(beta) > 1e-14 else 0.5
        theta = begin + (finish - begin) * min(1.0, max(0.0, portion))
        low, high = geometry.bend_interval(0)
        center_radius = geometry.radius_mm / cosine**2
        turns.append(
            SweepTurn(
                index,
                placed.label,
                geometry.radius_mm,
                center_radius,
                reach,
                reach / center_radius,
                low + (high - low) * theta / angle,
                point,
            )
        )
        width = unit(rotate(rotate(width, tangent, beta), axis, alpha))
    return tuple(turns), width
