"""
Restore fixed endpoint pose after sampled width-clearance steps in the broad chart.

This bounded heuristic does not certify continuous clearance or equilibrium.
Coarse projection uses its initial replay pose;fine closure uses original targets.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from experiments.experiment_ribbon_cap_transition.compatible_coordinates import (
    probe_coordinates,
    trial_coordinates,
)
from experiments.experiment_ribbon_cap_transition.compatible_strip import CompatiblePath
from experiments.experiment_ribbon_cap_transition.director_constrained_step import constrained_step
from experiments.experiment_ribbon_cap_transition.director_shooting import residual
from experiments.experiment_ribbon_cap_transition.endpoint_first import EndpointCase

from .active_clearance import ClearanceSnapshot, sample
from .box_fit import POLISH
from .box_fit import refine as fit_endpoints
from .broad_chart import bounds, carrier_maximum, integrate
from .families import Seed
from .guidance import DistancePair

Transport = Callable[[tuple[float, ...]], CompatiblePath]


def distance_model(snapshot: ClearanceSnapshot, path: CompatiblePath) -> tuple[float, ...]:
    """
    Recompute closest distance at fixed witness fractions as separating normals rotate.
    """
    return tuple(
        deficit
        if plane is None
        else DistancePair(plane.first_u, plane.second_u, plane.thickness_mm).violation(path)
        for plane, deficit in zip(snapshot.planes, snapshot.deficits)
    )


def _project(
    case: EndpointCase,
    proposed: tuple[float, ...],
    candidate: CompatiblePath,
    reference: tuple[float, ...],
    transport: Transport,
) -> tuple[tuple[float, ...], CompatiblePath]:
    """
    Spend at most three box-aware Newton corrections toward one frozen coarse pose.
    """
    maximum = carrier_maximum(case)
    lower, upper = bounds(case)
    for _ in range(3):
        errors = tuple(a - b for a, b in zip(residual(case, candidate), reference))
        if max(abs(value) for value in errors) <= 1e-7:
            break
        columns = []
        for index in range(10):
            _, parameters = probe_coordinates(proposed, index, maximum)
            probe = transport(parameters)
            step = parameters[index] - proposed[index]
            observed = tuple(a - b for a, b in zip(residual(case, probe), reference))
            columns.append(tuple((a - b) / step for a, b in zip(observed, errors)))
        correction = constrained_step(columns, errors, 1e-8, [()] * 10, (), proposed, lower, upper)
        before = sum(value * value for value in errors)
        for fraction in (1.0, 0.5):
            _, parameters = trial_coordinates(proposed, correction.values, fraction, maximum)
            probe = transport(parameters)
            after = sum((a - b) ** 2 for a, b in zip(residual(case, probe), reference))
            if after < before:
                proposed, candidate = parameters, probe
                break
    return proposed, candidate


def refine(
    case: EndpointCase, seed: Seed, base: dict[str, Any], checkpoint: Callable[[], None]
) -> tuple[CompatiblePath, dict[str, Any]]:
    """
    Try at most eight projected width steps and four fine original-target steps.

    Accept actual projected pose error<=1e-7 and strictly decreasing globally
    audited clearance merit. Final physical/endpoint acceptance remains external.
    At most700coarse plus50polish transports;all rejected work counts.
    """
    started = perf_counter()
    values = base["coordinates"]
    count = 0
    trials: list[dict[str, Any]] = []
    maximum = carrier_maximum(case)
    lower, upper = bounds(case)

    def transport(parameters: tuple[float, ...]) -> CompatiblePath:
        """
        Retain the original inclusive coarse transport ceiling and caller checkpoint.
        """
        nonlocal count
        count += 1
        if count > 700:
            raise RuntimeError("Projection transport cap.")
        return integrate(case, parameters, 64, checkpoint)

    path = transport(values)
    reference = residual(case, path)
    current = sample(case, path, checkpoint)
    score = sum(value * value for value in current.deficits)
    for outer in range(8):
        if max(current.deficits) < 1e-9:
            break
        model = distance_model(current, path)
        pose = residual(case, path)
        columns = []
        slack_columns = []
        for index in range(10):
            _, parameters = probe_coordinates(values, index, maximum)
            probe = transport(parameters)
            step = parameters[index] - values[index]
            columns.append(
                tuple((a - b) / step for a, b in zip(distance_model(current, probe), model))
            )
            derivative = tuple((a - b) / step for a, b in zip(residual(case, probe), pose))
            slack_columns.append(tuple(value for d in derivative for value in (-d, d)))
        quadratic = constrained_step(
            columns, model, 1e-3, slack_columns, (1e-7,) * 18, values, lower, upper
        )
        accepted = False
        for fraction in (1.0, 0.5):
            _, proposed = trial_coordinates(values, quadratic.values, fraction, maximum)
            candidate = transport(proposed)
            proposed, candidate = _project(case, proposed, candidate, reference, transport)
            error = max(abs(a - b) for a, b in zip(residual(case, candidate), reference))
            fresh = sample(case, candidate, checkpoint)
            after = sum(value * value for value in fresh.deficits)
            take = error <= 1e-7 and after < score
            trials.append(
                dict(
                    outer=outer,
                    fraction=fraction,
                    pose_error=error,
                    before=score,
                    after=after,
                    contact_pairs=fresh.contacts["contact_pairs"],
                    accepted=take,
                    coordinates=proposed,
                )
            )
            if take:
                values, path, current, score = proposed, candidate, fresh, after
                accepted = True
                break
        if not accepted:
            break
    fresh_seed = Seed(seed.index, values, score, seed.descriptor)
    path, metrics = fit_endpoints(case, fresh_seed, checkpoint, POLISH)
    metrics.update(
        projection_trials=trials,
        projection_reference=reference,
        projection_transports=count,
        evaluations=metrics["evaluations"] + count,
        seconds=perf_counter() - started,
    )
    return path, metrics
