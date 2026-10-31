"""
Share exact Bernstein degree elevation across boundary geometry experiments.
"""

from __future__ import annotations

from cable_bundler.routing.geometry import Vector3, difference


def septic_cap_controls(
    point: Vector3, velocity: Vector3, acceleration: Vector3, jerk: Vector3
) -> tuple[Vector3, ...]:
    """
    Convert endpoint derivatives into the first four degree-seven controls.
    """
    return (
        point,
        point.translated(velocity, 1 / 7),
        point.translated(velocity, 2 / 7).translated(acceleration, 1 / 42),
        point.translated(velocity, 3 / 7)
        .translated(acceleration, 1 / 14)
        .translated(jerk, 1 / 210),
    )


def elevate_controls(points: tuple[Vector3, ...], degree: int) -> tuple[Vector3, ...]:
    """
    Increase polynomial degree without changing the curve or its parameter derivatives.

    Require a nonconstant control polygon and an integer degree no lower than its
    current degree. This changes representation only, never chooses a route.
    """
    if (
        len(points) < 2
        or isinstance(degree, bool)
        or not isinstance(degree, int)
        or degree < len(points) - 1
    ):
        raise ValueError(
            "Degree elevation requires a nonconstant polygon and a nondecreasing degree."
        )
    while len(points) <= degree:
        count = len(points)
        interior = tuple(
            points[i].translated(difference(points[i - 1], points[i]), i / count)
            for i in range(1, count)
        )
        points = (points[0], *interior, points[-1])
    return points
