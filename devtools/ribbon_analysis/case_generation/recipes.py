"""
Compose common scenario intents into boundary poses without prescribing a path.

The displacement formulas author targets only. In particular,a lateral event's
pose construction is NOT a feasible ribbon arc,and a twist's straight chord is
NOT a straight centerline constraint. The solver must discover the interior.
"""

from __future__ import annotations

import math

from cable_bundler.routing.geometry import Vector3, cross, dot

from ..contracts import Targets
from .models import Event

BASICS = (
    Event("u", 180),
    Event("s", 45),
    Event("lateral", 45),
    Event("lateral", 90),
    Event("lateral", 180),
    Event("twist", 45),
    Event("twist", 90),
    Event("twist", 180),
)
COMBINATIONS = (
    (BASICS[0], BASICS[6]),
    (BASICS[1], BASICS[2]),
    (BASICS[3], BASICS[5]),
    (BASICS[2], BASICS[7], BASICS[1]),
)


def rotate(vector: Vector3, axis: Vector3, radians: float) -> Vector3:
    """
    Rotate a vector around a unit axis without changing material ordering.
    """
    c, s = math.cos(radians), math.sin(radians)
    product = cross(axis, vector)
    along = dot(axis, vector) * (1 - c)
    return Vector3(
        vector.x * c + product.x * s + axis.x * along,
        vector.y * c + product.y * s + axis.y * along,
        vector.z * c + product.z * s + axis.z * along,
    )


def compile_pose(
    name: str,
    events: tuple[Event, ...],
    *,
    lines: int = 13,
    diameter_mm: float = 1.0,
    radius_widths: float = 2.5,
) -> Targets:
    """
    Compose local end poses with neutral spacing,then return only fixed targets.

    Each event acts in the preceding endpoint frame. S has two opposing bend
    intents. No intermediate waypoint,trajectory or witness reaches the solver.
    """
    if not events or not math.isfinite(radius_widths) or radius_widths <= 0:
        raise ValueError("Supply events and a positive finite radius reference.")
    width = lines * diameter_mm
    position = Vector3(2 * width, 0, 0)
    tangent, lateral = Vector3(1, 0, 0), Vector3(0, 1, 0)

    def turn(degrees: float, lateral_turn: bool) -> None:
        """
        Advance a pose construction,without declaring its arc physically feasible.
        """
        nonlocal position, tangent, lateral
        theta = math.radians(degrees)
        normal = lateral if lateral_turn else cross(tangent, lateral)
        radius = radius_widths * width
        position = position.translated(tangent, radius * math.sin(abs(theta)))
        position = position.translated(normal, math.copysign(radius * (1 - math.cos(theta)), theta))
        axis = cross(tangent, lateral) if lateral_turn else lateral
        angle = theta if lateral_turn else -theta
        tangent = rotate(tangent, axis, angle)
        lateral = rotate(lateral, axis, angle)

    for index, event in enumerate(events):
        if index:
            position = position.translated(tangent, 1.5 * width)
        if event.kind == "twist":
            position = position.translated(tangent, 6 * width)
            lateral = rotate(lateral, tangent, math.radians(event.degrees))
        elif event.kind == "s":
            turn(event.degrees, False)
            turn(-event.degrees, False)
        else:
            turn(event.degrees, event.kind == "lateral")
    position = position.translated(tangent, 2 * width)
    return Targets.capture(
        Targets(
            name,
            Vector3(0, 0, 0),
            position,
            Vector3(1, 0, 0),
            tangent,
            Vector3(0, 1, 0),
            lateral,
            lines,
            diameter_mm,
        )
    )
