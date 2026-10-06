"""
Expose one explicit candidate while retaining the original macaroni contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude, unit
from experiments.experiment_secure_discrete_ribbon.bank import bank_ribbon_frames
from experiments.experiment_secure_discrete_ribbon.cases import RibbonStressCase
from experiments.experiment_secure_discrete_ribbon.contract import (
    certify_curvature,
    discrete_profile_reach,
)
from experiments.experiment_secure_discrete_ribbon.frames import (
    RibbonFrame,
    ribbon_frames,
    ribbon_lane_points,
)
from experiments.experiment_secure_discrete_ribbon.shape import (
    RibbonEndFit,
    RibbonShape,
    solve_ribbon_shape,
)

from .ends import SmoothCapTransition, cap_direction

LaneObserver = Callable[[str, tuple[tuple[Vector3, ...], ...]], None]


@dataclass(frozen=True)
class _ObservedTransition:
    """
    Observe the unchanged cap policy without inserting another solve or blend.
    """

    transition: SmoothCapTransition
    observer: LaneObserver

    def lead_length_mm(
        self, historical_lead_mm: float, lanes: tuple[tuple[Vector3, ...], ...]
    ) -> float:
        """
        Delegate the support decision unchanged.
        """
        return self.transition.lead_length_mm(historical_lead_mm, lanes)

    def blend(
        self,
        lanes: tuple[tuple[Vector3, ...], ...],
        fit: RibbonEndFit | None,
        *,
        at_start: bool,
        distances_mm: tuple[float, ...],
        lead_mm: float,
    ) -> tuple[tuple[Vector3, ...], ...]:
        """
        Record immutable lane samples after the original policy has blended once.
        """
        result = self.transition.blend(
            lanes, fit, at_start=at_start, distances_mm=distances_mm, lead_mm=lead_mm
        )
        self.observer("cap_A" if at_start else "cap_B", result)
        return result


def candidate_frames(
    case: RibbonStressCase,
    start_fit: RibbonEndFit,
    end_fit: RibbonEndFit,
    *,
    maximum_sections: int = 32,
    observer: LaneObserver | None = None,
) -> tuple[RibbonFrame, ...]:
    """
    Validate the fixed route/caps and bank the unchanged sampled section scaffold.

    The route certificate applies to the input route, not subsequent deformation
    or interpolation. Observers record unbanked and banked samples only.
    """
    certify_curvature(case.route, discrete_profile_reach(case.lines, case.diameter_mm))
    tangents = (case.route.curves[0].derivative(0), case.route.curves[-1].derivative(1))
    for fit, tangent, width in zip(
        (start_fit, end_fit), tangents, (case.start_width, case.end_width)
    ):
        if fit.approach_normal is None:
            raise ValueError("The candidate requires both actual cap normals.")
        cap_tangent = cap_direction(fit.approach_normal, tangent)
        if dot(cap_tangent, unit(tangent)) < 1 - 1e-7:
            raise ValueError("The fixed centerline tangent does not match its cap plane.")
        if abs(dot(unit(width), unit(tangent))) > 1e-8:
            raise ValueError("The guide width must lie in its exact cap plane.")
    frames = ribbon_frames(
        case.route,
        case.start_width,
        case.end_width,
        maximum_sections=maximum_sections,
        endpoint_tangents=tangents,
    )
    if observer is not None:
        observer("unbanked", ribbon_lane_points(frames, case.lines, case.diameter_mm))
    frames = bank_ribbon_frames(frames, case.lines, case.diameter_mm)
    if observer is not None:
        observer("banked", ribbon_lane_points(frames, case.lines, case.diameter_mm))
    return frames


def solve_candidate(
    case: RibbonStressCase,
    start_fit: RibbonEndFit,
    end_fit: RibbonEndFit,
    *,
    maximum_sections: int = 32,
    observer: LaneObserver | None = None,
) -> RibbonShape:
    """
    Solve the existing fixed-centerline candidate with its original fold budget.

    Shared frame validation does not change blending, targets or search decisions.
    Returned samples still require complete branch and native audits.
    """
    frames = candidate_frames(
        case, start_fit, end_fit, maximum_sections=maximum_sections, observer=observer
    )
    tangents = (case.route.curves[0].derivative(0), case.route.curves[-1].derivative(1))
    # Constant width perpendicular to every derivative makes lanes rigid translates.
    width = unit(case.start_width)
    translated = (
        magnitude(difference(width, unit(case.end_width))) <= 1e-10
        and all(
            abs(dot(difference(b, a), width)) <= 1e-8
            for curve in case.route.curves
            for a, b in zip(
                (curve.start, curve.control_a, curve.control_b),
                (curve.control_a, curve.control_b, curve.end),
            )
        )
        and all(magnitude(difference(frame.width, width)) <= 1e-8 for frame in frames)
    )
    exact_inward = (
        (
            unit(tangents[0]),
            Vector3(-unit(tangents[1]).x, -unit(tangents[1]).y, -unit(tangents[1]).z),
        )
        if translated
        else None
    )
    transition = SmoothCapTransition(exact_inward, (start_fit, end_fit))
    shape = solve_ribbon_shape(
        frames,
        case.lines,
        case.diameter_mm,
        start_fit=start_fit,
        end_fit=end_fit,
        end_transition=transition
        if observer is None
        else _ObservedTransition(transition, observer),
    )
    if observer is not None:
        observer("equalized", shape.lanes)
    return shape
