"""
Check the equal-length restriction of rigid perpendicular profile paths exactly.
"""

from fractions import Fraction

from cable_bundler.routing.geometry import Vector3

RationalPoint = tuple[Fraction, Fraction, Fraction]


def planar_controls(points: tuple[Vector3, ...]) -> bool:
    """
    Test exact coplanarity of the supplied float control polygon.

    For a regular Frenet-framed curve, constant binormal is equivalent to planarity.
    With no lateral bending, |(r+qW)'|²=|r'|²+q²|W'|². Thus nonplanar rigid normal
    profiles necessarily lengthen both edges. This is not a general ribbon test.
    """
    if len(points) < 2:
        raise ValueError("A control polygon needs at least two points.")
    origin: RationalPoint = (Fraction(points[0].x), Fraction(points[0].y), Fraction(points[0].z))
    rows = tuple(
        (Fraction(p.x) - origin[0], Fraction(p.y) - origin[1], Fraction(p.z) - origin[2])
        for p in points[1:]
    )
    direction = next((row for row in rows if any(row)), None)
    if direction is None:
        return True
    for row in rows:
        normal = tuple(
            direction[i] * row[j] - direction[j] * row[i] for i, j in ((1, 2), (2, 0), (0, 1))
        )
        if any(normal):
            return all(
                sum((a * b for a, b in zip(normal, value)), Fraction(0)) == 0 for value in rows
            )
    return True
