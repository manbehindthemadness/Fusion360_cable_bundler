"""
Allocate new three-turn motions with analytic center and conductor curvature bounds.

For any lane offset h, velocity=T*L+h*W' has magnitude at least L because T.W'=0.
Thus curvature <= A/L+C/L^2, with A=max|T'| and C=max|h|*max|W''|. This includes
banking acceleration and applies to continuous reference curves, not native cubic
interpolation, elastic strain, clearance or containment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cable_bundler.routing.geometry import cross, difference, dot, magnitude

from .banked_schedule import ScheduleKind, schedule
from .bounded_travel import AllocationStatus, TravelAllocation, allocate
from .coupled_motion import AngleLaw, CoupledMotion
from .coupled_route import construct as original_construct
from .endpoint_first import EndpointCase, controls
from .radius_allocation import GuidePlan, _place


@dataclass(frozen=True)
class ConductorGuidePlan(GuidePlan):
    """
    Add the selected motion policy and continuous reference-lane curvature bound.
    """

    schedule_kind: ScheduleKind
    lane_curvature_bound_per_mm: float


def curvature_coefficients(case: EndpointCase, motion: CoupledMotion) -> tuple[float, float]:
    """
    Bound parameter tangent and width acceleration without sampling or curve fitting.

    The two terms of W'' are perpendicular, allowing their maximum magnitudes to
    combine by hypot. Independent derivative maxima make this bound conservative.
    """
    speed = abs(motion.angle) * (1.875 if motion.law is AngleLaw.EASED else 1)
    acceleration = abs(motion.angle) * 10 / math.sqrt(3) if motion.law is AngleLaw.EASED else 0
    a = speed * magnitude(cross(motion.axis, motion.tangent))
    width_second = magnitude(cross(motion.axis, motion.width)) * math.hypot(
        acceleration, speed * speed
    )
    return a, (case.lines - 1) * case.diameter_mm / 2 * width_second


def lane_bound(case: EndpointCase, motions: tuple[CoupledMotion, ...]) -> float:
    """
    Return an analytic curvature upper bound for every ordered conductor centerline.
    """
    return max(
        (a / motion.length + c / motion.length**2)
        for motion in motions
        for a, c in (curvature_coefficients(case, motion),)
    )


def minimum_travel(case: EndpointCase, motions: tuple[CoupledMotion, ...]) -> tuple[float, ...]:
    """
    Require both the existing macaroni bound and continuous per-conductor radius.

    Solving L^2/R-A*L-C>=0 gives the conductor floor. The unchanged conservative
    1e-12 relative roundoff guard is applied before any allocation is evaluated.
    """
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    radius = 3 * case.diameter_mm
    floors = []
    for motion in motions:
        a, c = curvature_coefficients(case, motion)
        center_floor = a * reach / 0.8
        lane_floor = (a * radius + math.sqrt((a * radius) ** 2 + 4 * c * radius)) / 2
        floors.append(max(center_floor, lane_floor) * (1 + 1e-12))
    return tuple(floors)


def construct(case: EndpointCase) -> ConductorGuidePlan:
    """
    Allocate once within the preselected schedule, retaining unclosed diagnostics.

    An allocation failure never changes schedule, bounds or external target poses.
    Controls remain exact. Reference-lane bounds do not establish native sweeps or
    complete ribbon compliance, and unclosed diagnostics remain failed connections.
    """
    controls(case)
    chord = difference(case.end, case.start)
    if (
        magnitude(difference(case.start_width, case.end_width)) <= 1e-10
        and abs(dot(chord, case.start_width)) <= 1e-10
    ):
        motions = original_construct(case)
        lengths = tuple(m.length for m in motions)
        return ConductorGuidePlan(
            motions,
            True,
            TravelAllocation(AllocationStatus.FEASIBLE, lengths, 0),
            (),
            magnitude(difference(motions[-1].jet(1)[0], case.end)),
            ScheduleKind.ANALYTIC_CONTROL,
            lane_bound(case, motions),
        )
    selected = schedule(case)
    lower = minimum_travel(case, selected.motions)
    allocation = allocate(tuple(m.displacement(1) for m in selected.motions), lower, chord)
    connected = allocation.lengths is not None
    lengths = allocation.lengths if connected else lower
    if lengths is None:
        raise RuntimeError("Missing conductor-bounded travel lengths.")
    motions = _place(selected.motions, lengths, case)
    gap = magnitude(difference(motions[-1].jet(1)[0], case.end))
    if connected and gap > 1e-8:
        raise RuntimeError("Conductor-bounded allocation failed fixed endpoint closure.")
    return ConductorGuidePlan(
        motions, connected, allocation, lower, gap, selected.kind, lane_bound(case, motions)
    )
