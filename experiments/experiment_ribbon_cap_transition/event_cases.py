"""
Keep fixed endpoint fixtures separate from continuous event observations.
"""

from __future__ import annotations

import math
from dataclasses import replace

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .banked_schedule import ScheduleKind
from .bounded_travel import AllocationStatus, TravelAllocation
from .coupled_motion import ZERO, CoupledMotion
from .coupled_route import cases as previous_cases
from .endpoint_first import EndpointCase
from .material_allocation import MaterialPlan
from .material_allocation import construct as previous_construct
from .material_strip import MaterialSpan, MaterialStrip

S_NAME = "smooth_S_event_control"


def cases() -> tuple[EndpointCase, ...]:
    """
    Retain all seven examined poses and add one fixed-pose smooth planar S control.

    Its two eased signed turns are an integration representation, not inferred
    conceptual events, separate native pieces or a general routing policy.
    """
    x, y = Vector3(1, 0, 0), Vector3(0, 1, 0)
    return (
        *previous_cases(),
        EndpointCase(S_NAME, Vector3(-40, 0, -10), Vector3(40, 0, 10), x, x, y, y),
    )


def construct(case: EndpointCase) -> MaterialPlan:
    """
    Apply the previous fixed-budget solver or the predeclared exact S control branch.

    For the S fixture, quintic-angle symmetry puts each unit displacement along
    the chord bisector; two equal positive lengths close the frozen positions.
    Tangent and curvature remain continuous, including zero curvature at reversal.
    Other endpoint families receive no new search, retry or route adjustment.
    """
    if case.name != S_NAME:
        return previous_construct(case)
    if case != cases()[-1]:
        raise ValueError("S control requires its original frozen boundary conditions.")
    chord = difference(case.end, case.start)
    angle = -2 * math.atan2(chord.z, chord.x)
    prototype = CoupledMotion(
        ZERO, case.start_tangent, case.start_width, case.start_width, angle, 1
    )
    length = magnitude(chord) / (2 * magnitude(prototype.displacement(1)))
    first = replace(prototype, start=case.start, length=length)
    tangent, width = first.frame(1)
    second = CoupledMotion(first.jet(1)[0], tangent, width, width, -angle, length)
    strip = MaterialStrip(
        (MaterialSpan(first, 0, 0), MaterialSpan(second, 0, 0)),
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1,
    )
    gap = magnitude(difference(second.jet(1)[0], case.end))
    if gap > 1e-8:
        raise RuntimeError("Frozen smooth S control did not close its endpoints.")
    allocation = TravelAllocation(AllocationStatus.FEASIBLE, (length, length), 0)
    return MaterialPlan(
        (first, second),
        True,
        allocation,
        (),
        gap,
        ScheduleKind.ANALYTIC_CONTROL,
        first.maximum_curvature(),
        0,
        0,
        0,
        0,
        (),
        "analytic fixed-pose S control",
        strip,
    )
