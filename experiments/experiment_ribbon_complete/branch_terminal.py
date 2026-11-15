"""
Bound a planned round termination and its boundary approach against a fixed captured target.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import add, multiply

from .capture import target as validate_target
from .contracts import FixedTarget
from .curve_lengths import distance
from .spatial_certificate import cross, dot
from .spatial_transition import SpatialPatch, derive


@dataclass(frozen=True)
class TerminalCertificate:
    """
    Retain conservative distance-to-circle and approach bounds without claiming a native junction pass.
    """

    status: str
    distance_upper_mm: Fraction
    axial_upper_mm: Fraction
    radial_upper_mm: Fraction
    minimum_forward_numerator: Fraction
    maximum_cross_squared: Fraction


def certify(
    patch: SpatialPatch, target: FixedTarget, checkpoint: Callable[[], None]
) -> TerminalCertificate:
    """
    Enclose the whole terminal curve, not selected profile landmarks.

    Captured routes traverse terminal-to-cap; this boundary plan traverses
    cap-to-terminal, so the required terminal direction is explicitly negated.
    Exact polynomial projection bounds distance to the prescribed circle plane
    and radius with one combined0.01mm allowance. The existing0.001degree approach
    gate protects material-frame flow. Overlarge bounds stay unresolved.
    """
    checkpoint()
    validate_target(target)
    if patch.frame.high != Fraction(1):
        raise ValueError("Only the final global span can bind the termination")
    row = patch.rows[-1]
    weight = tuple(p[3] for p in row)
    xyz = (tuple(p[0] for p in row), tuple(p[1] for p in row), tuple(p[2] for p in row))
    point = (Fraction(target.point.x), Fraction(target.point.y), Fraction(target.point.z))
    axis = (Fraction(-target.tangent.x), Fraction(-target.tangent.y), Fraction(-target.tangent.z))
    delta = (
        add(xyz[0], weight, -point[0]),
        add(xyz[1], weight, -point[1]),
        add(xyz[2], weight, -point[2]),
    )
    axis_squared = sum((x * x for x in axis), Fraction(0))
    projection = add(
        add(tuple(x * axis[0] for x in delta[0]), tuple(x * axis[1] for x in delta[1])),
        tuple(x * axis[2] for x in delta[2]),
    )
    norm_lower = distance((Fraction(0),) * 3, axis)[0]
    if norm_lower <= 0:
        raise ValueError("Termination direction has no positive norm enclosure")
    axial = max(abs(x) for x in projection) / (min(weight) * norm_lower)
    radius = Fraction(patch.section.terminal_radius_mm)
    radial_residual = add(
        add(dot(delta, delta), multiply(projection, projection), Fraction(-1) / axis_squared),
        multiply(weight, weight),
        -(radius**2),
    )
    radial = max(abs(x) for x in radial_residual) / (min(weight) ** 2 * radius)
    last = derive(patch.rows, 0)[-1]
    derivative_xyz = (
        tuple(p[0] for p in last),
        tuple(p[1] for p in last),
        tuple(p[2] for p in last),
    )
    derivative_weight = tuple(p[3] for p in last)
    velocity_parts = tuple(
        add(multiply(derivative_xyz[k], weight), multiply(xyz[k], derivative_weight), Fraction(-1))
        for k in range(3)
    )
    velocity = (velocity_parts[0], velocity_parts[1], velocity_parts[2])
    axis_polynomials = ((axis[0],), (axis[1],), (axis[2],))
    forward = dot(velocity, axis_polynomials)
    crossed = cross(velocity, axis_polynomials)
    cross_squared = max(
        sum((crossed[k][i] ** 2 for k in range(3)), Fraction(0)) for i in range(len(crossed[0]))
    )
    minimum = min(forward)
    tangent_limit = Fraction(math.tan(math.radians(0.001)))
    status = (
        "certified"
        if axial + radial <= Fraction(1, 100)
        and minimum > 0
        and cross_squared <= (minimum * tangent_limit) ** 2
        else "unresolved"
    )
    checkpoint()
    return TerminalCertificate(status, axial + radial, axial, radial, minimum, cross_squared)
