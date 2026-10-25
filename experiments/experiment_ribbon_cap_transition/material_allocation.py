"""
Project fixed endpoints onto a developable finite-width material-strip family.

Six capped scalar Gauss-Newton updates are a bounded diagnostic, not a global
solver. Each projection inspects at most63 algebraic supports; derivative probes
are counted, and failure never snaps the endpoint or relaxes curvature bounds.
"""

from __future__ import annotations

from dataclasses import dataclass

from cable_bundler.routing.geometry import difference, dot, magnitude

from .banked_schedule import TurnSchedule
from .bounded_travel import AllocationStatus, TravelAllocation
from .closure_allocation import (
    DERIVATIVE_STEP,
    MAX_ANGLE,
    MAX_STEP,
    MAX_UPDATES,
    ClosurePlan,
    Projection,
    closest_travel,
)
from .closure_schedule import initial, schedule
from .conductor_allocation import construct as baseline_construct
from .coupled_motion import ZERO
from .endpoint_first import EndpointCase, controls
from .material_policy import minimum_travel, place, prototypes
from .material_strip import MaterialSpan, MaterialStrip


@dataclass(frozen=True)
class MaterialPlan(ClosurePlan):
    """
    Retain the actual material strip alongside bounded closure counters.
    """

    strip: MaterialStrip


def _project(
    case: EndpointCase, baseline: TurnSchedule, angle: float
) -> tuple[TurnSchedule, tuple[MaterialSpan, ...], tuple[float, ...], Projection]:
    """
    Recompute continuous curvature floors before each counted travel projection.
    """
    selected = schedule(case, baseline, angle)
    spans = prototypes(selected)
    lower = minimum_travel(case, spans)
    projection = closest_travel(
        tuple(m.displacement(1) for m in selected.motions), lower, difference(case.end, case.start)
    )
    return selected, spans, lower, projection


def construct(case: EndpointCase) -> MaterialPlan:
    """
    Make at most six clipped updates from the unchanged baseline schedule.

    Central finite differences of the projected residual use +/-1e-4 radians.
    Each update is limited to15degrees and the total scheduling angle to just
    under90degrees. At most19 projections/1197 support checks occur per case.
    Stop at1e-8mm closure, a numerically stationary derivative, or six updates.
    Final residuals are retained even if an update worsened them; no best-of retry.
    """
    controls(case)
    chord = difference(case.end, case.start)
    if (
        magnitude(difference(case.start_width, case.end_width)) <= 1e-10
        and abs(dot(chord, case.start_width)) <= 1e-10
    ):
        control = baseline_construct(case)
        strip = MaterialStrip(
            tuple(MaterialSpan(m, 0, 0) for m in control.motions),
            case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1,
        )
        return MaterialPlan(
            control.motions,
            control.connected,
            control.allocation,
            control.lower_bounds_mm,
            control.endpoint_gap_mm,
            control.schedule_kind,
            control.lane_curvature_bound_per_mm,
            0,
            0,
            0,
            0,
            (),
            "unchanged analytic control",
            strip,
        )
    baseline = initial(case)
    angle, updates, calls, checked = 0.0, 0, 0, 0
    history: list[tuple[float, float]] = []
    termination = "six-update budget exhausted"
    while True:
        selected, spans, lower, projection = _project(case, baseline, angle)
        calls += 1
        checked += projection.checked_bases
        gap = magnitude(projection.residual)
        history.append((angle, gap))
        if gap <= 1e-8:
            termination = "fixed endpoint reached"
            break
        if updates == MAX_UPDATES:
            break
        plus = _project(case, baseline, angle + DERIVATIVE_STEP)[3]
        minus = _project(case, baseline, angle - DERIVATIVE_STEP)[3]
        calls += 2
        checked += plus.checked_bases + minus.checked_bases
        derivative = ZERO.translated(
            difference(plus.residual, minus.residual), 1 / (2 * DERIVATIVE_STEP)
        )
        denominator = dot(derivative, derivative)
        if denominator <= 1e-20:
            termination = "stationary projected residual"
            break
        step = max(-MAX_STEP, min(MAX_STEP, -dot(projection.residual, derivative) / denominator))
        next_angle = max(-MAX_ANGLE, min(MAX_ANGLE, angle + step))
        if abs(next_angle - angle) <= 1e-12:
            termination = "stationary or bounded schedule angle"
            break
        angle = next_angle
        updates += 1
    strip = place(case, spans, projection.lengths)
    motions = tuple(span.motion for span in strip.spans)
    gap = magnitude(difference(motions[-1].jet(1)[0], case.end))
    connected = gap <= 1e-8
    allocation = TravelAllocation(
        AllocationStatus.FEASIBLE if connected else AllocationStatus.UNRESOLVED,
        projection.lengths if connected else None,
        checked,
    )
    return MaterialPlan(
        motions,
        connected,
        allocation,
        lower,
        gap,
        selected.kind,
        max(m.maximum_curvature() for m in motions),
        angle,
        updates,
        calls,
        checked,
        tuple(history),
        termination,
        strip,
    )
