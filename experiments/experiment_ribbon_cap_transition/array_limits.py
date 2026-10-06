"""
Author uniformly tightened centerlines using only the unchanged input certificate.

Material, sphere and width directions remain fixed. No ribbon solves, native
feedback, endpoint repair or changed certificate tolerances enter this search.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter
from uuid import NAMESPACE_URL, uuid5

from cable_bundler.routing.geometry import CubicBezier, Vector3, difference
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    UnsafeRibbon,
    certify_curvature,
    discrete_profile_reach,
)


@dataclass(frozen=True)
class ScaleCheck:
    """
    Retain every authoring probe, including explicit certificate rejections.
    """

    scale: float
    passed: bool
    maximum_ratio: float | None
    reason: str | None


@dataclass(frozen=True)
class ScaleSelection:
    """
    Freeze the observed passing side of a finite certificate boundary bracket.
    """

    scale: float
    rejected_scale: float
    maximum_ratio: float
    checks: tuple[ScaleCheck, ...]
    elapsed_seconds: float


def scaled_case(parent: RibbonStressCase, scale: float) -> RibbonStressCase:
    """
    Scale ordered curve controls and route points about the unchanged sphere center.
    """
    if not 0 < scale <= 1:
        raise ValueError("Authoring scale must be in (0, 1].")
    center = parent.end_boundary.center

    def point(value: Vector3) -> Vector3:
        """
        Apply one rigid-center similarity to a position, not material dimensions.
        """
        return center.translated(difference(value, center), scale)

    name = parent.name + "_certificate_limit"
    curves = tuple(
        CubicBezier(*(point(value) for value in (c.start, c.control_a, c.control_b, c.end)))
        for c in parent.route.curves
    )
    route = replace(
        parent.route,
        cable_id=uuid5(NAMESPACE_URL, name),
        cable_number=name,
        points=tuple(point(value) for value in parent.route.points),
        curves=curves,
    )
    return replace(parent, name=name, family=name, route=route)


def select_scale(parent: RibbonStressCase) -> ScaleSelection:
    """
    Check scale1 then bisect (0,1]23 times within a ten-second authoring cap.

    Catch only explicit certificate rejection; parent rejection and unexpected
    errors stop the batch. Zero is singular and never evaluated. This boundary
    concerns the input centerline envelope, not twisted/native material compliance.
    """
    started = perf_counter()
    lower, upper, ratio = 0.0, 1.0, 0.0
    checks: list[ScaleCheck] = []
    for index in range(24):
        if perf_counter() - started >= 10:
            raise RuntimeError("Certificate authoring time cap; no native scheduling.")
        scale = upper if index == 0 else (lower + upper) / 2
        case = scaled_case(parent, scale)
        try:
            certificate = certify_curvature(
                case.route, discrete_profile_reach(case.lines, case.diameter_mm)
            )
        except UnsafeRibbon as error:
            checks.append(ScaleCheck(scale, False, None, str(error)))
            if index == 0:
                raise RuntimeError("Parent no longer certifies; no refinement.") from error
            lower = scale
        else:
            checks.append(ScaleCheck(scale, True, certificate.maximum_ratio, None))
            upper, ratio = scale, certificate.maximum_ratio
    elapsed = perf_counter() - started
    if elapsed >= 10 or lower == 0:
        raise RuntimeError("Certificate boundary not bracketed within authoring budget.")
    return ScaleSelection(upper, lower, ratio, tuple(checks), elapsed)
