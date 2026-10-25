"""
Project fixed endpoint displacement onto curvature-safe travel and one schedule angle.

Six capped scalar Gauss-Newton updates are a bounded diagnostic, not a global
solver. Each projection inspects at most63 algebraic supports; derivative probes
are counted, and failure never snaps the endpoint or relaxes curvature bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude

from .banked_schedule import ScheduleKind, TurnSchedule
from .bounded_travel import AllocationStatus, TravelAllocation, _coefficients
from .closure_schedule import initial, schedule
from .conductor_allocation import construct as baseline_construct
from .conductor_allocation import lane_bound, minimum_travel
from .coupled_motion import ZERO
from .endpoint_first import EndpointCase, controls
from .radius_allocation import GuidePlan, _place

MAX_UPDATES = 6
DERIVATIVE_STEP = 1e-4
MAX_STEP = math.pi / 12
MAX_ANGLE = math.pi / 2 - DERIVATIVE_STEP


@dataclass(frozen=True)
class Projection:
    """
    Retain the nearest nonnegative travel vector, including nonzero closure error.
    """

    lengths: tuple[float, ...]
    residual: Vector3
    checked_bases: int


@dataclass(frozen=True)
class ClosurePlan(GuidePlan):
    """
    Keep final geometry, bounded solver workload and every update residual together.
    """

    schedule_kind: ScheduleKind
    lane_curvature_bound_per_mm: float
    schedule_angle: float
    updates: int
    projection_calls: int
    checked_bases_total: int
    history: tuple[tuple[float, float], ...]
    termination: str


def closest_travel(
    columns: tuple[Vector3, ...], lower: tuple[float, ...], chord: Vector3
) -> Projection:
    """
    Minimize endpoint residual over forward travel above fixed nonnegative floors.

    In three dimensions the nearest point in the finitely generated travel cone
    has an independent support of size at most three. Finite-precision rank skips
    remain diagnostic limitations. No negative travel is clipped into feasibility.
    Equal residuals choose shorter travel. Returns failure residuals explicitly.
    """
    if not 1 <= len(columns) <= 7 or len(columns) != len(lower):
        raise ValueError("Projection requires one to seven paired travel columns.")
    if any(not math.isfinite(v) for p in (*columns, chord) for v in (p.x, p.y, p.z)) or any(
        not math.isfinite(v) or v < 0 for v in lower
    ):
        raise ValueError("Projection vectors and nonnegative floors must be finite.")
    residual = chord
    for column, floor in zip(columns, lower):
        residual = residual.translated(column, -floor)
    best_lengths, best_residual = lower, residual
    best_key = (dot(residual, residual), sum(lower))
    checked = 0
    for size in range(1, min(3, len(columns)) + 1):
        for indices in combinations(range(len(columns)), size):
            checked += 1
            support = tuple(columns[index] for index in indices)
            values = _coefficients(support, residual)
            if values is None or min(values) < 0:
                continue
            remaining = residual
            lengths = list(lower)
            for index, value in zip(indices, values):
                remaining = remaining.translated(columns[index], -value)
                lengths[index] += value
            key = (dot(remaining, remaining), sum(lengths))
            if key < best_key:
                best_lengths, best_residual, best_key = tuple(lengths), remaining, key
    return Projection(best_lengths, best_residual, checked)


def _project(
    case: EndpointCase, baseline: TurnSchedule, angle: float
) -> tuple[TurnSchedule, tuple[float, ...], Projection]:
    """
    Recompute continuous curvature floors before each counted travel projection.
    """
    selected = schedule(case, baseline, angle)
    lower = minimum_travel(case, selected.motions)
    projection = closest_travel(
        tuple(m.displacement(1) for m in selected.motions), lower, difference(case.end, case.start)
    )
    return selected, lower, projection


def construct(case: EndpointCase) -> ClosurePlan:
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
        return ClosurePlan(
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
        )
    baseline = initial(case)
    angle, updates, calls, checked = 0.0, 0, 0, 0
    history: list[tuple[float, float]] = []
    termination = "six-update budget exhausted"
    while True:
        selected, lower, projection = _project(case, baseline, angle)
        calls += 1
        checked += projection.checked_bases
        gap = magnitude(projection.residual)
        history.append((angle, gap))
        if gap <= 1e-8:
            termination = "fixed endpoint reached"
            break
        if updates == MAX_UPDATES:
            break
        plus = _project(case, baseline, angle + DERIVATIVE_STEP)[2]
        minus = _project(case, baseline, angle - DERIVATIVE_STEP)[2]
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
    motions = _place(selected.motions, projection.lengths, case)
    gap = magnitude(difference(motions[-1].jet(1)[0], case.end))
    connected = gap <= 1e-8
    allocation = TravelAllocation(
        AllocationStatus.FEASIBLE if connected else AllocationStatus.UNRESOLVED,
        projection.lengths if connected else None,
        checked,
    )
    return ClosurePlan(
        motions,
        connected,
        allocation,
        lower,
        gap,
        selected.kind,
        lane_bound(case, motions),
        angle,
        updates,
        calls,
        checked,
        tuple(history),
        termination,
    )
