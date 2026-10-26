"""
Fit fixed endpoint poses with cold-start material-director fields.

This bounded experimental shooting method has no stored fixture paths,case-name
branches,post-result target movement or geometric endpoint snapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Callable

from cable_bundler.routing.geometry import Vector3, cross, difference, dot, magnitude, unit

from .coupled_motion import orientation_angles
from .director_rotation_transport import integrate_rotation
from .director_route_objective import free_penalties, regular_penalties
from .director_route_seed import corkscrew_seed
from .director_routing_field import RoutingField
from .director_seed_bank import ranked_seed
from .director_transport import DirectorPath, integrate
from .endpoint_first import EndpointCase, controls

# noinspection PyProtectedMember
from .target_shooting import _solve


class TransportMethod(Enum):
    """
    Distinguish the retained free-axis baseline from structural unit rotations.
    """

    AXES = "axis-RK4"
    ROTATION = "rotation-RK4"
    REGULAR = "regular-rotation-RK4"
    FREE = "free-rotation-RK4"


class SeedMethod(Enum):
    """
    Keep initialization comparisons explicit without per-case named branches.
    """

    OBLIQUE = "oblique-events"
    CORKSCREW = "coupled-reversal"
    BANK = "fixed-generic-bank"


@dataclass(frozen=True)
class ShootingPolicy:
    """
    Freeze coarse/final grids,iteration limits and step size before a batch.
    """

    coarse_rounds: int = 12
    final_rounds: int = 6
    maximum_step: float = 1.5
    transport: TransportMethod = TransportMethod.AXES
    seed_method: SeedMethod = SeedMethod.OBLIQUE


BASELINE = ShootingPolicy()
ROTATION = ShootingPolicy(transport=TransportMethod.ROTATION)
REGULAR = ShootingPolicy(18, 3, 1.5, TransportMethod.REGULAR)
CORKSCREW = ShootingPolicy(18, 3, 1.5, TransportMethod.REGULAR, SeedMethod.CORKSCREW)
FREE = ShootingPolicy(18, 3, 1.5, TransportMethod.FREE, SeedMethod.CORKSCREW)
BANK = ShootingPolicy(18, 3, 1.5, TransportMethod.FREE, SeedMethod.BANK)


def damped_step(
    columns: list[tuple[float, ...]], errors: tuple[float, ...], damping: float
) -> list[float]:
    """
    Solve the small damped least-squares update without a numerical dependency.
    """
    normal: list[list[float]] = []
    gradient: list[float] = []
    for i, column in enumerate(columns):
        normal.append(
            [
                sum(a * b for a, b in zip(column, other)) + (damping if i == j else 0)
                for j, other in enumerate(columns)
            ]
        )
        gradient.append(-sum(a * b for a, b in zip(column, errors)))
    return _solve(normal, gradient)


def bounded(values: tuple[float, ...]) -> tuple[float, ...]:
    """
    Restrict search coordinates without changing target poses or geometry criteria.
    """
    if len(values) != 10 or not all(math.isfinite(v) for v in values):
        raise ValueError("Director shooting requires ten finite coordinates.")
    return tuple(
        max(-4 * math.pi, min(4 * math.pi, v))
        if i < 5
        else max(-3.0, min(3.0, v))
        if i < 9
        else max(1.0, min(5.0, v))
        for i, v in enumerate(values)
    )


def field_for(
    case: EndpointCase, values: tuple[float, ...], *, policy: ShootingPolicy = BASELINE
) -> RoutingField:
    """
    Translate bounded coordinates to a smooth field with structural normal end caps.
    """
    if bounded(values) != values:
        raise ValueError("Shooting coordinates lie outside the frozen search bounds.")
    distance = magnitude(difference(case.end, case.start))
    ruling_scale = 1.0
    if policy.transport is TransportMethod.REGULAR:
        half = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
        bound = (
            2
            * math.pi
            * (abs(values[5]) + abs(values[6]) + 2 * abs(values[7]) + 2 * abs(values[8]))
        )
        allowed = 0.9 * distance * values[9] / half
        ruling_scale = allowed / math.hypot(allowed, bound)
    return RoutingField(
        case.name,
        distance * values[9],
        (values[0], values[1], values[2], values[3]),
        (
            values[5] * ruling_scale,
            -values[5] * ruling_scale,
            values[6] * ruling_scale,
            values[7] * ruling_scale,
        ),
        case.lines,
        case.diameter_mm,
        values[4],
        values[8] * ruling_scale,
    )


def seed(case: EndpointCase, method: SeedMethod = SeedMethod.OBLIQUE) -> tuple[float, ...]:
    """
    Derive one deterministic seed from endpoint geometry alone.

    Fit three oblique-axis orientation increments to the bending basis. This
    initializes a continuous field,not three geometric sections. Equal frames
    use chord-derived planar bending;exact straight poses start with zero fields.
    """
    controls(case)
    chord = difference(case.end, case.start)
    distance = magnitude(chord)
    if (
        magnitude(difference(case.start_width, case.end_width)) < 1e-10
        and abs(dot(chord, case.start_width)) < 1e-10
    ):
        normal = cross(case.start_width, case.start_tangent)
        theta = math.atan2(dot(case.end_tangent, normal), dot(case.end_tangent, case.start_tangent))
        direction = math.atan2(dot(chord, normal), dot(chord, case.start_tangent))
        if abs(abs(theta) - math.pi) < 1e-8 and direction < 0:
            theta = -math.pi
        bend = 2 * math.pi * (direction - theta / 2)
        ratio = 1.0 if max(abs(theta), abs(bend)) < 1e-10 else 1.2
        return bounded((theta, 0.0, bend, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ratio))
    if method is SeedMethod.CORKSCREW:
        return bounded(corkscrew_seed(case))
    angles = orientation_angles(
        case.start_tangent, case.start_width, case.end_tangent, case.end_width
    )
    if max(abs(a) for a in angles) < 1e-9:
        normal = cross(case.start_width, case.start_tangent)
        bend = 2 * math.pi * math.atan2(dot(chord, normal), dot(chord, case.start_tangent))
        lateral = abs(dot(chord, case.start_width)) > 1e-8
        if abs(bend) < 0.1 and lateral:
            bend = 0.5
        straight = magnitude(difference(unit(chord), case.start_tangent)) < 1e-10
        return bounded(
            (
                0.0,
                0.0,
                bend,
                0.0,
                0.0,
                0.0,
                0.25 if lateral else 0.0,
                0.0,
                0.0,
                1.0 if straight else 1.2,
            )
        )
    rows = []
    target = []
    for u, angle, sign in zip((1 / 6, 0.5, 5 / 6), angles, (1, -1, 1)):
        a = 2 * math.pi * u
        rows.append((1.0, math.cos(a), math.sin(a), math.sin(2 * a), math.cos(2 * a)))
        target.append(3 * angle * sign / math.sqrt(2))
    matrix = [
        [sum(row[i] * row[j] for row in rows) + (1e-5 if i == j else 0) for j in range(5)]
        for i in range(5)
    ]
    right = [sum(row[i] * v for row, v in zip(rows, target)) for i in range(5)]
    bend = _solve(matrix, right)
    return bounded(tuple(bend) + (-0.5, 0.0, 0.0, -5 / 6, max(1.5, min(3.0, 200 / distance))))


def endpoint_metrics(case: EndpointCase, path: DirectorPath) -> dict[str, float]:
    """
    Measure actual A-edge arrival before companion compatibility or native drawing.
    """
    half = path.field.half_width_mm
    point, velocity = path.lane(1, half)
    target = case.end.translated(case.end_width, half)
    state, _ = path.pose(1)
    tangent = unit(velocity)
    width = Vector3(*state[6:9])
    return {
        "edge_position_error_mm": magnitude(difference(point, target)),
        "edge_tangent_error": magnitude(difference(tangent, case.end_tangent)),
        "terminal_width_error": magnitude(difference(width, case.end_width)),
        "center_endpoint_error_mm": magnitude(difference(Vector3(*state[:3]), case.end)),
    }


def residual(case: EndpointCase, path: DirectorPath) -> tuple[float, ...]:
    """
    Build a dimensionless A-position/material-frame closure residual,not an energy.

    The final gate uses actual A velocity and full-width regularity separately.
    """
    state = path.states[-1]
    half = path.field.half_width_mm
    actual = Vector3(*state[:3]).translated(Vector3(*state[6:9]), half)
    target = case.end.translated(case.end_width, half)
    delta = difference(actual, target)
    distance = magnitude(difference(case.end, case.start))
    tangent = difference(Vector3(*state[3:6]), case.end_tangent)
    width = difference(Vector3(*state[6:9]), case.end_width)
    return (
        delta.x / distance,
        delta.y / distance,
        delta.z / distance,
        tangent.x,
        tangent.y,
        tangent.z,
        width.x,
        width.y,
        width.z,
    )


def solve(
    case: EndpointCase,
    checkpoint: Callable[[], None],
    *,
    policy: ShootingPolicy = BASELINE,
    progress: dict[str, Any] | None = None,
) -> tuple[DirectorPath, dict[str, Any]]:
    """
    Fit one cold start under a registered coarse64/final512policy.

    Baseline/rotation use12+6rounds(max218evaluations);geometry-aware policies
    use18+3(max254). Each round has ten probes and at most two full/half trials.
    BANK first screens at most46generic starts and refines only the best one.
    Coarse geometry-aware objectives include penalties;fine fits endpoint pose.
    Only decreasing stage objectives are accepted,stepnorm<=1.5. Actual final
    position/frame gates remain1e-8;no native success follows from numerical fit.
    """
    if policy not in (BASELINE, ROTATION, REGULAR, CORKSCREW, FREE, BANK):
        raise ValueError("Use the frozen baseline shooting policy.")
    started = perf_counter()
    seed_metrics: dict[str, Any] = {"seed_screenings": 0, "seed_seconds": 0.0}
    if policy.seed_method is SeedMethod.BANK and not (
        magnitude(difference(case.start_width, case.end_width)) < 1e-10
        and abs(dot(difference(case.end, case.start), case.start_width)) < 1e-10
    ):

        def build_seed(coordinates: tuple[float, ...]) -> RoutingField:
            """
            Bind the same free-field coordinate map used by nonlinear refinement.
            """
            return field_for(case, coordinates, policy=policy)

        def score_seed(candidate_path: DirectorPath) -> tuple[float, ...]:
            """
            Compare generic seeds with the identical coarse endpoint/policy objective.
            """
            return residual(case, candidate_path) + free_penalties(case, candidate_path)

        values, seed_metrics = ranked_seed(
            case, (seed(case), seed(case, SeedMethod.CORKSCREW)), build_seed, score_seed, checkpoint
        )
    else:
        values = seed(case, policy.seed_method)
    initial = (
        case.start.x,
        case.start.y,
        case.start.z,
        case.start_tangent.x,
        case.start_tangent.y,
        case.start_tangent.z,
        case.start_width.x,
        case.start_width.y,
        case.start_width.z,
    )
    evaluations = 0
    stages = []

    def observe(
        coordinates: tuple[float, ...], grid: int
    ) -> tuple[DirectorPath, tuple[float, ...]]:
        """
        Count all transport evaluations and enforce caller scheduling limits.
        """
        nonlocal evaluations
        checkpoint()
        evaluations += 1
        if progress is not None:
            progress.update(evaluations=evaluations, grid=grid, seconds=perf_counter() - started)
        transport = integrate if policy.transport is TransportMethod.AXES else integrate_rotation
        observed_path = transport(
            field_for(case, coordinates, policy=policy), grid, checkpoint, initial=initial
        )
        errors = residual(case, observed_path)
        if grid == 64 and policy.transport is TransportMethod.REGULAR:
            errors += regular_penalties(case, observed_path)
        if grid == 64 and policy.transport is TransportMethod.FREE:
            errors += free_penalties(case, observed_path)
        return observed_path, errors

    for steps, rounds, tolerance in (
        (64, policy.coarse_rounds, 1e-6),
        (512, policy.final_rounds, 1e-12),
    ):
        stage_started = perf_counter()
        path, error_vector = observe(values, steps)
        error = sum(v * v for v in error_vector)
        history = [error]
        damping = 1e-3 if steps == 64 else 1e-8
        for _ in range(rounds):
            if max(abs(v) for v in error_vector) < tolerance:
                break
            if (
                steps == 512
                and policy.transport is not TransportMethod.AXES
                and max(endpoint_metrics(case, path).values()) <= 1e-8
            ):
                break
            columns = []
            for i in range(10):
                probe = list(values)
                step = (
                    -1e-5
                    if (i < 5 and values[i] >= 4 * math.pi)
                    or (5 <= i < 9 and values[i] >= 3)
                    or (i == 9 and values[i] >= 5)
                    else 1e-5
                )
                probe[i] += step
                proposed = bounded(tuple(probe))
                _, observed = observe(proposed, steps)
                actual_step = proposed[i] - values[i]
                columns.append(tuple((a - b) / actual_step for a, b in zip(observed, error_vector)))
            delta = damped_step(columns, error_vector, damping)
            norm = math.sqrt(sum(v * v for v in delta))
            factor = min(1.0, policy.maximum_step / norm) if norm else 1.0
            accepted = False
            for fraction in (1.0, 0.5):
                proposed = bounded(tuple(a + fraction * factor * b for a, b in zip(values, delta)))
                candidate, candidate_vector = observe(proposed, steps)
                candidate_error = sum(v * v for v in candidate_vector)
                if candidate_error < error:
                    values, path, error_vector, error, accepted = (
                        proposed,
                        candidate,
                        candidate_vector,
                        candidate_error,
                        True,
                    )
                    break
            history.append(error)
            damping = max(1e-12, damping / 3) if accepted else damping * 10
        stages.append(
            {"steps": steps, "seconds": perf_counter() - stage_started, "history": history}
        )
    if evaluations > 2 + 12 * (policy.coarse_rounds + policy.final_rounds):
        raise RuntimeError("Director shooting evaluation bound exceeded.")
    metrics: dict[str, Any] = endpoint_metrics(case, path)
    metrics.update(
        seed_metrics,
        seconds=perf_counter() - started,
        evaluations=evaluations,
        coordinates=values,
        stages=stages,
    )
    metrics["endpoint_gate_passed"] = (
        max(
            metrics[k]
            for k in (
                "edge_position_error_mm",
                "edge_tangent_error",
                "terminal_width_error",
                "center_endpoint_error_mm",
            )
        )
        <= 1e-8
    )
    return path, metrics
