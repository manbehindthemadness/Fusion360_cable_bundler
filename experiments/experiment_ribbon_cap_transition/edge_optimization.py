"""
Improve material compatibility by moving only interior boundary controls.

Degree elevation preserves the seed shape;two or four free interior controls
provide six or twelve coordinates without changing terminal first three derivatives.
Warm-started development refinement is not cold-start generalized routing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Callable

from cable_bundler.routing.geometry import Vector3, difference, magnitude

from .edge_first import BoundaryCurve, EdgeCandidate, construct, frame
from .endpoint_first import EndpointCase

# noinspection PyProtectedMember
from .target_shooting import _solve

SAMPLES = 65
ROUNDS = 6
MAX_EVALUATIONS = 49


@dataclass(frozen=True)
class InteriorPolicy:
    """
    Fix interior freedom and update count before a bounded development comparison.
    """

    free_controls: int
    rounds: int
    samples: int = SAMPLES
    center_goal: float = 0.8
    lane_radius_diameters: float = 3.0
    sphere_scale: float = 1.0


STANDARD = InteriorPolicy(2, ROUNDS)
EXPANDED = InteriorPolicy(4, 3)
PRECISION = InteriorPolicy(4, 1, 129, 0.78, 3.1, 0.98)


def elevate(curve: BoundaryCurve, free_controls: int = 2) -> BoundaryCurve:
    """
    Elevate a curve to the declared interior freedom without altering its polynomial.
    """
    points = curve.points
    target = 8 + free_controls
    if free_controls not in (2, 4) or len(points) > target:
        raise ValueError("Interior policy cannot lower degree or use unsupported freedom.")
    while len(points) < target:
        degree = len(points) - 1
        points = (
            (points[0],)
            + tuple(
                points[index].translated(
                    difference(points[index - 1], points[index]), index / (degree + 1)
                )
                for index in range(1, degree + 1)
            )
            + (points[-1],)
        )
    return BoundaryCurve(points)


def deform(seed: BoundaryCurve, values: tuple[float, ...], scale: float) -> BoundaryCurve:
    """
    Move only interior controls,leaving all terminal constraints intact.
    """
    count = len(seed.points) - 8
    if count not in (2, 4) or len(values) != 3 * count or not all(math.isfinite(v) for v in values):
        raise ValueError("Interior deformation needs paired finite coordinates for its policy.")
    points = list(seed.points)
    for index in range(count):
        shift = Vector3(*(scale * value for value in values[index * 3 : index * 3 + 3]))
        points[index + 4] = points[index + 4].translated(shift, 1)
    return BoundaryCurve(tuple(points))


def residuals(
    case: EndpointCase,
    curve: BoundaryCurve,
    values: tuple[float, ...],
    *,
    policy: InteriorPolicy = STANDARD,
) -> tuple[float, ...]:
    """
    Screen the policy's fixed stations and conservative curvature/extent goals.

    A0.1Jacobian margin is a search goal only;final acceptance uses the unchanged
    positive-Jacobian gate at257stations. No invalid Jacobian is clipped into a
    passing geometry. Small coordinate regularization discourages arbitrary travel.
    Singular sampled frames receive an explicit surrogate penalty;the final
    assessor still rejects them. This objective is kinematic,not elastic energy.
    Default goals match physical gates;PRECISION tightens only search goals to
    cover inter-sample peaks. Acceptance thresholds remain outside this function.
    """
    half_width = case.lines * case.diameter_mm / 2 + case.diameter_mm * 0.1
    reach = math.hypot(half_width, case.diameter_mm / 2)
    sphere = 2.5 * case.lines * case.diameter_mm * policy.sphere_scale
    center = case.start.translated(difference(case.end, case.start), 0.5)
    result = []
    for index in range(policy.samples):
        try:
            observed = frame(curve, index / (policy.samples - 1))
            jacobian = min(1.0, 1 - 2 * half_width * observed.slope_rate / observed.speed)
            center_jacobian = 1 - half_width * observed.slope_rate / observed.speed
            folding = max(0.0, 0.1 - jacobian)
            curvature = (
                max(0.0, observed.curvature * reach / (policy.center_goal * center_jacobian) - 1)
                if center_jacobian > 0
                else 1 + abs(center_jacobian)
            )
            lane_curvature = (
                max(
                    0.0,
                    observed.curvature
                    * (policy.lane_radius_diameters * case.diameter_mm)
                    / jacobian
                    - 1,
                )
                if jacobian > 0
                else 1 + abs(jacobian)
            )
            occupied = max(
                magnitude(difference(observed.lane(offset)[0], center)) + case.diameter_mm / 2
                for offset in (0.0, -half_width, -2 * half_width)
            )
            containment = max(0.0, occupied / sphere - 1)
            result.extend(
                (
                    math.log1p(folding),
                    math.log1p(curvature),
                    math.log1p(lane_curvature),
                    math.log1p(containment),
                )
            )
        except ValueError:
            result.extend((20.0, 20.0, 20.0, 20.0))
    result.extend(value * 1e-3 for value in values)
    return tuple(result)


def improve(
    case: EndpointCase,
    seed: BoundaryCurve,
    checkpoint: Callable[[], None],
    *,
    policy: InteriorPolicy = STANDARD,
) -> tuple[EdgeCandidate, dict[str, object]]:
    """
    Make the declared bounded LM rounds without changing boundary data.

    Six forward differences(1e-4)and at most two trials per round give49screenings
    maximum. Step norm<=0.25,coordinates within[-1,1]chord units. Only decreasing
    objective is accepted;damping halves/increases tenfold on acceptance/rejection.
    Every evaluation calls the external resource checkpoint. One final257station
    audit independently gates companion drawing,including unscreened lane radius.
    STANDARD uses6rounds/6coordinates/49screens;EXPANDED uses3rounds/12coordinates/
    43screens. Both retain identical physical checks and step/coordinate bounds.
    PRECISION uses1round/12coordinates/15screens,129stations and tighter search
    goals;the same independent final gate controls all companion permission.
    """
    if policy not in (STANDARD, EXPANDED, PRECISION):
        raise ValueError("Use a registered bounded interior policy.")
    elevated = elevate(seed, policy.free_controls)
    scale = magnitude(difference(case.end, case.start))
    dimensions = 3 * policy.free_controls
    values = (0.0,) * dimensions
    evaluations = 0

    def observe(coordinates: tuple[float, ...]) -> tuple[BoundaryCurve, tuple[float, ...]]:
        """
        Count every bounded screening and preserve the same physical constraints.
        """
        nonlocal evaluations
        checkpoint()
        evaluations += 1
        observed_curve = deform(elevated, coordinates, scale)
        return observed_curve, residuals(case, observed_curve, coordinates, policy=policy)

    started = perf_counter()
    curve, residual = observe(values)
    error = sum(v * v for v in residual)
    history, damping = [error], 1e-2
    for _ in range(policy.rounds):
        columns = []
        for index in range(dimensions):
            probe = list(values)
            step = -1e-4 if values[index] >= 1 else 1e-4
            probe[index] += step
            _, observed = observe(tuple(probe))
            columns.append(tuple((a - b) / step for a, b in zip(observed, residual)))
        matrix = [
            [
                sum(a * b for a, b in zip(left, right)) + (damping if i == j else 0)
                for j, right in enumerate(columns)
            ]
            for i, left in enumerate(columns)
        ]
        right = [-sum(a * b for a, b in zip(column, residual)) for column in columns]
        delta = _solve(matrix, right)
        norm = math.sqrt(sum(v * v for v in delta))
        factor = min(1.0, 0.25 / norm) if norm else 1.0
        accepted = False
        for fraction in (1.0, 0.5):
            proposed = tuple(
                max(-1.0, min(1.0, a + fraction * factor * b)) for a, b in zip(values, delta)
            )
            shape, candidate_residual = observe(proposed)
            candidate_error = sum(v * v for v in candidate_residual)
            if candidate_error < error:
                values, curve, residual, error, accepted = (
                    proposed,
                    shape,
                    candidate_residual,
                    candidate_error,
                    True,
                )
                break
        damping = max(1e-8, damping / 2) if accepted else damping * 10
        history.append(error)
    maximum_evaluations = 1 + policy.rounds * (dimensions + 2)
    if evaluations > maximum_evaluations:
        raise RuntimeError("Interior edge-screening budget exceeded.")
    optimization_seconds = perf_counter() - started
    checkpoint()
    candidate = construct(case, reference_curve=curve)
    metrics = dict(candidate.metrics)
    metrics.update(
        optimization_seconds=optimization_seconds,
        screening_evaluations=evaluations,
        screening_stations=policy.samples,
        objective_history=history,
        interior_coordinates=values,
    )
    return replace(candidate, metrics=metrics), {
        "evaluations": evaluations,
        "objective_history": history,
    }
