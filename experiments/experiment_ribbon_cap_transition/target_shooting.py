"""
Jointly fit three admissible turns and travel to fixed endpoint position and frame.

This bounded development method frees all local turning axes and angles rather
than continuing one orientation-preserving schedule angle. Accepted steps must
decrease the combined position/frame residual; exact closure is never snapped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable

from cable_bundler.routing.geometry import difference, dot, magnitude, unit

from .banked_schedule import TurnSchedule
from .bounded_travel import AllocationStatus, TravelAllocation
from .closure_schedule import initial
from .coupled_motion import ZERO, CoupledMotion
from .endpoint_first import EndpointCase
from .event_cases import S_NAME
from .event_cases import construct as control_construct
from .material_allocation import MaterialPlan
from .material_policy import minimum_travel, place, prototypes
from .material_strip import MaterialSpan

TravelPolicy = Callable[[EndpointCase, tuple[MaterialSpan, ...]], tuple[float, ...]]

MAX_UPDATES = 12
MAX_EVALUATIONS = 181


@dataclass(frozen=True)
class Shot:
    """
    Retain one evaluated material plan and dimensionless endpoint residual.
    """

    plan: MaterialPlan
    residual: tuple[float, ...]

    @property
    def error(self) -> float:
        """
        Return squared combined endpoint residual for step acceptance.
        """
        return sum(value * value for value in self.residual)


def _solve(matrix: list[list[float]], right: list[float]) -> list[float]:
    """
    Solve a small damped positive-definite system with partial pivoting.

    Singular/nonfinite systems reject rather than returning a guessed step.
    Inputs are copied; no external numerical package is required.
    """
    size = len(right)
    rows = [list(row) + [value] for row, value in zip(matrix, right)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda candidate: abs(rows[candidate][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        if not math.isfinite(divisor) or abs(divisor) < 1e-18:
            raise ValueError("Endpoint shooting system is singular.")
        rows[column] = [value / divisor for value in rows[column]]
        for index in range(size):
            if index != column:
                factor = rows[index][column]
                rows[index] = [a - factor * b for a, b in zip(rows[index], rows[column])]
    result = [row[-1] for row in rows]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("Endpoint shooting step is nonfinite.")
    return result


def _bounded(values: tuple[float, ...]) -> tuple[float, ...]:
    """
    Restrict solver coordinates without changing external targets or geometry rules.

    First three angles are within +/-pi, next three ruling slopes within +/-4;
    seven travel surpluses are nonnegative in endpoint-chord units. These search
    bounds do not establish infeasibility when closure is unsuccessful.
    """
    return tuple(
        max(-math.pi, min(math.pi, value))
        if index < 3
        else max(-4.0, min(4.0, value))
        if index < 6
        else max(0.0, value)
        for index, value in enumerate(values)
    )


def evaluate(
    case: EndpointCase, values: tuple[float, ...], *, travel_policy: TravelPolicy | None = None
) -> Shot:
    """
    Construct admissible turns and regular material transitions from13 coordinates.

    Every local rotation axis is unit(eta*T+W); no forbidden width-axis bend or
    isolated straight twist is introduced. Existing seven-span floor policies
    remain authoritative. Frame errors are explicit alongside position error.
    A supplied experimental travel policy changes only the length floors;the
    default preserves the historical joint-shooting computation.
    """
    if len(values) != 13 or not all(math.isfinite(value) for value in values):
        raise ValueError("Shooting requires thirteen finite coordinates.")
    values = _bounded(values)
    scale = max(magnitude(difference(case.end, case.start)), case.diameter_mm)
    tangent, width = case.start_tangent, case.start_width
    motions = [CoupledMotion(ZERO, tangent, width, width, 0, 1)]
    for angle, slope in zip(values[:3], values[3:6]):
        axis = unit(ZERO.translated(tangent, slope).translated(width, 1))
        motion = CoupledMotion(ZERO, tangent, width, axis, angle, 1)
        motions.append(motion)
        tangent, width = motion.frame(1)
        motions.append(CoupledMotion(ZERO, tangent, width, width, 0, 1))
    selected = TurnSchedule(initial(case).kind, tuple(motions))
    spans = prototypes(selected)
    floors = minimum_travel if travel_policy is None else travel_policy
    lower = floors(case, spans)
    lengths = tuple(floor + scale * extra for floor, extra in zip(lower, values[6:]))
    strip = place(case, spans, lengths)
    placed = tuple(span.motion for span in strip.spans)
    end = placed[-1].jet(1)[0]
    tangent, width = placed[-1].frame(1)
    gap = magnitude(difference(end, case.end))
    tangent_error = magnitude(difference(tangent, case.end_tangent))
    width_error = magnitude(difference(width, case.end_width))
    connected = gap <= 1e-8 and max(tangent_error, width_error) <= 1e-8
    residual = tuple(
        value / divisor
        for vector, divisor in (
            (difference(end, case.end), scale),
            (difference(tangent, case.end_tangent), 1.0),
            (difference(width, case.end_width), 1.0),
        )
        for value in (vector.x, vector.y, vector.z)
    )
    plan = MaterialPlan(
        placed,
        connected,
        TravelAllocation(
            AllocationStatus.FEASIBLE if connected else AllocationStatus.UNRESOLVED,
            lengths if connected else None,
            0,
        ),
        lower,
        gap,
        selected.kind,
        max(m.maximum_curvature() for m in placed),
        0,
        0,
        0,
        0,
        (),
        "joint endpoint shooting evaluation",
        strip,
    )
    return Shot(plan, residual)


def construct(
    case: EndpointCase,
    *,
    checkpoint: Callable[[], None] | None = None,
    travel_policy: TravelPolicy | None = None,
) -> tuple[MaterialPlan, dict[str, object]]:
    """
    Make at most12 joint damped updates,13 derivative probes and2 trials per update.

    One deterministic seed is obtained from the original motion decomposition;
    initial slopes are clipped to the declared search box. Each forward difference
    uses1e-5 parameter units. Step norm is capped0.35; a half step is tried only
    if the full step fails improvement. Rejected rounds increase damping tenfold;
    accepted rounds halve it. All attempts count within181 evaluations. Controls
    use unchanged analytic construction, with no shooting or retry.
    An optional caller checkpoint runs before each numerical round to enforce
    external resource limits; its exception propagates without a local retry.
    A supplied travel policy is forwarded to every probe/trial identically;
    controls retain their unchanged analytic construction.
    """
    if case.name in ("control", "reference_broad_return", S_NAME):
        return control_construct(case), {"evaluations": 0, "error_history": []}

    def observe(coordinates: tuple[float, ...]) -> Shot:
        """
        Apply one fixed floor policy to every seed,probe and candidate step.
        """
        if travel_policy is None:
            return evaluate(case, coordinates)
        return evaluate(case, coordinates, travel_policy=travel_policy)

    selected = initial(case)
    angles, slopes = [], []
    for motion in selected.motions[1::2]:
        b = dot(motion.axis, motion.width)
        if abs(b) <= 1e-12:
            raise ValueError("Original decomposition contains pure twist.")
        angles.append(motion.angle * (1 if b > 0 else -1))
        slopes.append(dot(motion.axis, motion.tangent) / b)
    values = _bounded(tuple(angles + slopes + [0.0] * 7))
    shot = observe(values)
    evaluations, updates, damping = 1, 0, 1e-3
    history = [shot.error]
    for _ in range(MAX_UPDATES):
        if shot.plan.connected:
            break
        if checkpoint is not None:
            checkpoint()
        columns = []
        for index in range(13):
            probe = list(values)
            step = -1e-5 if index < 6 and values[index] >= (math.pi if index < 3 else 4) else 1e-5
            probe[index] += step
            observed = observe(tuple(probe))
            evaluations += 1
            columns.append(tuple((a - b) / step for a, b in zip(observed.residual, shot.residual)))
        matrix = [
            [
                sum(a * b for a, b in zip(left, right)) + (damping if i == j else 0)
                for j, right in enumerate(columns)
            ]
            for i, left in enumerate(columns)
        ]
        right = [-sum(a * b for a, b in zip(column, shot.residual)) for column in columns]
        delta = _solve(matrix, right)
        norm = math.sqrt(sum(value * value for value in delta))
        factor = min(1.0, 0.35 / norm) if norm else 1.0
        accepted = False
        for fraction in (1.0, 0.5):
            trial = _bounded(tuple(a + fraction * factor * b for a, b in zip(values, delta)))
            candidate = observe(trial)
            evaluations += 1
            if candidate.error < shot.error:
                values, shot, accepted = trial, candidate, True
                break
        updates += 1
        damping = max(1e-8, damping / 2) if accepted else damping * 10
        history.append(shot.error)
    if evaluations > MAX_EVALUATIONS:
        raise RuntimeError("Endpoint shooting evaluation budget exceeded.")
    plan = replace(
        shot.plan,
        updates=updates,
        history=tuple((float(index), error) for index, error in enumerate(history)),
        termination="joint endpoint reached"
        if shot.plan.connected
        else "joint update budget exhausted",
    )
    return plan, {"evaluations": evaluations, "error_history": history, "coordinates": values}
