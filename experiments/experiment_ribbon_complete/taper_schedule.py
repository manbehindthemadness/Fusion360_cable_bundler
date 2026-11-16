"""
Plan an exact C2 taper timing from one explicit serial material allowance.

This isolated planner covers straight center paths and constant orthonormal axes:
X(u)=C0+L*u*T+beta(u)*D, with D perpendicular to T. It does not author or replace
branch candidates, handle rational weight motion, or certify a complete ribbon.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .material_paths import square_root_lower


@dataclass(frozen=True)
class TaperRequirement:
    """
    Supply a straight trace's length, transverse displacement and curvature ceiling.

    Displacement is an enclosing magnitude, not a fitted component or a strain
    tolerance. A zero curvature ceiling is permitted and may leave the chosen
    family unresolved. Curved centers or moving frames need another certificate.
    """

    length_mm: Fraction
    displacement_mm: Fraction
    curvature_limit_per_mm: Fraction

    def __post_init__(self) -> None:
        """
        Require exact nonnegative dimensional inputs and positive center length.
        """
        values = (self.length_mm, self.displacement_mm, self.curvature_limit_per_mm)
        if (
            any(type(value) is not Fraction for value in values)
            or self.length_mm <= 0
            or self.displacement_mm < 0
            or self.curvature_limit_per_mm < 0
        ):
            raise ValueError(
                "Exact positive length and nonnegative displacement/curvature required"
            )


@dataclass(frozen=True)
class BlendInterval:
    """
    Retain exact Bernstein controls on one nonempty part of the global unit interval.
    """

    low: Fraction
    high: Fraction
    controls: tuple[Fraction, ...]


@dataclass(frozen=True)
class TaperSchedule:
    """
    Return a conditional blend certificate or an unresolved family without geometry.

    All requirements are declared serial contributions to ONE corresponding path,
    not siblings or independent layouts. The caller must debit trunk and all other
    contributions before supplying the remaining allowance. No implicit zero trunk
    bound, transverse metric, material atlas, junction or native pass is inferred.
    """

    requirements: tuple[TaperRequirement, ...]
    allowance_mm: Fraction
    status: Literal["certified", "unresolved"]
    reason: str
    alpha: Fraction | None
    intervals: tuple[BlendInterval, ...]
    discrepancy_upper_mm: Fraction | None
    curvature_upper_per_mm: tuple[Fraction, ...]


def plan(
    requirements: tuple[TaperRequirement, ...],
    allowance_mm: Fraction,
    checkpoint: Callable[[], None],
) -> TaperSchedule:
    """
    Derive one monotone C2 blend without search, geometric repair or a work reserve.

    beta-prime ramps by cubic smoothstep, stays constant, then ramps down. Its
    plateau speed is1/(1-alpha), and integral(beta-prime squared) is
    (1-44*alpha/35)/(1-alpha) squared. Rationalization of sqrt(L²+|D|²*beta'²)-L
    gives the serial bound A*energy, where A=sum(|D|²/(2L)). Curvature is at most
    3*|D|/(2*L²*alpha*(1-alpha)). Both are sufficient bounds, not necessity claims.

    Energy increases on(0,1/2]. Conservatively approximate its largest budget-
    admissible alpha using a forty-bit upper square-root enclosure. Wider ramps
    reduce this family's curvature bound. The arithmetic grid is a
    numerical proof dependency, not a dimensional acceptance rule. Unresolved
    rounding or curvature constraints never establish input infeasibility.
    """
    checkpoint()
    if (
        not isinstance(requirements, tuple)
        or not requirements
        or any(not isinstance(value, TaperRequirement) for value in requirements)
        or type(allowance_mm) is not Fraction
        or not 0 < allowance_mm <= Fraction(1, 100)
    ):
        raise ValueError("Declare nonempty serial requirements and one positive allowance<=0.01mm")
    amount = Fraction(0)
    for value in requirements:
        checkpoint()
        amount += value.displacement_mm**2 / (2 * value.length_mm)
    half = Fraction(1, 2)
    alpha = half
    if amount and amount * Fraction(52, 35) > allowance_mm:
        ratio = allowance_mm / amount
        if ratio <= 1:
            return TaperSchedule(
                requirements,
                allowance_mm,
                "unresolved",
                "Insufficient allowance for this sufficient bound",
                None,
                (),
                None,
                (),
            )
        coefficient = 2 * ratio - Fraction(44, 35)
        discriminant = coefficient**2 - 4 * ratio * (ratio - 1)
        if discriminant < 0:
            return TaperSchedule(
                requirements,
                allowance_mm,
                "unresolved",
                "Unresolved analytic budget root",
                None,
                (),
                None,
                (),
            )
        lower = square_root_lower(discriminant)
        upper = lower if lower**2 == discriminant else lower + Fraction(1, 1 << 40)
        alpha = (coefficient - upper) / (2 * ratio)
    checkpoint()
    if not 0 < alpha <= half:
        return TaperSchedule(
            requirements,
            allowance_mm,
            "unresolved",
            "Budget root is unresolved at the fixed arithmetic grid",
            None,
            (),
            None,
            (),
        )
    energy = (1 - Fraction(44, 35) * alpha) / (1 - alpha) ** 2
    discrepancy = amount * energy
    curvatures = tuple(
        3 * value.displacement_mm / (2 * value.length_mm**2 * alpha * (1 - alpha))
        for value in requirements
    )
    if discrepancy > allowance_mm:
        return TaperSchedule(
            requirements,
            allowance_mm,
            "unresolved",
            "Conservative budget root did not certify",
            None,
            (),
            discrepancy,
            curvatures,
        )
    if any(bound > value.curvature_limit_per_mm for bound, value in zip(curvatures, requirements)):
        return TaperSchedule(
            requirements,
            allowance_mm,
            "unresolved",
            "Curvature bound is not certified in the budget-admissible family",
            None,
            (),
            discrepancy,
            curvatures,
        )
    speed = 1 / (1 - alpha)
    first = BlendInterval(
        Fraction(0),
        alpha,
        tuple(
            speed * alpha * value
            for value in (Fraction(0), Fraction(0), Fraction(0), Fraction(1, 4), half)
        ),
    )
    last = BlendInterval(
        1 - alpha, Fraction(1), tuple(1 - value for value in reversed(first.controls))
    )
    intervals = (
        (first, last)
        if alpha == half
        else (
            first,
            BlendInterval(alpha, 1 - alpha, (first.controls[-1], last.controls[0])),
            last,
        )
    )
    checkpoint()
    return TaperSchedule(
        requirements,
        allowance_mm,
        "certified",
        "Conditional straight fixed-frame trace certificate",
        alpha,
        intervals,
        discrepancy,
        curvatures,
    )
