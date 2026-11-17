"""
Bind encoded uniform authoring knots to their exact requested physical phase partition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class UniformPhaseChart:
    """
    Retain both sides of a piecewise affine, increasing source-to-material parameter map.

    Original controls use encoded phase knots. Requested material cuts use the
    exact rational angle*i/count partition. On each cell the same unit parameter
    evaluates both; no spatial control, material label or curve is changed.
    """

    encoded: tuple[Fraction, ...]
    nominal: tuple[Fraction, ...]

    @property
    def maximum_phase_error_radians(self) -> Fraction:
        """
        Bound the coordinate difference over every cell by its endpoint extrema.
        """
        return max(abs(a - b) for a, b in zip(self.encoded, self.nominal))


def uniform_phase_chart(angle_radians: float, knots: tuple[float, ...]) -> UniformPhaseChart:
    """
    Recover the exact requested partition only from the unchanged uniform cubic authoring basis.

    Confirm the complete encoded grid and multiplicities, not proximity to an
    endpoint. Nonuniform, altered or invalid bases are rejected without snapping.
    Both affine cell derivatives are positive. Evaluating unchanged polynomial
    controls against nominal material increments includes the encoding Jacobian
    in the existing absolute speed-error bound; no extra tolerance is introduced.
    This map does not erase spatial seam gaps or qualify native correspondence.
    """
    if (
        type(angle_radians) not in (int, float)
        or not math.isfinite(angle_radians)
        or angle_radians <= 0
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in knots)
    ):
        raise ValueError("Positive finite requested phase and finite source knots required")
    encoded = tuple(dict.fromkeys(Fraction(value) for value in knots))
    count = len(encoded) - 1
    if count < 1 or any(a >= b for a, b in zip(encoded, encoded[1:])):
        raise ValueError("Complete strictly increasing source phase partition required")
    expected = tuple(Fraction(angle_radians * i / count) for i in range(count + 1))
    basis = (
        (expected[0],) * 4
        + tuple(v for v in expected[1:-1] for _ in range(3))
        + (expected[-1],) * 4
    )
    if encoded != expected or tuple(Fraction(value) for value in knots) != basis:
        raise ValueError("Original uniform cubic phase basis required; source knots changed")
    nominal = tuple(Fraction(angle_radians) * i / count for i in range(count + 1))
    return UniformPhaseChart(encoded, nominal)
