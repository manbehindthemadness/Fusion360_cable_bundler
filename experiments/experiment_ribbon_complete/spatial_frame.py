"""
Retain explicit polynomial branch frames without normalization, target fitting or material relabeling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from artifacts.verification.resume3204.polynomial import Polynomial, derivative
from cable_bundler.routing.geometry import Vector3

from .capture import finite

Components = tuple[Polynomial, Polynomial, Polynomial]


class ChartOrientation(Enum):
    """
    Preserve the root's material handedness across every branch span.
    """

    POSITIVE = 1
    NEGATIVE = -1


def components(values: tuple[Vector3, ...]) -> Components:
    """
    Interpret the unchanged stored vector controls as exact component polynomials.
    """
    return (
        tuple(Fraction(p.x) for p in values),
        tuple(Fraction(p.y) for p in values),
        tuple(Fraction(p.z) for p in values),
    )


def split_at(values: Polynomial, parameter: Fraction) -> tuple[Polynomial, Polynomial]:
    """
    Subdivide a scalar Bernstein polynomial at an exact unit coordinate.
    """
    left, right = [values[0]], [values[-1]]
    while len(values) > 1:
        values = tuple((1 - parameter) * a + parameter * b for a, b in zip(values, values[1:]))
        left.append(values[0])
        right.append(values[-1])
    return tuple(left), tuple(reversed(right))


def restrict(values: Polynomial, low: Fraction, high: Fraction) -> Polynomial:
    """
    Reparameterize the original global shape onto a frame span without restarting the morph.
    """
    if not values or not 0 <= low < high <= 1:
        raise ValueError("A nonempty polynomial and increasing unit interval are required")
    left = split_at(values, high)[0]
    return left if low == 0 else split_at(left, low / high)[1]


@dataclass(frozen=True)
class FrameSpan:
    """
    Freeze center, width and thickness fields on one polynomial span of the global branch parameter.

    Field controls are raw physical vectors, not secretly normalized moving frames.
    Endpoint pose, lengths, no-lateral-bend, cross-section metrics and junction flow
    need their own audits. One span supports constant through quintic fields;
    unsupported representations are not geometric infeasibility declarations.
    """

    low: Fraction
    high: Fraction
    center: tuple[Vector3, ...]
    width: tuple[Vector3, ...]
    thickness: tuple[Vector3, ...]
    orientation: ChartOrientation

    def __post_init__(self) -> None:
        """
        Require a complete finite representation and explicit immutable material orientation.
        """
        if (
            type(self.low) is not Fraction
            or type(self.high) is not Fraction
            or not 0 <= self.low < self.high <= 1
            or not isinstance(self.orientation, ChartOrientation)
        ):
            raise ValueError(
                "Exact increasing global interval and root material orientation required"
            )
        for field in (self.center, self.width, self.thickness):
            if (
                not isinstance(field, tuple)
                or not 1 <= len(field) <= 6
                or not all(finite(p) for p in field)
            ):
                raise ValueError("Each frame field needs1..6finite unchanged vector controls")

    def fields(self) -> tuple[Components, Components, Components]:
        """
        Return exact raw coordinate fields in the local span parameter.
        """
        return components(self.center), components(self.width), components(self.thickness)


def differentiated(values: Components) -> Components:
    """
    Retain three-component polynomial shape while differentiating a frame field.
    """
    return derivative(values[0]), derivative(values[1]), derivative(values[2])
