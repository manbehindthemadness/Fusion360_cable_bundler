"""
Compose original native UV traces with explicit rational surfaces without model-curve fitting or parameter inference.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass, field
from fractions import Fraction
from math import comb

from artifacts.verification.resume3204.polynomial import Polynomial, add, multiply

from .exact_frame import Point
from .native_material_chart import NativeSurfaceSnapshot
from .native_trim_boundary import NativeTrimCurve
from .spatial_frame import split_at


def _factors(
    degree: int, numerator: Polynomial, denominator: Polynomial, checkpoint: Callable[[], None]
) -> tuple[Polynomial, ...]:
    """
    Clear one positive rational coordinate's Bernstein basis denominator exactly.
    """
    opposite = add(denominator, numerator, Fraction(-1))
    output = []
    for index in range(degree + 1):
        checkpoint()
        value = (Fraction(comb(degree, index)),)
        for factor in (numerator,) * index + (opposite,) * (degree - index):
            value = multiply(value, factor)
        output.append(value)
    return tuple(output)


@dataclass(frozen=True)
class NativeSurfaceTrace:
    """
    Own an exact whole-curve homogeneous world image under the SAME surface and UV trace.

    Both surface directions must be single clamped Bernstein spans. Original
    UV controls must lie in that natural rectangle, so every cleared basis
    factor is nonnegative and the resulting denominator coefficients positive.
    This is algebraic composition, not a sampled approximation or a material
    chart. Capture adapters establish actual face/coedge provenance first.
    """

    surface: NativeSurfaceSnapshot
    curve: NativeTrimCurve
    checkpoint: InitVar[Callable[[], None]]
    numerators: tuple[Polynomial, ...] = field(init=False)
    denominator: Polynomial = field(init=False)

    def __post_init__(self, checkpoint: Callable[[], None]) -> None:
        """
        Derive all image coefficients exactly, rejecting extrapolated or unsupported surface domains.
        """
        checkpoint()
        surface, curve = self.surface, self.curve
        factors = []
        for axis, degree, knots, count in (
            (0, surface.degree_u, surface.knots_u, len(surface.rows)),
            (1, surface.degree_v, surface.knots_v, len(surface.rows[0])),
        ):
            low, high = knots[degree], knots[-degree - 1]
            if (
                count != degree + 1
                or low >= high
                or knots != (low,) * (degree + 1) + (high,) * (degree + 1)
                or any(not low <= p[axis] <= high for p in curve.controls)
            ):
                raise ValueError(
                    "Single-span natural domains containing the whole UV control hull required"
                )
            coordinate = tuple(
                (p[axis] - low) * w / (high - low) for p, w in zip(curve.controls, curve.weights)
            )
            factors.append(_factors(degree, coordinate, curve.weights, checkpoint))
        result = [(Fraction(0),)] * 4
        for i, first in enumerate(factors[0]):
            for j, second in enumerate(factors[1]):
                checkpoint()
                basis = multiply(first, second)
                weight = surface.weights[i][j]
                for k, coefficient in enumerate((*surface.rows[i][j], Fraction(1))):
                    result[k] = add(result[k], tuple(x * weight * coefficient for x in basis))
        if min(result[3]) <= 0:
            raise ValueError("Positive complete composed denominator coefficients required")
        object.__setattr__(self, "numerators", tuple(result[:3]))
        object.__setattr__(self, "denominator", result[3])
        checkpoint()

    def affine_numerator(self, gradient: Point, offset: Fraction) -> Polynomial:
        """
        Return the exact numerator of one world-affine functional without modifying coordinates.
        """
        if len(gradient) != 3 or any(type(x) is not Fraction for x in (*gradient, offset)):
            raise ValueError("An exact world gradient and offset required")
        result = tuple(offset * x for x in self.denominator)
        for coefficient, values in zip(gradient, self.numerators):
            result = add(result, values, coefficient)
        return result

    def point(self, parameter: Fraction, checkpoint: Callable[[], None]) -> Point:
        """
        Evaluate the exact image at a unit trace coordinate without assigning native-edge or material parameters.
        """
        checkpoint()
        if type(parameter) is not Fraction or not 0 <= parameter <= 1:
            raise ValueError("An exact unit trace parameter required")
        denominator = split_at(self.denominator, parameter)[0][-1]
        result = tuple(
            split_at(values, parameter)[0][-1] / denominator for values in self.numerators
        )
        checkpoint()
        return result
