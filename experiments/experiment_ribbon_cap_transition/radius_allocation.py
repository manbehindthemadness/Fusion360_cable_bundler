"""
Require forward, curvature-safe travel within the frozen chord-guided motion family.

Failed allocation still supplies an explicitly unclosed minimum-length diagnostic
for inspection. It never becomes a completed route or a fallback accepted cable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cable_bundler.routing.geometry import difference, dot, magnitude

from .bounded_travel import AllocationStatus, TravelAllocation, allocate
from .chord_coupled import schedule
from .coupled_motion import CoupledMotion
from .coupled_route import construct as original_construct
from .endpoint_first import EndpointCase, controls


@dataclass(frozen=True)
class GuidePlan:
    """
    Keep connected candidates distinct from unclosed lower-bound visual diagnostics.
    """

    motions: tuple[CoupledMotion, ...]
    connected: bool
    allocation: TravelAllocation
    lower_bounds_mm: tuple[float, ...]
    endpoint_gap_mm: float


def minimum_travel(case: EndpointCase, motions: tuple[CoupledMotion, ...]) -> tuple[float, ...]:
    """
    Derive segment-length floors from the analytic centerline macaroni limit.

    Unit-length primitive curvature scales inversely with travel. A fixed 1e-12
    relative guard keeps roundoff away from the 0.8 boundary without weakening it.
    Straight zero-angle segments need no positive minimum and may be omitted.
    These floors do not certify per-lane curvature, clearance or material strain.
    """
    reach = math.hypot(
        case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1, case.diameter_mm / 2
    )
    return tuple(m.maximum_curvature() * m.length * reach / 0.8 * (1 + 1e-12) for m in motions)


def _place(
    prototypes: tuple[CoupledMotion, ...], lengths: tuple[float, ...], case: EndpointCase
) -> tuple[CoupledMotion, ...]:
    """
    Position one forward motion sequence without snapping or moving external targets.
    """
    placed, start = [], case.start
    for prototype, length in zip(prototypes, lengths):
        if length == 0:
            if prototype.angle != 0:
                raise RuntimeError("A nonzero rotation cannot have zero travel.")
            continue
        motion = replace(prototype, start=start, length=length)
        placed.append(motion)
        start = motion.jet(1)[0]
    if not placed:
        raise RuntimeError("Empty diagnostic motion sequence.")
    return tuple(placed)


def construct(case: EndpointCase) -> GuidePlan:
    """
    Allocate once and retain a visible, clearly classified result for every case.

    Controls keep their exact original analytic geometry. For general poses, one
    bounded allocation problem uses the unchanged chord schedule. A failed result
    displays required-minimum travel only; its endpoint gap remains an explicit
    failure even if its center curvature and frame coupling meet named checks.
    """
    controls(case)
    chord = difference(case.end, case.start)
    if (
        magnitude(difference(case.start_width, case.end_width)) <= 1e-10
        and abs(dot(chord, case.start_width)) <= 1e-10
    ):
        motions = original_construct(case)
        lengths = tuple(m.length for m in motions)
        return GuidePlan(
            motions,
            True,
            TravelAllocation(AllocationStatus.FEASIBLE, lengths, 0),
            (),
            magnitude(difference(motions[-1].jet(1)[0], case.end)),
        )
    prototypes = schedule(case)
    lower = minimum_travel(case, prototypes)
    allocation = allocate(tuple(m.displacement(1) for m in prototypes), lower, chord)
    connected = allocation.lengths is not None
    lengths = allocation.lengths if connected else lower
    if lengths is None:
        raise RuntimeError("Missing travel lengths.")
    motions = _place(prototypes, lengths, case)
    gap = magnitude(difference(motions[-1].jet(1)[0], case.end))
    if connected and gap > 1e-8:
        raise RuntimeError("Bounded allocation failed fixed endpoint closure.")
    return GuidePlan(motions, connected, allocation, lower, gap)
