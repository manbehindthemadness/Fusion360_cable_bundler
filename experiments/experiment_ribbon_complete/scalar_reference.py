"""
Enclose captured scalar values and first derivatives against analytic trigonometry independently.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from math import comb, factorial

from artifacts.verification.resume3204.polynomial import Polynomial, derivative, elevate
from artifacts.verification.resume3219.interval import Interval, fixed, trigonometry


@dataclass(frozen=True)
class ScalarReferenceBounds:
    """
    Retain whole-span value and global-phase derivative errors without differentiating a remainder bound.
    """

    sine: Fraction
    cosine: Fraction
    sine_first: Fraction
    cosine_first: Fraction
    phase_first: Fraction


def enclose(
    sine: Polynomial,
    cosine: Polynomial,
    phase: Polynomial,
    low: Fraction,
    high: Fraction,
    checkpoint: Callable[[], None],
) -> ScalarReferenceBounds:
    """
    Compare exact stored quintics with degree12 Taylor polynomials on one original interval.

    True endpoint sine/cosine use rigorous interval trigonometry. Taylor power
    coefficients convert exactly to Bernstein intervals; the separate remainder
    is h**13/13! for each compared FUNCTION, including cos and -sin when bounding
    derivatives. Outward128bit interval arithmetic is inherited. No libm values,
    new physical tolerance, source coefficient changes or refinement are used.
    """
    checkpoint()
    if (
        any(
            len(values) != 6 or any(type(x) is not Fraction for x in values)
            for values in (sine, cosine, phase)
        )
        or any(type(x) is not Fraction for x in (low, high))
        or not 0 <= low < high <= 4
    ):
        raise ValueError(
            "Exact quintics and an original increasing phase interval within0..4 required"
        )
    width = high - low
    sn, cs = trigonometry(low)
    cycles = ((sn, cs, sn.negate(), cs.negate()), (cs, sn.negate(), cs.negate(), sn))

    def taylor(cycle: tuple[Interval, ...]) -> tuple[Interval, ...]:
        """
        Convert bounded Taylor coefficients to Bernstein form on the same local unit interval.
        """
        powers = tuple(cycle[k % 4].multiply(fixed(width**k / factorial(k))) for k in range(13))
        controls = []
        for i in range(13):
            value = fixed(Fraction(0))
            for k in range(i + 1):
                value = value.add(powers[k].multiply(fixed(Fraction(comb(i, k), comb(12, k)))))
            controls.append(value)
        return tuple(controls)

    sine_controls, cosine_controls = (taylor(cycle) for cycle in cycles)
    remainder = width**13 / factorial(13)

    def error(values: Polynomial, reference: tuple[Interval, ...]) -> Fraction:
        """
        Bound the complete polynomial difference plus its own analytic Taylor remainder.
        """
        exact = elevate(values, 12)
        return (
            max(target.add(fixed(-actual)).absolute() for actual, target in zip(exact, reference))
            + remainder
        )

    sine_first = tuple(Fraction(x, width) for x in derivative(sine))
    cosine_first = tuple(Fraction(x, width) for x in derivative(cosine))
    checkpoint()
    return ScalarReferenceBounds(
        error(sine, sine_controls),
        error(cosine, cosine_controls),
        error(sine_first, cosine_controls),
        error(cosine_first, tuple(x.negate() for x in sine_controls)),
        max(abs(Fraction(x, width) - 1) for x in derivative(phase)),
    )
