"""
Select one fixture radius with at most 24 unchanged input-certificate evaluations.

Uniformly scaled semicircle curvature bounds vary inversely with radius. This
brackets the existing finite-depth certificate, not native loft feasibility,
minimum distance for arbitrary routes, or full twisted-conductor compliance.
No ribbon solver, Fusion call, target repair or certificate-policy change occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)

from .fixtures import certificate_limit_case


@dataclass(frozen=True)
class RadiusCheck:
    """
    Retain every passing/rejected authoring probe without counting ribbon coverage.
    """

    radius_mm: float
    passed: bool
    maximum_ratio: float | None
    reason: str | None


@dataclass(frozen=True)
class RadiusSelection:
    """
    Freeze the closest observed passing radius and its unresolved boundary bracket.
    """

    radius_mm: float
    rejected_radius_mm: float
    maximum_ratio: float
    checks: tuple[RadiusCheck, ...]
    elapsed_seconds: float


def select_radius() -> RadiusSelection:
    """
    Check R20 then bisect (0, 20] 23 times, retaining the passing side unchanged.

    Zero is a singular scale, not evaluated. After the first rejection the lower
    bound is observed. The final interval width is the numerical margin; exact
    minimum is not claimed. Scheduling stops at 10 seconds, including failures;
    unexpected errors propagate. Catch only the certificate's explicit rejection.
    """
    started = perf_counter()
    checks: list[RadiusCheck] = []
    lower, upper = 0.0, 20.0
    best_ratio = 0.0
    for index in range(24):
        if perf_counter() - started >= 10:
            raise RuntimeError("Radius authoring time cap reached; no native scheduling.")
        radius = upper if index == 0 else (lower + upper) / 2
        case = certificate_limit_case(radius)
        try:
            certificate = certify_curvature(
                case.route, discrete_profile_reach(case.lines, case.diameter_mm)
            )
        except UnsafeRibbon as error:
            checks.append(RadiusCheck(radius, False, None, str(error)))
            if index == 0:
                raise RuntimeError(
                    "Parent R20 no longer certifies; stop without refinement."
                ) from error
            lower = radius
        else:
            checks.append(RadiusCheck(radius, True, certificate.maximum_ratio, None))
            upper, best_ratio = radius, certificate.maximum_ratio
    elapsed = perf_counter() - started
    if elapsed >= 10 or lower == 0:
        raise RuntimeError("Radius boundary was not bracketed within the authoring budget.")
    return RadiusSelection(upper, lower, best_ratio, tuple(checks), elapsed)
